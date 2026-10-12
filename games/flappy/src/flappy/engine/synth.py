"""
Sound primitives: waveform generators that return raw 16-bit PCM arrays.
Why synthesis: no audio files are shipped or loaded, so the project stays small
and runs anywhere pygame runs.
"""

import math
import random
from array import array

import pygame

from flappy.engine.state import AUDIO


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
