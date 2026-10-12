"""
Autopilot used by the self-test and the screenshot tool. Never used during real play.
"""

from flappy.config import BASE_H
from flappy.game.pipes import LIP_OVER
from flappy.game.tuning import BIRD_X, HITBOX_HALF, PIPE_W


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
