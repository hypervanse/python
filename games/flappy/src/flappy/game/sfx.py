"""
Flappy-specific sound effects. engine/sfx.py builds them at startup, next to the standard bank.
"""

from flappy.engine.synth import cat, midi_hz, mix, synth

GAME_SFX = {   # extra sounds for this game: name -> zero-arg builder returning array('h')
    # flap: short high-passed "whoosh" (noise sweeping down) + a soft square chirp underneath
    "flap":  lambda: mix(synth(0.09, 5200, 1800, "noise", 0.16, decay=22),
                         synth(0.07, 520, 900, "square", 0.10, decay=30, duty=0.25)),
    # point: two sine tones a perfect fourth apart -> reads as "reward" without being shrill
    "point": lambda: cat(synth(0.05, midi_hz(83), None, "sine", 0.32),
                         synth(0.16, midi_hz(88), None, "sine", 0.32, decay=9)),
    # hit: low noise thump + falling square = blunt impact
    "hit":   lambda: mix(synth(0.18, 900, 120, "noise", 0.45, decay=16),
                         synth(0.16, 300, 70, "square", 0.30, decay=12)),
    # fall: long descending triangle glide while the bird drops
    "fall":  lambda: synth(0.45, 900, 180, "tri", 0.22, decay=3, release=0.1),
}
