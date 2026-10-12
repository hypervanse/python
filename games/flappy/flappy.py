#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FLAPPY -- a Flappy Bird clone for Pydroid 3 (Android), also runs on desktop.

Single file, pygame + standard library only, zero asset files: every sprite is
pygame.draw primitives, every sound effect AND the adaptive music are synthesized
into raw PCM at startup, high scores / settings / trophies persist in SQLite.

    Pydroid 3 : open this file -> yellow play button.  Tap = flap, back = pause.
    Desktop   : python3 flappy.py      (click / SPACE / UP = flap, P or ESC = pause)
    Self-test : python3 flappy.py --selftest   (headless, exits 0 on success)

Difficulty knobs (gravity, flap impulse, gap size, pipe speed, spacing) are all
in section 0 with units and the effect of raising / lowering each one.

SECTION MAP -- when building a new game, sections 1-5 and 7 are infrastructure and
are kept as-is; you rewrite section 0 (identity/tuning) and section 6 (the game).
    0  CONFIG            identity, logical resolution, palette, game tuning knobs
    1  PLATFORM          display + scaling, unified touch/mouse/key input, lifecycle
    2  AUDIO ENGINE      PCM synthesizer, SFX bank, procedural adaptive music
    3  PERSISTENCE       SQLite: high-score table, settings, lifetime stats, trophies
    4  UI KIT            cached text, buttons, toasts, particles, popups, shake
    5  META SCREENS      title / pause / settings / initials / scores / trophies / over
    6  GAME              the actual game: new/input/update/draw/hud/bot + trophies + skins
    7  MAIN LOOP         frame driver, run lifecycle, --selftest harness
"""

import os
import sys
import math
import time
import json
import random
import sqlite3
import datetime
from array import array

# --selftest must pick SDL's headless drivers BEFORE pygame is imported
SELFTEST = "--selftest" in sys.argv
if SELFTEST:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")   # keep Pydroid's console clean

import pygame


# =====================================================================
# 0. CONFIG
# =====================================================================
GAME_ID    = "flappy"            # slug: names the database file -> one DB per game
GAME_TITLE = "FLAPPY"

BASE_W, BASE_H = 360, 640        # logical canvas, portrait. All coordinates use this space.
FPS        = 60
DT_MAX     = 1.0 / 30.0          # clamp simulation dt: a GC pause / app switch can't teleport objects
SR         = 22050               # audio sample rate; 22.05 kHz halves synthesis time vs 44.1 kHz
TOP_N      = 10                  # rows in the high-score table

# palette (shared by UI; the game section may define its own)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
UI_BG      = (18, 20, 38)
UI_PANEL   = (32, 36, 66)
UI_EDGE    = (90, 100, 170)
UI_ACCENT  = (255, 200, 60)
UI_GOOD    = (90, 230, 140)
UI_BAD     = (255, 90, 90)
UI_DIM     = (130, 135, 165)

# ---- game tuning (FLAPPY). Units: logical px, seconds, px/s, px/s^2. ----
# The physics are tuned for TOUCH, not keyboard spam: a finger tap has ~50-100 ms
# of latency and nobody can tap faster than ~6-7 Hz comfortably, so one flap must
# carry the bird a meaningful distance (~65 px) and the fall must be readable.
#   apex height of one flap = FLAP_V^2 / (2*GRAVITY) = 440^2/3000 ~= 65 px
#   time to apex            = FLAP_V / GRAVITY       = 0.29 s
GRAVITY      = 1500.0            # px/s^2 downward. Higher = heavier bird, harder; lower = floaty.
FLAP_V       = 440.0             # px/s upward velocity SET (not added) by a tap. Setting it makes
                                 #   every tap identical regardless of current fall speed -> predictable.
MAX_FALL     = 620.0             # px/s terminal velocity; caps how fast a missed tap punishes you.
BIRD_X       = 100               # px, fixed horizontal position of the bird (world scrolls instead)
BIRD_R       = 14                # px, drawn body radius
HITBOX_HALF  = 10                # px, half-size of the square collision box (< BIRD_R = forgiveness)
GROUND_H     = 84                # px, ground strip height at the bottom
GROUND_Y     = BASE_H - GROUND_H # px, top of the ground = death line

PIPE_W       = 60                # px, pipe width. Wider = longer time inside the gap = harder.
GAP_START    = 168               # px, vertical gap at score 0. Bigger = easier.
GAP_MIN      = 122               # px, gap floor reached late in a run (never below ~4.3x bird height).
GAP_SHRINK   = 1.5               # px removed from the gap per pipe passed -> difficulty curve
SPEED_START  = 140.0             # px/s pipe scroll speed at score 0. Higher = less reaction time.
SPEED_MAX    = 215.0             # px/s cap.
SPEED_RAMP   = 1.6               # px/s added per pipe passed
PIPE_SPACING = 215               # px between consecutive pipes (spawned by DISTANCE, not timer,
                                 #   so spacing stays constant when speed ramps or a frame hitches)
GAP_MARGIN   = 70                # px, keep gaps at least this far from the top and the ground
GAP_JUMP_MAX = 190               # px, max vertical shift of gap centre between consecutive pipes
                                 #   (keeps every pipe pair physically reachable)
NEAR_MISS    = 9                 # px, passing within this of a pipe lip counts as a "close call"
MILESTONES   = (10, 25, 50, 100) # scores that fire the LEVEL fanfare and raise music intensity


# =====================================================================
# 1. PLATFORM -- display, input, lifecycle
# =====================================================================
APP = {}        # all app-level (non-game) state lives in this one dict


def is_android():
    # Pydroid 3 exposes the Android environment; CPython-on-Android has getandroidapilevel
    return ("ANDROID_ROOT" in os.environ or "ANDROID_ARGUMENT" in os.environ
            or hasattr(sys, "getandroidapilevel"))


def open_display():
    """Prefer pygame.SCALED: draw at BASE_W x BASE_H, SDL upscales on the GPU with
    letterboxing, and mouse coordinates arrive already in logical space.
    Fallback: native-size window + our own CPU scaling of a logical canvas."""
    fs = pygame.FULLSCREEN if is_android() else 0
    try:
        screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.SCALED | fs)
        return screen, True
    except (pygame.error, AttributeError):
        size = (0, 0) if is_android() else (BASE_W, BASE_H)
        return pygame.display.set_mode(size, fs), False


def view_transform():
    """Scale k and offsets (ox, oy) of the logical canvas inside the physical window."""
    try:
        ww, wh = pygame.display.get_window_size()
    except (AttributeError, pygame.error):
        ww, wh = APP["screen"].get_size()
    k = min(ww / BASE_W, wh / BASE_H)
    return k, (ww - BASE_W * k) / 2.0, (wh - BASE_H * k) / 2.0


def phys_to_logical(px, py):
    k, ox, oy = view_transform()
    return (px - ox) / k, (py - oy) / k


def finger_to_logical(e):
    # FINGER* events carry normalized (0..1) window coords, never logical ones
    try:
        ww, wh = pygame.display.get_window_size()
    except (AttributeError, pygame.error):
        ww, wh = APP["screen"].get_size()
    return phys_to_logical(e.x * ww, e.y * wh)


DOWN_DEBOUNCE_MS = 80       # a 2nd 'down' this soon and this close = the same touch reported twice
DOWN_DEBOUNCE_PX = 30

# lifecycle events differ between pygame/SDL versions -> resolve with getattr
_BG_EVENTS = {getattr(pygame, n) for n in ("APP_WILLENTERBACKGROUND", "APP_DIDENTERBACKGROUND",
                                            "WINDOWFOCUSLOST", "WINDOWMINIMIZED") if hasattr(pygame, n)}
_FG_EVENTS = {getattr(pygame, n) for n in ("APP_DIDENTERFOREGROUND", "WINDOWFOCUSGAINED",
                                            "WINDOWRESTORED") if hasattr(pygame, n)}
_BACK_KEYS = {pygame.K_ESCAPE, getattr(pygame, "K_AC_BACK", -999)}


def collect_input():
    """Drain the SDL queue into one normalized frame of input:
         ptr  : [{'type': 'down'|'move'|'up', 'x', 'y'}]  in logical coords
         keys : [pygame KEYDOWN events] (non-back keys)
         back, quit : bool;  life : 'bg' | 'fg' | None
    Android reports one touch as BOTH a FINGER* event and a synthesized MOUSE* event.
    Policy: per frame, use mouse events if any arrived (they are logical-mapped under
    SCALED and exist on desktop too), else finger events; then debounce 'down's so a
    twin arriving one frame later is dropped."""
    mouse, finger, keys = [], [], []
    back = quit_ = False
    life = None
    for e in pygame.event.get():
        t = e.type
        if t == pygame.QUIT:
            quit_ = True
        elif t == pygame.KEYDOWN:
            if e.key in _BACK_KEYS:
                back = True
            else:
                keys.append(e)
        elif t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and getattr(e, "button", 1) == 1:
            x, y = e.pos if APP["scaled"] else phys_to_logical(*e.pos)
            mouse.append({"type": "down" if t == pygame.MOUSEBUTTONDOWN else "up", "x": x, "y": y})
        elif t == pygame.MOUSEMOTION and e.buttons and e.buttons[0]:
            x, y = e.pos if APP["scaled"] else phys_to_logical(*e.pos)
            mouse.append({"type": "move", "x": x, "y": y})
        elif t in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
            x, y = finger_to_logical(e)
            kind = {pygame.FINGERDOWN: "down", pygame.FINGERUP: "up"}.get(t, "move")
            finger.append({"type": kind, "x": x, "y": y})
        elif t in _BG_EVENTS:
            life = "bg"
        elif t in _FG_EVENTS:
            life = "fg"
    ptr = mouse if mouse else finger
    out = []
    now = pygame.time.get_ticks()
    for ev in ptr:
        if ev["type"] == "down":
            lx, ly, lt = APP["last_down"]
            if now - lt < DOWN_DEBOUNCE_MS and abs(ev["x"] - lx) + abs(ev["y"] - ly) < DOWN_DEBOUNCE_PX:
                continue
            APP["last_down"] = (ev["x"], ev["y"], now)
        out.append(ev)
    return {"ptr": out, "keys": keys, "back": back, "quit": quit_, "life": life}


def present():
    """Flip the frame. In the CPU fallback path, scale the logical canvas to the window."""
    if not APP["scaled"]:
        scr = APP["screen"]
        k, ox, oy = view_transform()
        scr.fill(BLACK)
        scr.blit(pygame.transform.scale(APP["canvas"], (int(BASE_W * k), int(BASE_H * k))), (int(ox), int(oy)))
    pygame.display.flip()


# =====================================================================
# 2. AUDIO ENGINE -- synthesized SFX + procedural adaptive music
# Everything is generated into signed 16-bit PCM arrays (array('h')) and wrapped
# with pygame.mixer.Sound(buffer=...). Pure Python, no numpy, no files.
# =====================================================================
AUDIO = {"ok": False, "sr": SR, "ch": 1, "sfx": {}, "notes": {}, "song": None,
         "song_cache": {}, "step": 0, "acc": 0.0, "intensity": 0, "voices": {}, "paused": False}

VOICE_CH  = {"bass": 0, "arp": 1, "lead": 2, "drum": 3, "hat": 4}   # reserved mixer channels
VOICE_MIX = {"bass": 0.55, "arp": 0.26, "lead": 0.42, "drum": 0.70, "hat": 0.22}


def audio_init():
    """Called after pygame.init(). Reads back what the device ACTUALLY opened: Android
    often forces stereo and/or 44.1/48 kHz regardless of pre_init, and synthesizing
    at the wrong rate would shift every pitch."""
    try:
        info = pygame.mixer.get_init()
    except pygame.error:
        info = None
    if not info:
        return False
    freq, size, ch = info
    if size != -16:                       # we only emit signed 16-bit PCM
        return False
    AUDIO.update(ok=True, sr=freq, ch=ch)
    pygame.mixer.set_num_channels(16)
    pygame.mixer.set_reserved(len(VOICE_CH))     # music voices can't be stolen by SFX
    AUDIO["voices"] = {v: pygame.mixer.Channel(i) for v, i in VOICE_CH.items()}
    return True


def midi_hz(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def synth(dur, f0, f1=None, wave="square", vol=0.4, attack=0.004, release=0.03,
          decay=0.0, duty=0.5, vib_hz=0.0, vib_depth=0.0):
    """One voice -> array('h').
       f0 -> f1    linear pitch glide (sweeps, zaps, kicks)
       wave        square (duty sets timbre: .5 hollow, .25 nasal, .125 thin), tri, saw, sine,
                   noise (sample-and-hold at rate f: high f = hiss, low f = rumble)
       envelope    linear attack, exponential decay (per second), linear release tail."""
    sr = AUDIO["sr"]
    n = max(1, int(sr * dur))
    out = array("h", bytes(2 * n))
    f1 = f0 if f1 is None else f1
    a_n = max(1, int(attack * sr))
    r_n = max(1, int(release * sr))
    amp = vol * 32767.0
    two_pi = 2.0 * math.pi
    rnd = random.Random(7).random          # fixed seed -> identical noise every launch
    hold = rnd() * 2 - 1
    phase = 0.0
    dk = math.exp(-decay / sr) if decay else 1.0   # per-sample decay factor
    env_d = 1.0
    for i in range(n):
        f = f0 + (f1 - f0) * (i / n)
        if vib_depth:
            f *= 1.0 + vib_depth * math.sin(two_pi * vib_hz * i / sr)
        phase += f / sr
        if phase >= 1.0:
            phase -= int(phase)
            if wave == "noise":
                hold = rnd() * 2 - 1
        if wave == "square":
            s = 1.0 if phase < duty else -1.0
        elif wave == "tri":
            s = 4.0 * abs(phase - 0.5) - 1.0
        elif wave == "saw":
            s = 2.0 * phase - 1.0
        elif wave == "sine":
            s = math.sin(two_pi * phase)
        else:
            s = hold
        e = env_d
        env_d *= dk
        if i < a_n:
            e *= i / a_n
        if i > n - r_n:
            e *= (n - i) / r_n
        out[i] = int(s * e * amp)
    return out


def cat(*parts):
    """Concatenate buffers end to end (multi-note jingles)."""
    out = array("h")
    for p in parts:
        out.extend(p)
    return out


def mix(*parts):
    """Sum buffers sample-wise with clipping (layered sounds: noise + tone)."""
    n = max(len(p) for p in parts)
    acc = [0] * n
    for p in parts:
        for i, v in enumerate(p):
            acc[i] += v
    return array("h", (max(-32767, min(32767, v)) for v in acc))


def rest(dur):
    return array("h", bytes(2 * max(1, int(AUDIO["sr"] * dur))))


def to_sound(buf):
    """Mono PCM -> pygame Sound in the mixer's channel layout (interleave copies)."""
    ch = AUDIO["ch"]
    if ch > 1:
        st = array("h", bytes(2 * len(buf) * ch))
        for c in range(ch):
            st[c::ch] = buf
        buf = st
    return pygame.mixer.Sound(buffer=buf.tobytes())


