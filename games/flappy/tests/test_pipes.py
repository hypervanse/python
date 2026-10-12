"""
Pipe geometry and difficulty curves. These are pure functions, so no window is needed.
"""

from flappy.game.pipes import gap_for, pipe_rects, speed_for
from flappy.game.tuning import GAP_MIN, GAP_START, SPEED_MAX, SPEED_START


def test_gap_starts_wide_and_never_drops_below_the_minimum():
    assert gap_for(0) == GAP_START
    assert gap_for(10_000) == GAP_MIN          # clamped: the course stays playable forever


def test_speed_ramps_up_and_then_caps():
    assert speed_for(0) == SPEED_START
    assert speed_for(10_000) == SPEED_MAX


def test_pipe_pair_frames_exactly_the_requested_gap():
    pipe = {"x": 100.0, "gy": 300.0, "gap": 120.0}   # gap centre at y=300, 120 px tall
    r = pipe_rects(pipe)
    assert r["bot_lip"].top - r["top_lip"].bottom == 120   # the free space is the gap, nothing more
    assert r["top_body"].top < 0                           # the top pipe runs off-screen: no flying over it
