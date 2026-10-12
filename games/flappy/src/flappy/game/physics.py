"""
Bird physics and collisions: semi-implicit Euler gravity, a set velocity on flap,
rectangle collisions against the same geometry that is drawn.
"""

import math

import pygame

from flappy.config import BASE_H, BASE_W, UI_ACCENT, WHITE
from flappy.engine.music import set_intensity
from flappy.engine.sfx import sfx
from flappy.engine.ui import burst, popup, shake
from flappy.game.pipes import LIP_OVER, pipe_rects, spawn_pipe, speed_for
from flappy.game.rules import SKINS
from flappy.game.state import _BG
from flappy.game.tuning import (
    BIRD_X,
    GRAVITY,
    GROUND_Y,
    HITBOX_HALF,
    MAX_FALL,
    MILESTONES,
    NEAR_MISS,
    PIPE_SPACING,
    PIPE_W,
)


def bird_box(y):
    """Square hitbox, smaller than the drawn bird (forgiveness for the round sprite)."""
    return pygame.Rect(BIRD_X - HITBOX_HALF, int(y) - HITBOX_HALF, 2 * HITBOX_HALF, 2 * HITBOX_HALF)

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