def build_sfx(progress):
    """The standard SFX vocabulary every game should have. Game-specific sounds are
    added the same way (see GAME_SFX in section 6). Pitch ladders ('coin0'..'coin7')
    make chains audible: each successive catch sounds a semitone higher."""
    H = midi_hz
    S = {
        "tap":      synth(0.045, 1100, 800, "square", 0.22, decay=40, duty=0.25),
        "back":     synth(0.06, 520, 300, "square", 0.22, decay=30, duty=0.25),
        "tick":     synth(0.03, 1600, None, "square", 0.15, decay=60, duty=0.125),
        "start":    cat(synth(.07, H(72), wave="square", duty=.25, vol=.3), synth(.07, H(76), wave="square", duty=.25, vol=.3),
                        synth(.16, H(79), wave="square", duty=.25, vol=.3, decay=6)),
        "power":    synth(0.38, 300, 1300, "square", 0.28, duty=0.25, vib_hz=18, vib_depth=0.04),
        "hurt":     mix(synth(0.25, 4000, 600, "noise", 0.35, decay=12), synth(0.25, 420, 110, "square", 0.25, decay=8)),
        "explode":  synth(0.9, 2500, 120, "noise", 0.55, decay=4.5, release=0.2),
        "jump":     synth(0.12, 320, 760, "square", 0.25, decay=10, duty=0.5),
        "level":    cat(*[synth(.06, H(m), wave="square", duty=.125, vol=.28) for m in (72, 76, 79, 84)]),
        "gameover": cat(synth(.18, H(67), wave="tri", vol=.45), synth(.18, H(63), wave="tri", vol=.45),
                        synth(.5, H(60), H(58), "tri", .45, decay=2.5, release=.15)),
        "record":   cat(*[synth(.08, H(m), wave="square", duty=.25, vol=.3) for m in (72, 76, 79, 84, 79, 84)],
                        synth(.45, H(88), wave="square", duty=.25, vol=.3, vib_hz=7, vib_depth=.02, decay=2)),
        "achieve":  cat(*[synth(.05, H(m), wave="sine", vol=.35) for m in (84, 88, 91, 96)], synth(.3, H(100), wave="sine", vol=.3, decay=5)),
        "countdown": synth(0.09, H(76), None, "square", 0.25, decay=14, duty=0.25),
        "go":       synth(0.25, H(84), None, "square", 0.28, decay=6, duty=0.25),
    }
    for k in range(8):   # rising pitch ladder for combos / chains
        base = 76 + k
        S["coin%d" % k] = cat(synth(.045, H(base), wave="square", duty=.25, vol=.25),
                              synth(.11, H(base + 7), wave="square", duty=.25, vol=.25, decay=10))
    progress(0.3)
    for name, fn in GAME_SFX.items():        # game-specific additions (section 6)
        S[name] = fn()
    AUDIO["sfx"] = {k: to_sound(v) for k, v in S.items()}


def sfx(name, vol=1.0):
    """Fire-and-forget SFX on any free unreserved channel."""
    if not AUDIO["ok"] or AUDIO["paused"]:
        return
    snd = AUDIO["sfx"].get(name)
    if snd is None:
        return
    level = vol * APP["settings"]["sfx_vol"]
    if level <= 0:
        return
    ch = snd.play()
    if ch is not None:
        ch.set_volume(min(1.0, level))


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
    I = AUDIO["intensity"]
    step_dur = 60.0 / (song["bpm"] * (1.08 if I >= 3 else 1.0)) / 4.0
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
            if m is not None and I >= gate:
                V[voice].play(instrument(voice, m))
                V[voice].set_volume(VOICE_MIX[voice] * vol)
        for d in song["drums"][s]:
            if isinstance(d, tuple):                 # hats: 8ths at I>=2, 16ths at I>=3
                use = d[1] if I >= 3 else (d[0] if I >= 2 else None)
                if use:
                    V["hat"].play(instrument("hat", 0))
                    V["hat"].set_volume(VOICE_MIX["hat"] * vol)
            elif I >= 1:
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


# =====================================================================
# 3. PERSISTENCE -- SQLite
# Why SQLite and not a JSON/text file: writes are atomic (Android may kill the
# process at any moment; a half-written JSON file = lost scores), ORDER BY/LIMIT
# give the leaderboard for free, and the schema can be migrated with user_version.
# =====================================================================
SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS scores(
    id INTEGER PRIMARY KEY, initials TEXT NOT NULL, score INTEGER NOT NULL,
    created REAL NOT NULL, extra TEXT);
