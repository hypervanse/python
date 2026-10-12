"""
Procedural adaptive music: a 16-step sequencer that composes a new tune per run from a
key, a mood and a seed, and gates its voices by intensity (0..3).
"""

import random

import pygame

from flappy.engine.state import APP, AUDIO
from flappy.engine.synth import midi_hz, mix, synth, to_sound

VOICE_CH  = {"bass": 0, "arp": 1, "lead": 2, "drum": 3, "hat": 4}   # reserved mixer channels

VOICE_MIX = {"bass": 0.55, "arp": 0.26, "lead": 0.42, "drum": 0.70, "hat": 0.22}

# ---- procedural music ------------------------------------------------
# A song = 8 bars x 16 steps (16th notes) of events for 5 monophonic voices.
# Composition rules that keep generated music pleasant:
#   * chords come from a fixed diatonic scale via proven progressions
#   * the lead melody walks on the PENTATONIC subset (no semitone clashes)
#     and lands on a chord tone at each bar start
#   * an A A' A B phrase form gives repetition (memorability) + resolution
# Intensity layers (0..3) are gated at playback, so ONE song adapts to gameplay.
MOODS = {
    #           root  scale (semitones)      pentatonic        bpm   progressions (scale degrees)
    "title": (60, [0, 2, 4, 5, 7, 9, 11], [0, 2, 4, 7, 9],    104, [[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 4, 4]]),
    "play":  (57, [0, 2, 3, 5, 7, 8, 10], [0, 3, 5, 7, 10],   128, [[0, 5, 2, 6], [0, 3, 4, 0], [0, 5, 3, 4], [0, 6, 5, 6]]),
    "calm":  (60, [0, 2, 4, 5, 7, 9, 11], [0, 2, 4, 7, 9],     84, [[0, 3, 0, 4], [5, 3, 0, 4]]),
}

BASS_PATS = ["r...r...r...r...", "r.r.r.o.r.r.r.o.", "r..r..r.o..r.r..", "r.....r.r...f..."]

KICK_PATS = ["x...x...x...x...", "x.....x.x.......", "x...x...x..x.x.."]

SNARE_PAT = "....x.......x..."

HAT_PATS  = ["x.x.x.x.x.x.x.x.", "xxxxxxxxxxxxxxxx"]

ARP_SHAPES = [[0, 1, 2, 1], [0, 1, 2, 3], [2, 1, 0, 1], [0, 2, 1, 2]]

LEAD_RHYTHMS = [[0, 3, 6, 8, 12, 16, 19, 22, 24], [0, 4, 6, 8, 10, 12, 16, 20, 24, 28],
                [0, 2, 4, 8, 11, 14, 16, 18, 20, 24]]

