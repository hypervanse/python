"""
Bird physics: flap impulse, the fall-speed cap and the ground. These need the engine state
(sounds and particles), so each test requests the app_ready fixture from conftest.py.
"""

from flappy.game.physics import game_update
from flappy.game.state import flap, game_new
from flappy.game.tuning import FLAP_V, GROUND_Y, HITBOX_HALF, MAX_FALL


def test_first_tap_starts_the_run_and_flaps(app_ready):
    gs = game_new(0)
    assert gs["phase"] == "ready"
    flap(gs)
    assert gs["phase"] == "play"
    assert gs["vy"] == -FLAP_V                 # the velocity is SET to the impulse, not added to


def test_a_tap_lifts_the_same_amount_whatever_the_fall_speed(app_ready):
    diving, hovering = game_new(0), game_new(0)
    diving["phase"] = hovering["phase"] = "play"
    diving["vy"], hovering["vy"] = 500.0, 0.0  # falling fast vs. hovering
    flap(diving)
    flap(hovering)
    assert diving["vy"] == hovering["vy"] == -FLAP_V   # identical result: the timing is learnable


def test_fall_speed_is_capped_at_terminal_velocity(app_ready):
    gs = game_new(0)
    gs["phase"], gs["y"], gs["vy"] = "play", 200.0, 0.0
    for _ in range(40):                        # ~0.67 s of free fall, short enough to stay above the ground
        game_update(gs, 1 / 60)
    assert gs["phase"] == "play"
    assert gs["vy"] == MAX_FALL                # gravity alone would have pushed it past the cap


def test_hitting_the_ground_ends_the_run(app_ready):
    gs = game_new(0)
    gs["phase"] = "play"
    gs["y"] = GROUND_Y - HITBOX_HALF - 1.0     # just above the ground line
    gs["vy"] = 400.0                           # moving down
    game_update(gs, 1 / 30)
    assert gs["over"] is True
    assert gs["phase"] == "dead"