CREATE INDEX IF NOT EXISTS scores_by_score ON scores(score DESC, created ASC);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS achievements(id TEXT PRIMARY KEY, unlocked REAL NOT NULL);
"""
DEFAULT_SETTINGS = {"music_vol": 0.6, "sfx_vol": 0.8, "shake": True}


def db_path():
    """Home dir first: in Pydroid 3 `~` is the app's private, persistent storage,
    whereas a script's own folder can be a temporary copy (unsaved editor buffer).
    PYDROID_GAME_DB overrides (used by --selftest to keep real scores untouched)."""
    if os.environ.get("PYDROID_GAME_DB"):
        return os.environ["PYDROID_GAME_DB"]
    for d in (os.path.join(os.path.expanduser("~"), ".pydroid_games"), os.getcwd()):
        try:
            os.makedirs(d, exist_ok=True)
            if os.access(d, os.W_OK):
                return os.path.join(d, GAME_ID + ".sqlite3")
        except OSError:
            pass
    return ":memory:"       # nothing writable: same code path, session-only data


def db_open():
    try:
        con = sqlite3.connect(db_path())
        con.execute("SELECT 1")
    except sqlite3.Error:
        con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    ver = con.execute("PRAGMA user_version").fetchone()[0]
    # future migrations go here:  if ver < 2: con.execute("ALTER TABLE ..."); ...
    if ver < SCHEMA_VERSION:
        con.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
    con.commit()
    return con


def kv_get(key, default):
    row = APP["con"].execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    try:
        val = json.loads(row[0])
    except ValueError:
        return default
    if isinstance(default, dict):            # merge so newly added keys get defaults
        merged = dict(default)
        merged.update(val)
        return merged
    return val


def kv_set(key, value):
    APP["con"].execute("INSERT OR REPLACE INTO kv(key, value) VALUES(?, ?)", (key, json.dumps(value)))
    APP["con"].commit()


def db_top(n=TOP_N):
    return APP["con"].execute("SELECT id, initials, score, created FROM scores "
                              "ORDER BY score DESC, created ASC LIMIT ?", (n,)).fetchall()


def db_qualifies(score):
    if score <= 0:
        return False
    top = db_top()
    return len(top) < TOP_N or score > top[-1][2]


def db_add_score(initials, score, extra=None):
    cur = APP["con"].execute("INSERT INTO scores(initials, score, created, extra) VALUES(?,?,?,?)",
                             (initials, int(score), time.time(), json.dumps(extra or {})))
    APP["con"].commit()
    return cur.lastrowid


def db_rank(score_id):
    ids = [r[0] for r in db_top(1000)]
    return ids.index(score_id) + 1 if score_id in ids else None


def db_unlocked():
    return {r[0]: r[1] for r in APP["con"].execute("SELECT id, unlocked FROM achievements")}


def db_unlock(aid):
    APP["con"].execute("INSERT OR IGNORE INTO achievements(id, unlocked) VALUES(?, ?)", (aid, time.time()))
    APP["con"].commit()


def db_reset_scores():
    APP["con"].execute("DELETE FROM scores")
    APP["con"].commit()


# =====================================================================
# 4. UI KIT
# =====================================================================
_FONTS, _TXT = {}, {}


def font(size):
    f = _FONTS.get(size)
    if f is None:
        f = _FONTS[size] = pygame.font.SysFont(None, size)   # None = bundled font, always exists
    return f


def text(surf, s, size, x, y, color=WHITE, anchor="center", outline=BLACK):
    """Outlined text, rendered once per (string, size, colour) and cached:
    font.render is the most expensive thing a typical UI does per frame."""
    key = (s, size, color, outline)
    img = _TXT.get(key)
    if img is None:
        if len(_TXT) > 400:
            _TXT.clear()
        fg = font(size).render(s, True, color)
        if outline is None:
            img = fg
        else:
            bg = font(size).render(s, True, outline)
            img = pygame.Surface((fg.get_width() + 4, fg.get_height() + 4), pygame.SRCALPHA)
            for ox in (0, 2, 4):
                for oy in (0, 2, 4):
                    if (ox, oy) != (2, 2):
                        img.blit(bg, (ox, oy))
            img.blit(fg, (2, 2))
        _TXT[key] = img
    r = img.get_rect()
    setattr(r, anchor, (int(x), int(y)))
    surf.blit(img, r)
    return r


def button(x, y, w, h, label, action, style="primary"):
    """A button is plain data: rect + label + action string. Screens build their
    button list every frame; the same list drives both hit-testing and drawing."""
    return {"rect": pygame.Rect(int(x), int(y), int(w), int(h)), "label": label, "action": action, "style": style}


def vstack(items, top, w=230, h=54, gap=12):
    """Centred column of buttons. 54 logical px ~ 9 mm on a typical phone: comfortably tappable."""
    x = (BASE_W - w) // 2
    return [button(x, top + i * (h + gap), w, h, it[0], it[1], it[2] if len(it) > 2 else "primary")
            for i, it in enumerate(items)]


def draw_buttons(surf, btns):
    for b in btns:
        r = b["rect"].copy()
        pressed = APP["pressed"] is not None and APP["pressed"]["action"] == b["action"]
        if pressed:
            r.move_ip(0, 3)
        fill = {"primary": (60, 80, 170), "ghost": UI_PANEL, "danger": (150, 45, 55), "accent": (170, 120, 20)}[b["style"]]
        if pressed:
            fill = tuple(int(c * 0.75) for c in fill)
        if not pressed:
            pygame.draw.rect(surf, BLACK, r.move(0, 4), border_radius=12)       # drop shadow
        pygame.draw.rect(surf, fill, r, border_radius=12)
        pygame.draw.rect(surf, UI_EDGE, r, 2, border_radius=12)
        size = 34 if r.h >= 50 else 28
        text(surf, b["label"], size, r.centerx, r.centery)


def handle_buttons(btns, ev):
    """Fire on RELEASE inside the pressed button: lets a finger slide off to cancel,
    which is what mobile users expect from menus."""
    if ev["type"] == "down":
        for b in btns:
            if b["rect"].collidepoint(ev["x"], ev["y"]):
                APP["pressed"] = b
                return None
    elif ev["type"] == "up":
        p, APP["pressed"] = APP["pressed"], None
        if p is not None and p["rect"].collidepoint(ev["x"], ev["y"]):
            return p["action"]
    return None


def toast(title, sub="", color=UI_ACCENT):
    APP["toasts"].append({"title": title, "sub": sub, "color": color, "t": 0.0})


def burst(x, y, color, n=14, speed=160.0, life=0.6, size=3):
    for _ in range(n):
        a = random.uniform(0, 2 * math.pi)
        v = random.uniform(0.3, 1.0) * speed
        APP["particles"].append({"x": x, "y": y, "vx": math.cos(a) * v, "vy": math.sin(a) * v - 60,
                                 "t": 0.0, "life": life * random.uniform(0.7, 1.2), "c": color, "s": size})


def popup(s, x, y, color=WHITE, size=30):
    APP["popups"].append({"s": s, "x": x, "y": y, "t": 0.0, "c": color, "size": size})


def shake(amount):
    if APP["settings"]["shake"]:
        APP["shake"] = max(APP["shake"], amount)


def update_fx(dt):
    keep = []
    for p in APP["particles"]:
        p["t"] += dt
        if p["t"] < p["life"]:
            p["vy"] += 420 * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            keep.append(p)
    APP["particles"] = keep                      # rebinding frees dead particles immediately
    for p in APP["popups"]:
        p["t"] += dt
        p["y"] -= 40 * dt
    APP["popups"] = [p for p in APP["popups"] if p["t"] < 0.9]
    if APP["toasts"] and APP["mode"] not in TOAST_HOLD:
        APP["toasts"][0]["t"] += dt              # one at a time, queued
        if APP["toasts"][0]["t"] > 2.6:
            APP["toasts"].pop(0)
    APP["shake"] = max(0.0, APP["shake"] - 40 * dt)


def draw_fx(surf):
    for p in APP["particles"]:
        k = 1.0 - p["t"] / p["life"]
        pygame.draw.circle(surf, p["c"], (int(p["x"]), int(p["y"])), max(1, int(p["s"] * k + 0.5)))
    for p in APP["popups"]:
        text(surf, p["s"], p["size"], p["x"], p["y"], p["c"])


TOAST_HOLD = ("scores", "trophies", "settings")    # list screens: queue toasts until we leave


def draw_toast(surf):
    if not APP["toasts"] or APP["mode"] in TOAST_HOLD:
        return
    t = APP["toasts"][0]
    slide = min(1.0, t["t"] / 0.25, (2.6 - t["t"]) / 0.25)        # ease in / out
    r = pygame.Rect(20, int(-62 + 70 * slide), BASE_W - 40, 54)
    pygame.draw.rect(surf, UI_PANEL, r, border_radius=12)
    pygame.draw.rect(surf, t["color"], r, 2, border_radius=12)
    draw_trophy(surf, r.x + 28, r.centery, t["color"])
    text(surf, t["title"], 26, r.x + 54, r.y + 17, t["color"], "midleft")
    if t["sub"]:
        text(surf, t["sub"], 20, r.x + 54, r.y + 38, WHITE, "midleft")


def draw_trophy(surf, cx, cy, color):
    pygame.draw.polygon(surf, color, [(cx - 11, cy - 12), (cx + 11, cy - 12), (cx + 7, cy + 2), (cx - 7, cy + 2)])
    pygame.draw.rect(surf, color, (cx - 2, cy + 2, 4, 6))
    pygame.draw.rect(surf, color, (cx - 8, cy + 8, 16, 4))


def draw_panel(surf, rect):
    pygame.draw.rect(surf, UI_PANEL, rect, border_radius=14)
    pygame.draw.rect(surf, UI_EDGE, rect, 2, border_radius=14)


def dim(surf, alpha=150):
    d = pygame.Surface((BASE_W, BASE_H), pygame.SRCALPHA)
    d.fill((0, 0, 0, alpha))
    surf.blit(d, (0, 0))


# =====================================================================
# 5. META SCREENS -- everything around the game itself
# modes: title, play, pause, settings, initials, scores, trophies, over
# =====================================================================
INIT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
PAUSE_BTN = pygame.Rect(BASE_W - 54, 8, 46, 46)


def set_mode(mode):
    APP["prev_mode"], APP["mode"], APP["mode_t"] = APP["mode"], mode, 0.0
    APP["pressed"] = None


def buttons_for(mode):
    cx = BASE_W // 2
    if mode == "title":
        skin = SKINS[APP["settings"].get("skin", 0)]
        return vstack([("PLAY", "play", "accent"), ("HIGH SCORES", "scores"), ("TROPHIES", "trophies"),
                       ("SETTINGS", "settings"), ("Skin: %s" % skin[0], "skin", "ghost")], 300)
    if mode == "pause":
        return vstack([("RESUME", "resume", "accent"), ("RESTART", "restart"), ("SETTINGS", "settings"),
                       ("QUIT TO MENU", "menu", "danger")], 230)
    if mode == "settings":
        s = APP["settings"]
        reset_lbl = "TAP AGAIN TO ERASE" if APP["confirm_reset"] > 0 else "Reset high scores"
        return vstack([("Music: %d%%" % round(s["music_vol"] * 100), "music"),
                       ("Sound FX: %d%%" % round(s["sfx_vol"] * 100), "sfxvol"),
                       ("Screen shake: %s" % ("ON" if s["shake"] else "OFF"), "shake"),
                       (reset_lbl, "reset", "danger"), ("BACK", "back", "ghost")], 170)
    if mode == "initials":
        b = []
        for i in range(3):
            x = cx - 100 + i * 100 - 36
            b.append(button(x, 228, 72, 56, "^", "up%d" % i, "ghost"))
            b.append(button(x, 384, 72, 56, "v", "dn%d" % i, "ghost"))
        b.append(button(cx - 90, 480, 180, 58, "OK", "ok", "accent"))
        return b
    if mode == "scores":
        if APP["scores_from_run"]:
            return [button(24, BASE_H - 80, 150, 56, "RETRY", "retry", "accent"),
                    button(BASE_W - 174, BASE_H - 80, 150, 56, "MENU", "menu", "ghost")]
        return [button(cx - 90, BASE_H - 80, 180, 56, "BACK", "back", "ghost")]
    if mode == "trophies":
        return [button(cx - 90, BASE_H - 80, 180, 56, "BACK", "back", "ghost")]
    if mode == "over":
        return [button(24, BASE_H - 150, 150, 56, "RETRY", "retry", "accent"),
                button(BASE_W - 174, BASE_H - 150, 150, 56, "MENU", "menu", "ghost"),
                button(cx - 90, BASE_H - 80, 180, 52, "HIGH SCORES", "scores", "ghost")]
    return []


def do_action(a):
    """Every button / key shortcut ends up here: the complete navigation graph."""
    mode = APP["mode"]
    sfx("back" if a in ("back", "menu") else "tap")
    s = APP["settings"]
    if a in ("play", "retry", "restart"):
        start_run()
    elif a == "scores":
        APP["scores_from_run"] = mode == "over"
        set_mode("scores")
    elif a == "trophies":
        set_mode("trophies")
    elif a == "settings":
        APP["settings_return"] = mode
        set_mode("settings")
    elif a == "skin":
        stars = APP["life"].get("total", 0)
        unlocked = [i for i, sk in enumerate(SKINS) if stars >= sk[1]]
        cur = s.get("skin", 0)
        s["skin"] = unlocked[(unlocked.index(cur) + 1) % len(unlocked)] if cur in unlocked else 0
        nxt = next((sk for sk in SKINS if stars < sk[1]), None)
        if nxt and s["skin"] == unlocked[-1]:
            toast("Next skin: %s" % nxt[0], "%d more %s" % (nxt[1] - stars, CURRENCY[1]), UI_DIM)
        kv_set("settings", s)
    elif a == "resume":
        APP["resume_t"] = 1.5                     # 3-2-1 grace period before play continues
        set_intensity(APP["paused_intensity"])
        set_mode("play")
    elif a == "menu":
        APP["gs"] = None
        music_play("title")
        set_intensity(2)
        set_mode("title")
    elif a == "back":
        if mode == "settings":
            set_mode(APP.get("settings_return") or "title")
        elif mode == "scores" and APP["scores_from_run"]:
            do_action("menu")
        else:
            set_mode("title")
    elif a in ("music", "sfxvol"):
        k = "music_vol" if a == "music" else "sfx_vol"
        s[k] = round((s[k] + 0.2) % 1.2, 1)       # 0 -> 20 -> ... -> 100 -> 0 %
        kv_set("settings", s)
        sfx("tick")
    elif a == "shake":
        s["shake"] = not s["shake"]
        kv_set("settings", s)
        shake(8)
    elif a == "reset":
        if APP["confirm_reset"] > 0:
            db_reset_scores()
            APP["confirm_reset"] = 0.0
            toast("High scores erased", "", UI_BAD)
        else:
            APP["confirm_reset"] = 2.5             # second tap within 2.5 s confirms
    elif a[:2] in ("up", "dn"):
        i = int(a[2])
        APP["init_cursor"] = i
        c = APP["initials"][i]
        step = 1 if a[:2] == "up" else -1
        APP["initials"][i] = INIT_CHARS[(INIT_CHARS.index(c) + step) % len(INIT_CHARS)]
        sfx("tick")
    elif a == "ok":
        submit_initials()


def on_back():
    """Android back / ESC: in play it PAUSES (never quits mid-run); in menus it goes back."""
    mode = APP["mode"]
    if mode == "play" and APP["gs"] and not APP["gs"]["over"]:
        enter_pause()
    elif mode == "pause":
        do_action("resume")
    elif mode in ("settings", "scores", "trophies"):
        do_action("back")
    elif mode in ("over", "initials"):
        if mode == "initials":
            submit_initials()
        else:
            do_action("menu")
    elif mode == "title":
        APP["running"] = False


def enter_pause():
    if APP["mode"] != "play":
        return
    APP["paused_intensity"] = AUDIO["intensity"]
    set_intensity(0)                              # music drops to ambient layer while paused
    sfx("back")
    set_mode("pause")


def handle_initials_key(e):
    i = APP["init_cursor"]
    ch = (e.unicode or "").upper()
    if ch and ch in INIT_CHARS:
        APP["initials"][i] = ch
        APP["init_cursor"] = min(2, i + 1)
        sfx("tick")
    elif e.key == pygame.K_BACKSPACE or e.key == pygame.K_LEFT:
        APP["init_cursor"] = max(0, i - 1)
    elif e.key == pygame.K_RIGHT:
        APP["init_cursor"] = min(2, i + 1)
    elif e.key == pygame.K_UP:
        do_action("up%d" % i)
    elif e.key == pygame.K_DOWN:
        do_action("dn%d" % i)
    elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        do_action("ok")


def submit_initials():
    ini = "".join(APP["initials"])
    r = APP["run"]
    sid = db_add_score(ini, r["score"], {k: v for k, v in r.items() if isinstance(v, (int, float))})
    APP["life"]["last_initials"] = ini            # pre-filled next time: fewer taps
    kv_set("life", APP["life"])
    APP["highlight_id"] = sid
    APP["last_rank"] = db_rank(sid)
    if APP["last_rank"] == 1:
        sfx("record")
        burst(BASE_W / 2, 140, UI_ACCENT, 40, 260, 1.2, 4)
    APP["scores_from_run"] = True
    set_mode("scores")


# ---- screen drawing ------------------------------------------------------
def draw_title(c):
    t = APP["t"]
    text(c, GAME_TITLE, 64, BASE_W / 2, 110 + math.sin(t * 2.2) * 6, UI_ACCENT)
    best = APP["life"].get("best_score", 0)
    text(c, "BEST  %d" % best, 30, BASE_W / 2, 170)
    st = APP["life"].get("streak", 0)
    if st >= 2:
        text(c, "Day %d streak - keep it going!" % st, 24, BASE_W / 2, 204, UI_GOOD)
    got, total = len(APP["unlocked"]), len(ACHIEVEMENTS)
    text(c, "Trophies %d / %d" % (got, total), 24, BASE_W / 2, 232, UI_DIM)
    if int(t * 2) % 2 == 0:
        text(c, "tap PLAY", 22, BASE_W / 2, 270, UI_DIM)


def draw_pause(c):
    dim(c)
    text(c, "PAUSED", 60, BASE_W / 2, 150, UI_ACCENT)
    if APP["gs"]:
        text(c, "score %d" % APP["gs"]["score"], 30, BASE_W / 2, 196)


def draw_settings(c):
    dim(c, 200)
    text(c, "SETTINGS", 52, BASE_W / 2, 100, UI_ACCENT)
    text(c, "saved automatically", 22, BASE_W / 2, 136, UI_DIM)


def draw_initials(c):
    dim(c, 190)
    r = APP["run"]
    text(c, "NEW HIGH SCORE!" if APP["is_record"] else "TOP %d!" % TOP_N, 48, BASE_W / 2, 92, UI_ACCENT)
    text(c, "%d" % r["score"], 60, BASE_W / 2, 150)
    text(c, "ENTER YOUR INITIALS", 26, BASE_W / 2, 200, UI_DIM)
    for i in range(3):
        x = BASE_W / 2 - 100 + i * 100
        box = pygame.Rect(x - 36, 294, 72, 80)
        sel = i == APP["init_cursor"]
        pygame.draw.rect(c, UI_PANEL, box, border_radius=10)
        pygame.draw.rect(c, UI_ACCENT if sel else UI_EDGE, box, 3 if sel else 2, border_radius=10)
        blink = sel and int(APP["t"] * 3) % 2 == 0
        text(c, APP["initials"][i], 70, x, 336, UI_ACCENT if blink else WHITE)


def draw_scores(c):
    dim(c, 210)
    text(c, "HIGH SCORES", 50, BASE_W / 2, 52, UI_ACCENT)
    if APP["scores_from_run"] and APP.get("last_rank"):
        text(c, "you placed #%d" % APP["last_rank"], 26, BASE_W / 2, 88, UI_GOOD)
    rows = db_top()
    y0 = 118
    for i, (sid, ini, sc, created) in enumerate(rows):
        y = y0 + i * 30
        hl = sid == APP["highlight_id"]
        col = UI_ACCENT if hl and int(APP["t"] * 4) % 2 == 0 else (WHITE if i < 3 else UI_DIM)
        if hl:
            pygame.draw.rect(c, (60, 60, 20), (20, y - 14, BASE_W - 40, 28), border_radius=6)
        day = datetime.date.fromtimestamp(created).strftime("%d/%m")
        text(c, "%2d." % (i + 1), 26, 52, y, col, "midright")
        text(c, ini, 28, 72, y, col, "midleft")
        text(c, str(sc), 28, 250, y, col, "midright")
        text(c, day, 22, BASE_W - 32, y, UI_DIM, "midright")
    if not rows:
        text(c, "no scores yet - go set one!", 26, BASE_W / 2, 200, UI_DIM)
    L = APP["life"]
    y = y0 + TOP_N * 30 + 18
    mins = int(L.get("play_time", 0) // 60)
    stats = [("games", L.get("games", 0)), ("time played", "%dh%02dm" % divmod(mins, 60)),
             (CURRENCY[1], L.get("total", 0)), (LIFE_BEST[1], L.get("best_" + LIFE_BEST[0], 0)),
             ("day streak", L.get("streak", 0))]
    for i, (k, v) in enumerate(stats):
        text(c, k, 22, 40, y + i * 22, UI_DIM, "midleft")
        text(c, str(v), 22, BASE_W - 40, y + i * 22, WHITE, "midright")


def draw_trophies(c):
    dim(c, 210)
    got = APP["unlocked"]
    text(c, "TROPHIES %d/%d" % (len(got), len(ACHIEVEMENTS)), 46, BASE_W / 2, 52, UI_ACCENT)
    for i, (aid, name, desc, _) in enumerate(ACHIEVEMENTS):
        y = 96 + i * 44
        on = aid in got
        draw_trophy(c, 36, y + 10, UI_ACCENT if on else (70, 70, 90))
        text(c, name, 28, 60, y, WHITE if on else UI_DIM, "midleft")
        text(c, desc if on else "??? " + desc, 20, 60, y + 22, UI_DIM, "midleft")


def draw_over(c):
    dim(c, 170)
    r = APP["run"]
    text(c, "GAME OVER", 58, BASE_W / 2, 90, UI_BAD)
    text(c, "%d" % r["score"], 80, BASE_W / 2, 170, UI_ACCENT if APP["is_record"] else WHITE)
    if APP["is_record"]:
        text(c, "NEW RECORD!", 34, BASE_W / 2, 222, UI_ACCENT)
    else:
        text(c, "best %d" % APP["life"].get("best_score", 0), 28, BASE_W / 2, 222, UI_DIM)
    y = 266
    for k in RUN_SUMMARY:
        text(c, "%s  %s" % (k[1], k[2](r)), 26, BASE_W / 2, y)
        y += 28
    for name in APP["run_unlocks"][:3]:
        draw_trophy(c, 70, y + 12, UI_ACCENT)
        text(c, name, 26, 92, y + 10, UI_ACCENT, "midleft")
        y += 30


# =====================================================================
# 6. GAME -- FLAPPY
# Contract with the infrastructure:
#   game_new(skin_index) -> gs dict with at least: score, over, stats{...}
#   game_input(gs, ev)    pointer events {'type','x','y'} (logical coords) during play
#   game_key(gs, e)       KEYDOWN during play (desktop testing)
#   game_update(gs, dt)   advance; call sfx()/burst()/popup()/shake()/set_intensity();
#                         set gs['over'] = True when the run ends
#   game_draw(surf, gs)   world layer (gets screen shake);  game_bg(surf, t) backdrop
#   game_hud(surf, gs)    score / lives / combo (no shake)
#   game_bot(gs)          -> pointer events; autopilot used by --selftest
#   ACHIEVEMENTS, CURRENCY, LIFE_BEST, SKINS, RUN_SUMMARY, GAME_SFX
#
# Game state machine (gs["phase"]), nested inside the app's "play" mode:
#   "ready" : bird hovers on a sine bob, ground scrolls, no pipes, no gravity.
#             The first tap flaps AND starts the run, so that tap is never wasted.
#   "play"  : gravity, pipe spawning (by distance), scoring, collision.
#   "dead"  : pipes freeze, bird tumbles to the ground; gs["over"] = True hands
#             control to the infrastructure -> slow-mo beat -> initials / GAME OVER
#             screen (score, best, run summary, RETRY). That screen is the
#             GAME_OVER state; RETRY / SPACE / ENTER restarts.
# =====================================================================
GAME_SFX = {   # extra sounds for this game: name -> zero-arg builder returning array('h')
    # flap: short high-passed "whoosh" (noise sweeping down) + a soft square chirp underneath
    "flap":  lambda: mix(synth(0.09, 5200, 1800, "noise", 0.16, decay=22),
                         synth(0.07, 520, 900, "square", 0.10, decay=30, duty=0.25)),
    # point: two-tone sine ding, a perfect fourth apart -> reads as "reward" without being shrill
    "point": lambda: cat(synth(0.05, midi_hz(83), None, "sine", 0.32),
                         synth(0.16, midi_hz(88), None, "sine", 0.32, decay=9)),
    # hit: low noise thump + falling square = blunt impact
    "hit":   lambda: mix(synth(0.18, 900, 120, "noise", 0.45, decay=16),
                         synth(0.16, 300, 70, "square", 0.30, decay=12)),
    # fall: long descending tri glide while the bird drops
    "fall":  lambda: synth(0.45, 900, 180, "tri", 0.22, decay=3, release=0.1),
}

# (id, name, description, predicate(run_stats, lifetime_stats)) -- checked every 0.5 s and at run end
ACHIEVEMENTS = [
    ("first",     "Liftoff",        "Pass your first pipe",          lambda r, L: r["pipes"] >= 1),
    ("score10",   "Frequent Flyer", "Score 10 in one run",           lambda r, L: r["score"] >= 10),
    ("score25",   "Sky Pilot",      "Score 25 in one run",           lambda r, L: r["score"] >= 25),
    ("score50",   "Ace",            "Score 50 in one run",           lambda r, L: r["score"] >= 50),
    ("score100",  "Legend",         "Score 100 in one run",          lambda r, L: r["score"] >= 100),
    ("close5",    "Feather Touch",  "5 close calls in one run",      lambda r, L: r["close"] >= 5),
    ("survive60", "Endurance",      "Stay airborne for 60 seconds",  lambda r, L: r["time"] >= 60),
    ("regular",   "Regular",        "Play 10 games",                 lambda r, L: L.get("games", 0) >= 10),
    ("streak3",   "Habit",          "Play 3 days in a row",          lambda r, L: L.get("streak", 0) >= 3),
    ("migrate",   "Migration",      "Pass 500 pipes in total",       lambda r, L: L.get("total", 0) + r["pipes"] >= 500),
]

# lifetime currency = pipes passed, summed over all runs -> every run, even a 2-pipe one,
# moves you toward the next bird skin.
CURRENCY  = ("pipes", "pipes passed")
# run stat whose all-time best is kept in L["best_close"] and shown on the scores screen
LIFE_BEST = ("close", "most close calls")

# (name, lifetime pipes needed, (body colour, wing colour)) -- spaced roughly geometrically
SKINS = [("Canary", 0,    ((255, 214, 64),  (240, 160, 40))),
         ("Robin",  50,   ((235, 90, 70),   (170, 50, 50))),
         ("Bluejay", 150, ((80, 160, 255),  (40, 90, 200))),
         ("Parrot", 400,  ((90, 220, 110),  (40, 150, 70))),
         ("Phoenix", 1000, ((255, 130, 40), (230, 50, 140)))]

# lines on the game-over screen: (key, label, formatter)
RUN_SUMMARY = [("close", "close calls", lambda r: r["close"]),
               ("flaps", "flaps", lambda r: r["flaps"]),
               ("time", "time", lambda r: "%ds" % r["time"])]

PIPE_C, PIPE_HI, PIPE_LO = (96, 196, 70), (160, 236, 120), (52, 128, 40)   # body, highlight, shadow
OUTLINE = (30, 40, 30)
LIP_H, LIP_OVER = 26, 4          # pipe lip height and how far it overhangs the body on each side
_BG = {"scroll": 0.0}            # pre-rendered layers + world scroll distance (px) for parallax


# ---- difficulty as pure functions of score (one place to read the curve) ----
def gap_for(score):
    return max(GAP_MIN, GAP_START - GAP_SHRINK * score)


def speed_for(score):
    return min(SPEED_MAX, SPEED_START + SPEED_RAMP * score)


def game_new(skin):
    return {"score": 0, "over": False, "phase": "ready", "t": 0.0,
            "y": BASE_H * 0.42, "vy": 0.0, "angle": 0.0, "wing_t": 0.0,
            "pipes": [], "last_gy": BASE_H * 0.42, "flash": 0.0, "skin": skin,
            "stats": {"pipes": 0, "close": 0, "flaps": 0, "time": 0.0}}


def flap(gs):
    """One tap. Velocity is SET, not added: a tap while falling fast lifts exactly
    as much as a tap while hovering, which is what makes touch timing learnable."""
    if gs["phase"] == "dead":
        return
    if gs["phase"] == "ready":
        gs["phase"] = "play"                      # first tap starts the run AND flaps
    gs["vy"] = -FLAP_V
    gs["wing_t"] = 0.0                            # restart the wing-beat animation
    gs["stats"]["flaps"] += 1
    sfx("flap", 0.8)
    burst(BIRD_X - 12, gs["y"] + 6, (245, 245, 255), 4, 70, 0.3, 2)   # little feather puff


def game_input(gs, ev):
    if ev["type"] == "down":                      # react on PRESS: release would add ~100 ms of lag
        flap(gs)


def game_key(gs, e):
    if e.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
        flap(gs)                                  # keyboard fallback for desktop testing


def bird_box(y):
    """Square hitbox, smaller than the drawn bird (forgiveness for the round sprite)."""
    return pygame.Rect(BIRD_X - HITBOX_HALF, int(y) - HITBOX_HALF, 2 * HITBOX_HALF, 2 * HITBOX_HALF)


def pipe_rects(p):
    """Geometry of one pipe pair, used for BOTH drawing and collision so what you
    see is exactly what kills you. The top body extends far above the screen so the
    bird can't sneak over the pipe by flying off the top edge."""
    x, top, bot = int(p["x"]), int(p["gy"] - p["gap"] / 2), int(p["gy"] + p["gap"] / 2)
    return {"top_body": pygame.Rect(x, top - 2000, PIPE_W, 2000 - LIP_H),
            "top_lip":  pygame.Rect(x - LIP_OVER, top - LIP_H, PIPE_W + 2 * LIP_OVER, LIP_H),
            "bot_lip":  pygame.Rect(x - LIP_OVER, bot, PIPE_W + 2 * LIP_OVER, LIP_H),
            "bot_body": pygame.Rect(x, bot + LIP_H, PIPE_W, max(0, GROUND_Y - bot - LIP_H))}


