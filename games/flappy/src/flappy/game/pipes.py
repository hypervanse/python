"""
Pipe geometry, difficulty curves and spawning.
Why spawn by distance: spacing stays constant when speed ramps or a frame hitches.
"""

import random

import pygame

from flappy.game.tuning import (
    GAP_JUMP_MAX,
    GAP_MARGIN,
    GAP_MIN,
    GAP_SHRINK,
    GAP_START,
    GROUND_Y,
    PIPE_W,
    SPEED_MAX,
    SPEED_RAMP,
    SPEED_START,
)

LIP_H, LIP_OVER = 26, 4          # pipe lip height and how far it overhangs the body on each side

# ---- difficulty as pure functions of score (one place to read the curve) ----
def gap_for(score):
    return max(GAP_MIN, GAP_START - GAP_SHRINK * score)

def speed_for(score):
    return min(SPEED_MAX, SPEED_START + SPEED_RAMP * score)

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
