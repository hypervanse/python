"""
Shared mutable state. APP holds app-level state (mode, settings, toasts, particles,
database handle). AUDIO holds mixer state. Every module reads these two dicts, so
there is one place to look when something is wrong.
"""

from flappy.config import SR

APP = {}        # all app-level (non-game) state lives in this one dict

# Everything is generated into signed 16-bit PCM arrays (array('h')) and wrapped
# with pygame.mixer.Sound(buffer=...). Pure Python, no numpy, no files.
AUDIO = {"ok": False, "sr": SR, "ch": 1, "sfx": {}, "notes": {}, "song": None,
         "song_cache": {}, "step": 0, "acc": 0.0, "intensity": 0, "voices": {}, "paused": False}

def set_mode(mode):
    APP["prev_mode"], APP["mode"], APP["mode_t"] = APP["mode"], mode, 0.0
    APP["pressed"] = None