def spawn_pipe(gs, x):
    gap = gap_for(gs["score"])
    lo, hi = GAP_MARGIN + gap / 2, GROUND_Y - GAP_MARGIN - gap / 2
    # random gap centre, but never further than GAP_JUMP_MAX from the previous one
    gy = random.uniform(max(lo, gs["last_gy"] - GAP_JUMP_MAX), min(hi, gs["last_gy"] + GAP_JUMP_MAX))
    gs["last_gy"] = gy
    gs["pipes"].append({"x": float(x), "gy": gy, "gap": gap, "scored": False, "clear": 999.0})


def die(gs, why):
    gs["phase"] = "dead"
    gs["over"] = True                             # infra: slow-mo beat, then results screens
    gs["flash"] = 1.0
    gs["vy"] = min(gs["vy"], -120.0) if why == "pipe" else 0.0   # small bounce off a pipe
    sfx("hit")
    if why == "pipe":
        sfx("fall", 0.8)
    shake(10)
    burst(BIRD_X, gs["y"], SKINS[gs["skin"]][2][0], 22, 220, 0.7, 3)


def game_update(gs, dt):
    st = gs["stats"]
    gs["t"] += dt
    gs["wing_t"] += dt
    gs["flash"] = max(0.0, gs["flash"] - dt * 3)
    ph = gs["phase"]
    speed = speed_for(gs["score"])

    if ph == "ready":                             # hover: sine bob, world scrolls, no gravity
        gs["y"] = BASE_H * 0.42 + math.sin(gs["t"] * 5.0) * 8
        gs["angle"] = 0.0
        _BG["scroll"] += speed * dt
        return

    if ph == "dead":                              # tumble: heavier gravity so the fall reads in slow-mo
        gs["vy"] = min(MAX_FALL * 1.5, gs["vy"] + GRAVITY * 2.5 * dt)
        gs["y"] = min(GROUND_Y - HITBOX_HALF, gs["y"] + gs["vy"] * dt)
        gs["angle"] = max(-90.0, gs["angle"] - 400 * dt)
        return

    # ---- PLAY: semi-implicit Euler (velocity first, then position) ----
    st["time"] = gs["t"]
    gs["vy"] = min(MAX_FALL, gs["vy"] + GRAVITY * dt)
    gs["y"] += gs["vy"] * dt
    if gs["y"] < -30:                             # soft ceiling: the infinite top pipe does the policing
        gs["y"], gs["vy"] = -30.0, 0.0
    # nose follows velocity: up to +25 deg climbing, down to -80 deg diving
    gs["angle"] = max(-80.0, min(25.0, -gs["vy"] * 0.12))
    _BG["scroll"] += speed * dt

    # spawn by DISTANCE: next pipe appears once the last one has moved PIPE_SPACING px in
    if not gs["pipes"]:
        spawn_pipe(gs, BASE_W + 40)
    elif gs["pipes"][-1]["x"] <= BASE_W + 40 - PIPE_SPACING:
        spawn_pipe(gs, gs["pipes"][-1]["x"] + PIPE_SPACING)

    box = bird_box(gs["y"])
    for p in gs["pipes"]:
        p["x"] -= speed * dt
        if p["x"] - LIP_OVER < box.right and p["x"] + PIPE_W + LIP_OVER > box.left:
            # inside the pipe column: track tightest clearance for the "close call" stat
            top = p["gy"] - p["gap"] / 2
            bot = p["gy"] + p["gap"] / 2
            p["clear"] = min(p["clear"], box.top - top, bot - box.bottom)
        r = pipe_rects(p)
        if any(box.colliderect(rr) for rr in r.values()):
            die(gs, "pipe")
            return
        # score when the pipe's CENTRE line passes the bird's centre
        if not p["scored"] and p["x"] + PIPE_W / 2 < BIRD_X:
            p["scored"] = True
            gs["score"] += 1
            st["pipes"] += 1
            sfx("point")
            popup("+1", BIRD_X + 10, gs["y"] - 34, WHITE, 26)
            if p["clear"] <= NEAR_MISS:
                st["close"] += 1
                sfx("coin%d" % min(7, st["close"] - 1))   # rising pitch: close calls stack up
                popup("CLOSE!", BIRD_X + 40, gs["y"] - 60, UI_ACCENT, 28)
                burst(BIRD_X, gs["y"], UI_ACCENT, 10, 150)
            if gs["score"] in MILESTONES:
                sfx("level")
                popup("%d!" % gs["score"], BASE_W / 2, 230, UI_ACCENT, 56)
                burst(BASE_W / 2, 230, UI_ACCENT, 30, 240, 0.9, 3)
            # music gets denser as the run gets harder: 0-9 -> 1, 10-24 -> 2, 25+ -> 3
            set_intensity(1 + (gs["score"] >= MILESTONES[0]) + (gs["score"] >= MILESTONES[1]))
    # cull off-screen pipes by rebuilding the list (O(n), no mutation-while-iterating)
    gs["pipes"] = [p for p in gs["pipes"] if p["x"] + PIPE_W + LIP_OVER > 0]

    if box.bottom >= GROUND_Y:
        gs["y"] = GROUND_Y - HITBOX_HALF
        die(gs, "ground")


