"""
Audio device setup and the sound-effect bank.
Why pre_init and read-back: the mixer must be configured before pygame.init(), and the
real rate and channel count are read back because Android may not honour the request.
"""

import pygame

from flappy.engine.music import VOICE_CH
from flappy.engine.state import APP, AUDIO
from flappy.engine.synth import cat, midi_hz, mix, synth, to_sound


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

def build_sfx(progress, extra):
    """The standard SFX vocabulary every game should have. Game-specific sounds are
    added the same way: the game passes its own name -> builder dict as `extra`.
    Pitch ladders ('coin0'..'coin7')
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
    for name, fn in extra.items():           # game-specific additions, passed in by the caller
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
