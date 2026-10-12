"""
Run state: creation, flap, and the input mapping from touch/keys to flaps.
Phases: ready -> play -> dead. The run state dict gs is JSON-friendly.
"""

import pygame

from flappy.config import BASE_H
from flappy.engine.sfx import sfx
from flappy.engine.ui import burst
from flappy.game.tuning import BIRD_X, FLAP_V

_BG = {"scroll": 0.0}            # pre-rendered layers + world scroll distance (px) for parallax

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