# ---- pre-rendered graphics (built once, blitted per frame) ----------------
def _build_layers():
    sky = pygame.Surface((BASE_W, BASE_H))
    for y in range(BASE_H):                       # vertical gradient: deep blue -> warm horizon
        k = y / BASE_H
        pygame.draw.line(sky, (int(70 + 120 * k), int(150 + 60 * k), int(225 + 10 * k)), (0, y), (BASE_W, y))
    _BG["sky"] = sky
    rng = random.Random(11)                       # seeded: same skyline every launch
    city = pygame.Surface((BASE_W, 160), pygame.SRCALPHA)
    x = 0
    while x < BASE_W:                             # buildings must tile seamlessly -> stop exactly at BASE_W
        w = min(rng.randint(22, 48), BASE_W - x)
        h = rng.randint(50, 140)
        pygame.draw.rect(city, (150, 196, 210), (x, 160 - h, w, h))
        for wy in range(160 - h + 8, 150, 14):    # little lit windows
            for wx in range(x + 5, x + w - 6, 10):
                if rng.random() < 0.55:
                    pygame.draw.rect(city, (190, 226, 236), (wx, wy, 4, 6))
        x += w
    _BG["city"] = city
    clouds = pygame.Surface((BASE_W, 90), pygame.SRCALPHA)
    for i in range(7):
        cx, cy, r = rng.randint(0, BASE_W), rng.randint(30, 60), rng.randint(18, 30)
        for dx in (-r, 0, r):                     # 3 overlapping circles = cartoon cloud;
            for off in (-BASE_W, 0, BASE_W):      # drawn at +-BASE_W too so the strip tiles
                pygame.draw.circle(clouds, (250, 252, 255), (cx + dx + off, cy + (0 if dx else -8)), r)
    _BG["clouds"] = clouds
    ground = pygame.Surface((BASE_W + 24, GROUND_H))   # 24 px wider: one stripe period of slack
    ground.fill((222, 206, 140))
    pygame.draw.rect(ground, (110, 190, 70), (0, 0, BASE_W + 24, 16))
    for sx in range(-24, BASE_W + 48, 24):        # diagonal stripes, period 24 px
        pygame.draw.polygon(ground, (130, 210, 80), [(sx, 0), (sx + 12, 0), (sx + 4, 16), (sx - 8, 16)])
    pygame.draw.line(ground, OUTLINE, (0, 0), (BASE_W + 24, 0), 3)
    pygame.draw.line(ground, (180, 160, 100), (0, 17), (BASE_W + 24, 17), 2)
    _BG["ground"] = ground