def make_song(mood, seed):
    rng = random.Random(seed)
    root, scale, penta, bpm, progs = MOODS[mood]
    prog = rng.choice(progs)

    def deg(d, octv=0):                    # scale degree -> MIDI note (degrees wrap octaves)
        return root + 12 * (d // 7 + octv) + scale[d % 7]

    chords = [[deg(d), deg(d + 2), deg(d + 4)] for d in prog]
    pen = [root + 12 + p + 12 * o for o in (0, 1) for p in penta] + [root + 36]   # lead range
    bass_p, kick_p = rng.choice(BASS_PATS), rng.choice(KICK_PATS)
    arp = rng.choice(ARP_SHAPES)

    def motif(start_i):                    # random walk on pentatonic, chord tone on downbeats
        rhythm = rng.choice(LEAD_RHYTHMS)
        notes, i = [], start_i
        for _ in rhythm:
            i = max(0, min(len(pen) - 1, i + rng.choice((-2, -1, -1, 1, 1, 2, 0))))
            notes.append(i)
        return list(zip(rhythm, notes))

    A = motif(rng.randrange(3, 7))
    A2 = A[:-2] + [(s, max(0, min(len(pen) - 1, n + rng.choice((-1, 1))))) for s, n in A[-2:]]
    B = motif(A[-1][1])
    B[-1] = (B[-1][0], pen.index(root + 12) if (root + 12) in pen else 0)   # resolve to tonic
    phrases = [A, A2, A, B]                # each phrase = 2 bars (32 steps)

    total = 8 * 16
    ev = {v: [None] * total for v in ("bass", "arp", "lead")}
    drums = [[] for _ in range(total)]
    for s in range(total):
        bar, st = divmod(s, 16)
        ch = chords[bar % 4]
        c = bass_p[st]
        if c != ".":
            ev["bass"][s] = {"r": ch[0] - 12, "o": ch[0], "f": ch[2] - 12}[c]
        if st % 2 == 0:
            k = arp[(st // 2) % 4]
            ev["arp"][s] = ch[k] + 12 if k < 3 else ch[0] + 24
        if kick_p[st] == "x":
            drums[s].append("kick")
        if SNARE_PAT[st] == "x":
            drums[s].append("snare")
        drums[s].append(("hat0" if HAT_PATS[0][st] == "x" else None, "hat1"))
    for p, phrase in enumerate(phrases):
        for step, ni in phrase:
            ev["lead"][p * 32 + step] = pen[ni]
    return {"bpm": bpm, "total": total, "ev": ev, "drums": drums}

def instrument(voice, m):
    """Timbre per voice. Cached by (voice, note) -> each pitch synthesized once."""
    key = (voice, m)
    snd = AUDIO["notes"].get(key)
    if snd is None:
        f = midi_hz(m)
        if voice == "bass":
            buf = synth(0.26, f, wave="tri", vol=0.8, decay=5, release=0.05)
        elif voice == "arp":
            buf = synth(0.12, f, wave="square", vol=0.5, duty=0.125, decay=14)
        elif voice == "lead":
            buf = synth(0.30, f, wave="square", vol=0.55, duty=0.25, decay=3, vib_hz=6, vib_depth=0.012)
        elif voice == "kick":
            buf = synth(0.16, 160, 42, "sine", 0.95, decay=14)
        elif voice == "snare":
            buf = mix(synth(0.14, 7000, 3000, "noise", 0.6, decay=22), synth(0.08, 220, 160, "tri", 0.4, decay=30))
        else:   # hat
            buf = synth(0.04, 12000, None, "noise", 0.5, decay=80)
        snd = AUDIO["notes"][key] = to_sound(buf)
    return snd

def prewarm_song(song):
    for v in ("bass", "arp", "lead"):
        for m in set(x for x in song["ev"][v] if x is not None):
            instrument(v, m)
    for d in ("kick", "snare", "hat"):
        instrument(d, 0)

def music_play(mood, seed=None):
    """Switch song. Title uses a fixed seed (a recognizable theme); gameplay passes
    a fresh seed per run so every run has new music in the same key (so all notes
    are already cached -> switching never stalls on synthesis)."""
    if not AUDIO["ok"]:
        return
    seed = hash(mood) & 0xFFFF if seed is None else seed
    key = (mood, seed)
    song = AUDIO["song_cache"].get(key) or make_song(mood, seed)
    AUDIO["song_cache"][key] = song
    prewarm_song(song)
    AUDIO.update(song=song, step=0, acc=0.0)

def music_stop():
    AUDIO["song"] = None
    if AUDIO["ok"]:
        for ch in AUDIO["voices"].values():
            ch.stop()

def set_intensity(level):
    AUDIO["intensity"] = max(0, min(3, level))

def music_update(raw_dt):
    """Step sequencer driven by real time. Called once per frame; fires every 16th
    note that became due. Jitter is <= 1 frame (16 ms), inaudible for chiptune.
    After a stall it skips ahead instead of machine-gunning the backlog."""
    song = AUDIO["song"]
    if not AUDIO["ok"] or song is None or AUDIO["paused"]:
        return
    inten = AUDIO["intensity"]
    step_dur = 60.0 / (song["bpm"] * (1.08 if inten >= 3 else 1.0)) / 4.0
    AUDIO["acc"] += raw_dt
    if AUDIO["acc"] > 4 * step_dur:
        AUDIO["acc"] = step_dur
    vol = APP["settings"]["music_vol"]
    while AUDIO["acc"] >= step_dur:
        AUDIO["acc"] -= step_dur
        s = AUDIO["step"]
        AUDIO["step"] = (s + 1) % song["total"]
        if vol <= 0:
            continue
        V = AUDIO["voices"]
        for voice, gate in (("bass", 0), ("arp", 0), ("lead", 2)):   # layer gating by intensity
            m = song["ev"][voice][s]
            if m is not None and inten >= gate:
                V[voice].play(instrument(voice, m))
                V[voice].set_volume(VOICE_MIX[voice] * vol)
        for d in song["drums"][s]:
            if isinstance(d, tuple):                 # hats: 8ths at inten>=2, 16ths at inten>=3
                use = d[1] if inten >= 3 else (d[0] if inten >= 2 else None)
                if use:
                    V["hat"].play(instrument("hat", 0))
                    V["hat"].set_volume(VOICE_MIX["hat"] * vol)
            elif inten >= 1:
                V["drum"].play(instrument(d, 0))
                V["drum"].set_volume(VOICE_MIX["drum"] * vol)

def audio_pause(flag):
    """App backgrounded -> silence everything; Android keeps playing otherwise."""
    if not AUDIO["ok"]:
        return
    AUDIO["paused"] = flag
    if flag:
        pygame.mixer.pause()
    else:
        pygame.mixer.unpause()