def _bird_frames(skin):
    """3 wing poses per skin (up / mid / down), drawn once with an outline so the
    bird reads clearly at phone size. Rotation happens per frame on these."""
    key = "bird%d" % skin
    if key in _BG:
        return _BG[key]
    body, wing = SKINS[skin][2]
    frames = []
    for wy in (-7, 0, 6):                         # wing vertical offset per pose
        s = pygame.Surface((48, 40), pygame.SRCALPHA)
        c = (24, 20)                              # body centre inside the sprite
        pygame.draw.ellipse(s, OUTLINE, (c[0] - 17, c[1] - 14, 34, 28))
        pygame.draw.ellipse(s, body, (c[0] - 15, c[1] - 12, 30, 24))
        pygame.draw.ellipse(s, (255, 245, 210), (c[0] - 9, c[1] + 1, 18, 9))      # belly
        pygame.draw.ellipse(s, OUTLINE, (c[0] - 17, c[1] - 5 + wy, 18, 12))
        pygame.draw.ellipse(s, wing, (c[0] - 16, c[1] - 4 + wy, 16, 10))          # wing
        pygame.draw.circle(s, OUTLINE, (c[0] + 7, c[1] - 5), 7)
        pygame.draw.circle(s, WHITE, (c[0] + 7, c[1] - 5), 6)                    # eye
        pygame.draw.circle(s, BLACK, (c[0] + 9, c[1] - 5), 3)                    # pupil
        pygame.draw.polygon(s, OUTLINE, [(c[0] + 11, c[1] - 1), (c[0] + 24, c[1] + 3), (c[0] + 11, c[1] + 8)])
        pygame.draw.polygon(s, (255, 120, 40), [(c[0] + 12, c[1]), (c[0] + 22, c[1] + 3), (c[0] + 12, c[1] + 6)])
        frames.append(s)
    _BG[key] = frames
    return frames


def draw_ground(surf):
    surf.blit(_BG["ground"], (-int(_BG["scroll"] % 24), GROUND_Y))


def game_bg(surf, t):
    """Sky + parallax clouds/city. Each layer scrolls at a fraction of world speed:
    far things move slower, which is the whole depth illusion."""
    if "sky" not in _BG:
        _build_layers()
    if APP.get("gs") is None:                     # title screen: keep the world drifting
        _BG["scroll"] = t * 60
    s = _BG["scroll"]
    surf.blit(_BG["sky"], (0, 0))
    for layer, k, y in (("clouds", 0.10, 70), ("city", 0.25, GROUND_Y - 160)):
        off = -int(s * k) % BASE_W                # wrap: blit twice, side by side
        surf.blit(_BG[layer], (off - BASE_W, y))
        surf.blit(_BG[layer], (off, y))
    draw_ground(surf)


def draw_pipe(surf, p):
    r = pipe_rects(p)
    for body in (r["top_body"], r["bot_body"]):
        if body.h <= 0:
            continue
        vis = body.clip(pygame.Rect(-10, -10, BASE_W + 20, BASE_H + 20))   # don't fill 2000 px offscreen
        pygame.draw.rect(surf, PIPE_C, vis)
        pygame.draw.rect(surf, PIPE_HI, (vis.x + 6, vis.y, 8, vis.h))        # specular stripe
        pygame.draw.rect(surf, PIPE_LO, (vis.right - 12, vis.y, 8, vis.h))   # shadow stripe
        pygame.draw.rect(surf, OUTLINE, vis, 3)
    for lip in (r["top_lip"], r["bot_lip"]):
        pygame.draw.rect(surf, PIPE_C, lip)
        pygame.draw.rect(surf, PIPE_HI, (lip.x + 6, lip.y + 3, 8, lip.h - 6))
        pygame.draw.rect(surf, PIPE_LO, (lip.right - 14, lip.y + 3, 8, lip.h - 6))
        pygame.draw.rect(surf, OUTLINE, lip, 3, border_radius=3)


def game_draw(surf, gs):
    for p in gs["pipes"]:
        draw_pipe(surf, p)
    draw_ground(surf)                             # ground over pipe bottoms
    frames = _bird_frames(gs["skin"])
    if gs["phase"] == "dead":
        img = frames[1]
    else:                                         # wing beats fast right after a flap, then glides
        rate = 18 if gs["wing_t"] < 0.3 or gs["phase"] == "ready" else 8
        img = frames[int(gs["t"] * rate) % 3]
    img = pygame.transform.rotate(img, gs["angle"])
    surf.blit(img, img.get_rect(center=(BIRD_X, int(gs["y"]))))
    if gs["flash"] > 0:                           # white impact flash
        if "white" not in _BG:
            _BG["white"] = pygame.Surface((BASE_W, BASE_H))
            _BG["white"].fill(WHITE)
        _BG["white"].set_alpha(int(200 * gs["flash"]))
        surf.blit(_BG["white"], (0, 0))


def game_hud(surf, gs):
    if gs["phase"] == "ready":
        text(surf, "GET READY", 56, BASE_W / 2, 150, UI_ACCENT)
        text(surf, "best %d" % APP["life"].get("best_score", 0), 28, BASE_W / 2, 196)
        if int(gs["t"] * 2.5) % 2 == 0:
            text(surf, "TAP TO FLAP", 34, BASE_W / 2, 380)
        # "tap" icon drawn with primitives (no emoji glyphs on Android):
        # a fingertip dot plus a ripple ring that expands every 0.6 s
        cx, cy = BASE_W // 2, 450
        ph = (gs["t"] % 0.6) / 0.6
        pygame.draw.circle(surf, WHITE, (cx, cy), int(14 + 22 * ph), 3)
        pygame.draw.circle(surf, OUTLINE, (cx, cy), 12)
        pygame.draw.circle(surf, WHITE, (cx, cy), 9)
        return
    text(surf, str(gs["score"]), 72, BASE_W / 2, 64)


def game_bot(gs):
    """Autopilot for --selftest: flap whenever the bird has fallen below a target
    just under the next gap's centre and is still descending."""
    if gs["phase"] == "ready":
        return [{"type": "down", "x": BIRD_X, "y": BASE_H / 2}]
    nxt = next((p for p in gs["pipes"] if p["x"] + PIPE_W + LIP_OVER > BIRD_X - HITBOX_HALF), None)
    target = nxt["gy"] + 0.25 * nxt["gap"] if nxt else BASE_H * 0.45
    if gs["y"] > target and gs["vy"] > 0:
        return [{"type": "down", "x": BIRD_X, "y": BASE_H / 2}]
    return []


# =====================================================================
# 7. MAIN LOOP + run lifecycle + self-test
# =====================================================================
def start_run():
    L = APP["life"]
    today = datetime.date.today()
    if L.get("last_day") != today.isoformat():     # daily streak: consecutive calendar days played
        yday = (today - datetime.timedelta(days=1)).isoformat()
        L["streak"] = L.get("streak", 0) + 1 if L.get("last_day") == yday else 1
        L["last_day"] = today.isoformat()
        if L["streak"] >= 2:
            toast("Day %d streak!" % L["streak"], "come back tomorrow for %d" % (L["streak"] + 1), UI_GOOD)
    L["games"] = L.get("games", 0) + 1
    kv_set("life", L)
    APP["gs"] = game_new(APP["settings"].get("skin", 0))
    APP.update(run_unlocks=[], death_t=0.0, resume_t=0.0, ach_timer=0.0, highlight_id=None, last_rank=None)
    music_play("play", seed=random.randrange(1 << 16))    # fresh tune every run
    set_intensity(1)
    sfx("start")
    set_mode("play")


def run_stats():
    gs = APP["gs"]
    r = dict(gs["stats"])
    r["score"] = gs["score"]
    return r


def check_achievements(r):
    for aid, name, desc, pred in ACHIEVEMENTS:
        if aid in APP["unlocked"]:
            continue
        try:
            ok = pred(r, APP["life"])
        except (KeyError, TypeError, ValueError):
            ok = False
        if ok:
            db_unlock(aid)
            APP["unlocked"][aid] = time.time()
            APP["run_unlocks"].append(name)
            toast("TROPHY: " + name, desc)
            sfx("achieve")


def end_run():
    """Fold the run into lifetime stats, then route: initials (if top-N) or game over."""
    r = run_stats()
    L = APP["life"]
    APP["run"] = r
    prev_best = L.get("best_score", 0)
    APP["is_record"] = r["score"] > prev_best and r["score"] > 0
    L["best_score"] = max(prev_best, r["score"])
    bk = "best_" + LIFE_BEST[0]
    L[bk] = max(L.get(bk, 0), r.get(LIFE_BEST[0], 0))
    L["play_time"] = L.get("play_time", 0) + r.get("time", 0)
    check_achievements(r)                          # before folding stars so totals aren't double counted
    before = L.get("total", 0)
    L["total"] = before + r.get(CURRENCY[0], 0)
    newly = [sk[0] for sk in SKINS if before < sk[1] <= L["total"]]
    for name in newly:
        toast("SKIN UNLOCKED: " + name, "change it on the title screen", UI_GOOD)
    kv_set("life", L)
    music_play("calm")
    set_intensity(1)
    sfx("record" if APP["is_record"] else "gameover")
    if APP["is_record"]:
        burst(BASE_W / 2, 170, UI_ACCENT, 50, 300, 1.3, 4)
    if db_qualifies(r["score"]):
        APP["initials"] = list(L.get("last_initials", "AAA"))
        APP["init_cursor"] = 0
        set_mode("initials")
    else:
        set_mode("over")


def update_play(dt, raw_dt, inp):
    gs = APP["gs"]
    if APP["resume_t"] > 0:                        # post-pause countdown: world frozen
        before = math.ceil(APP["resume_t"] / 0.5)
        APP["resume_t"] -= raw_dt
        after = math.ceil(max(0, APP["resume_t"]) / 0.5)
        if after != before:
            sfx("go" if after == 0 else "countdown")
        return
    for ev in inp["ptr"]:
        if ev["type"] == "down" and PAUSE_BTN.inflate(16, 16).collidepoint(ev["x"], ev["y"]):
            enter_pause()
            return
        game_input(gs, ev)
    for e in inp["keys"]:
        if e.key == pygame.K_p:
            enter_pause()
            return
        game_key(gs, e)
    if gs["over"]:                                 # death sequence: slow motion, then results
        APP["death_t"] += raw_dt
        game_update_safe(gs, dt * 0.25)
        if APP["death_t"] > 1.3:
            end_run()
        return
    game_update_safe(gs, dt)
    APP["ach_timer"] += dt
    if APP["ach_timer"] >= 0.5:                    # mid-run trophies pop while you play
        APP["ach_timer"] = 0.0
        check_achievements(run_stats())


def game_update_safe(gs, dt):
    was_over = gs["over"]
    game_update(gs, dt)
    if was_over:
        gs["over"] = True


def frame(raw_dt, inp):
    """One tick of the whole app. Pure function of (state, input) -> state, so the
    self-test can drive it with synthetic input exactly like a real finger would."""
    if inp["quit"]:
        APP["running"] = False
        return
    if inp["life"] == "bg":
        APP["suspended"] = True
        enter_pause()                              # never keep playing in the background
        audio_pause(True)
        APP["con"].commit()
    elif inp["life"] == "fg":
        APP["suspended"] = False
        audio_pause(False)
    if APP["suspended"]:
        return
    dt = min(raw_dt, DT_MAX)
    APP["t"] += dt
    APP["mode_t"] += dt
    APP["confirm_reset"] = max(0.0, APP["confirm_reset"] - dt)
    music_update(raw_dt)
    update_fx(dt)
    if inp["back"]:
        on_back()
        return
    mode = APP["mode"]
    if mode == "play":
        update_play(dt, raw_dt, inp)
        return
    if mode == "initials":
        for e in inp["keys"]:
            handle_initials_key(e)
    elif mode == "title":
        for e in inp["keys"]:
            if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                do_action("play")
    elif mode in ("over", "scores") and APP["mode_t"] > 0.6:
        for e in inp["keys"]:
            if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                do_action("retry")
    if APP["mode_t"] < 0.35 and mode in ("over", "initials", "scores"):
        return                                     # swallow taps that were meant for the game
    btns = buttons_for(mode)
    for ev in inp["ptr"]:
        if mode == "initials" and ev["type"] == "down":
            for i in range(3):                     # tapping a letter box selects that slot
                if pygame.Rect(BASE_W / 2 - 136 + i * 100, 294, 72, 80).collidepoint(ev["x"], ev["y"]):
                    APP["init_cursor"] = i
        a = handle_buttons(btns, ev)
        if a:
            do_action(a)
            break


def render():
    c = APP["canvas"]
    w = APP["world"]
    mode = APP["mode"]
    game_bg(w, APP["t"])
    gs = APP["gs"]
    if gs is not None and mode in ("play", "pause", "over", "initials", "settings", "scores"):
        game_draw(w, gs)
    draw_fx(w)
    sx = sy = 0
    if APP["shake"] > 0:
        sx = int(random.uniform(-1, 1) * APP["shake"])
        sy = int(random.uniform(-1, 1) * APP["shake"])
    c.fill(BLACK)
    c.blit(w, (sx, sy))                            # shake moves the world, never the UI
    if mode == "play" and gs is not None:
        game_hud(c, gs)
        pygame.draw.rect(c, UI_PANEL, PAUSE_BTN, border_radius=10)
        pygame.draw.rect(c, WHITE, (PAUSE_BTN.x + 14, PAUSE_BTN.y + 12, 6, 22))
        pygame.draw.rect(c, WHITE, (PAUSE_BTN.x + 26, PAUSE_BTN.y + 12, 6, 22))
        if APP["resume_t"] > 0:
            dim(c, 90)
            text(c, str(math.ceil(APP["resume_t"] / 0.5)), 110, BASE_W / 2, BASE_H / 2, UI_ACCENT)
    {"title": draw_title, "pause": draw_pause, "settings": draw_settings, "initials": draw_initials,
     "scores": draw_scores, "trophies": draw_trophies, "over": draw_over}.get(mode, lambda s: None)(c)
    draw_buttons(c, buttons_for(mode) if mode != "play" else [])
    draw_toast(c)


def loading(progress, label):
    """Synthesis takes a few seconds on a phone. Draw progress AND pump events:
    Android flags an app that ignores its event queue for ~5 s as not responding."""
    pygame.event.pump()
    c = APP["canvas"]
    c.fill(UI_BG)
    text(c, GAME_TITLE, 52, BASE_W / 2, BASE_H / 2 - 60, UI_ACCENT)
    text(c, label, 24, BASE_W / 2, BASE_H / 2 + 40, UI_DIM)
    bar = pygame.Rect(60, BASE_H / 2, BASE_W - 120, 14)
    pygame.draw.rect(c, UI_PANEL, bar, border_radius=7)
    pygame.draw.rect(c, UI_ACCENT, (bar.x, bar.y, int(bar.w * progress), bar.h), border_radius=7)
    present()


def init_app():
    pygame.mixer.pre_init(SR, -16, 1, 512)        # BEFORE pygame.init(); 512-frame buffer = low latency
    pygame.init()
    pygame.display.set_caption(GAME_TITLE)
    screen, scaled = open_display()
    APP.update(screen=screen, scaled=scaled, running=True, suspended=False, mode="boot", prev_mode=None,
               t=0.0, mode_t=0.0, gs=None, run=None, run_unlocks=[], is_record=False, pressed=None,
               particles=[], popups=[], toasts=[], shake=0.0, last_down=(0, 0, -10 ** 9),
               initials=list("AAA"), init_cursor=0, highlight_id=None, last_rank=None, scores_from_run=False,
               confirm_reset=0.0, resume_t=0.0, death_t=0.0, ach_timer=0.0, paused_intensity=1)
    APP["canvas"] = screen if scaled else pygame.Surface((BASE_W, BASE_H)).convert()
    APP["world"] = pygame.Surface((BASE_W, BASE_H)).convert()
    APP["con"] = db_open()
    APP["settings"] = kv_get("settings", dict(DEFAULT_SETTINGS, skin=0))
    APP["life"] = kv_get("life", {})
    APP["unlocked"] = db_unlocked()
    loading(0.05, "tuning synthesizers...")
    t0 = time.time()
    if audio_init():
        build_sfx(lambda p: loading(p, "synthesizing sound effects..."))
        for i, (mood, seed) in enumerate((("title", None), ("calm", None), ("play", 1), ("play", 2))):
            loading(0.4 + 0.15 * i, "composing music...")
            music_play(mood, seed)                 # prewarms every note this key can use
    APP["synth_s"] = time.time() - t0
    loading(1.0, "ready")
    music_play("title")
    set_intensity(2)
    set_mode("title")


def main():
    init_app()
    clock = pygame.time.Clock()
    while APP["running"]:
        raw_dt = clock.tick(FPS) / 1000.0          # real elapsed time (sleeps to cap FPS)
        frame(raw_dt, collect_input())
        render()
        present()
    APP["con"].commit()
    APP["con"].close()
    pygame.quit()


def selftest():
    """Headless end-to-end run: menus -> play (autopilot) -> pause/resume -> death ->
    initials -> leaderboard -> settings persistence. Exit code 0 = all checks passed.
    Uses a throwaway DB so real high scores are never touched."""
    import tempfile
    db = os.path.join(tempfile.mkdtemp(), GAME_ID + "_selftest.sqlite3")
    os.environ["PYDROID_GAME_DB"] = db
    random.seed(12345)
    init_app()
    checks = []
    dt = 1.0 / 60

    def run(seconds, ptr_fn=None, **kw):
        for _ in range(int(seconds * 60)):
            ptr = ptr_fn() if ptr_fn else []
            frame(dt, dict({"ptr": ptr, "keys": [], "back": False, "quit": False, "life": None}, **kw))
            render()

    def tap(action):
        b = next((b for b in buttons_for(APP["mode"]) if b["action"] == action), None)
        if b is None:
            checks.append(("button '%s' exists in %s" % (action, APP["mode"]), False))
            return
        x, y = b["rect"].center
        run(0.4)                                   # human reaction time; also clears the tap-swallow window
        run(1 / 60, lambda: [{"type": "down", "x": x, "y": y}])
        run(1 / 60, lambda: [{"type": "up", "x": x, "y": y}])

    def check(name, ok):
        checks.append((name, bool(ok)))

    check("audio initialised (dummy driver ok)", AUDIO["ok"])
    check("sfx bank >= 20 sounds", len(AUDIO["sfx"]) >= 20)
    check("music notes cached", len(AUDIO["notes"]) > 10)
    run(0.5)
    check("boots to title", APP["mode"] == "title")
    tap("play")
    check("PLAY -> play mode", APP["mode"] == "play")
    run(25, lambda: game_bot(APP["gs"]) if APP["gs"] else [])
    check("score increases under autopilot", APP["gs"] and APP["gs"]["score"] > 0)
    check("music sequencer advanced", AUDIO["song"] is None or AUDIO["step"] > 0)
    if APP["mode"] == "play" and not APP["gs"]["over"]:
        run(1 / 60, back=True)
        check("back -> pause", APP["mode"] == "pause")
        tap("resume")
        check("resume -> play with countdown", APP["mode"] == "play" and APP["resume_t"] > 0)
        run(2)
        frame(dt, {"ptr": [], "keys": [], "back": False, "quit": False, "life": "bg"})
        check("background -> auto-pause", APP["mode"] == "pause" and APP["suspended"])
        frame(dt, {"ptr": [], "keys": [], "back": False, "quit": False, "life": "fg"})
        tap("resume")
        run(2)
        APP["gs"]["score"] = max(APP["gs"]["score"], 42)
        APP["gs"]["over"] = True
    run(2)
    check("death -> initials (empty table qualifies)", APP["mode"] == "initials")
    tap("up0")
    tap("up0")
    tap("ok")
    check("initials -> scores", APP["mode"] == "scores")
    rows = db_top()
    check("score row stored with edited initials", rows and rows[0][1] == "CAA")
    tap("menu")
    check("menu -> title", APP["mode"] == "title")
    tap("settings")
    tap("music")
    APP["con"].close()
    APP["con"] = db_open()                         # reopen: proves it was written to disk
    check("settings persisted across reopen", abs(kv_get("settings", {}).get("music_vol", 0) - 0.8) < 1e-6)
    check("lifetime stats persisted", kv_get("life", {}).get("games", 0) >= 1)
    check("at least one trophy unlocked", len(db_unlocked()) >= 1)
    tap("back")
    check("settings back -> title", APP["mode"] == "title")
    print("synthesis time: %.2fs  (sr=%d ch=%d)" % (APP["synth_s"], AUDIO["sr"], AUDIO["ch"]))
    bad = 0
    for name, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + name)
        bad += not ok
    print("%d/%d checks passed" % (len(checks) - bad, len(checks)))
    pygame.quit()
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    selftest() if SELFTEST else main()
