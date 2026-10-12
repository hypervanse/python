"""
Flappy's tuning knobs. Units: logical pixels (canvas is 360x640), seconds, px/s, px/s^2.
Every value says what raising or lowering it does.
"""

from flappy.config import BASE_H

# ---- game tuning (FLAPPY). Units: logical px, seconds, px/s, px/s^2. ----
# The physics are tuned for TOUCH, not keyboard spam: a finger tap has ~50-100 ms
# of latency and nobody can tap faster than ~6-7 Hz comfortably, so one flap must
# carry the bird a meaningful distance (~65 px) and the fall must be readable.
#   apex height of one flap = FLAP_V^2 / (2*GRAVITY) = 440^2/3000 ~= 65 px
#   time to apex            = FLAP_V / GRAVITY       = 0.29 s
GRAVITY      = 1500.0            # px/s^2 downward. Higher = heavier bird, harder; lower = floaty.

FLAP_V       = 440.0             # px/s upward velocity SET (not added) by a tap. Setting it makes

                                 #   every tap identical regardless of current fall speed -> predictable.
MAX_FALL     = 620.0             # px/s terminal velocity; caps how fast a missed tap punishes you.

BIRD_X       = 100               # px, fixed horizontal position of the bird (world scrolls instead)

BIRD_R       = 14                # px, drawn body radius

HITBOX_HALF  = 10                # px, half-size of the square collision box (< BIRD_R = forgiveness)

GROUND_H     = 84                # px, ground strip height at the bottom

GROUND_Y     = BASE_H - GROUND_H # px, top of the ground = death line

PIPE_W       = 60                # px, pipe width. Wider = longer time inside the gap = harder.

GAP_START    = 168               # px, vertical gap at score 0. Bigger = easier.

GAP_MIN      = 122               # px, gap floor reached late in a run (never below ~4.3x bird height).

GAP_SHRINK   = 1.5               # px removed from the gap per pipe passed -> difficulty curve

SPEED_START  = 140.0             # px/s pipe scroll speed at score 0. Higher = less reaction time.

SPEED_MAX    = 215.0             # px/s cap.

SPEED_RAMP   = 1.6               # px/s added per pipe passed

PIPE_SPACING = 215               # px between consecutive pipes (spawned by DISTANCE, not timer,

                                 #   so spacing stays constant when speed ramps or a frame hitches)
GAP_MARGIN   = 70                # px, keep gaps at least this far from the top and the ground

GAP_JUMP_MAX = 190               # px, max vertical shift of gap centre between consecutive pipes

                                 #   (keeps every pipe pair physically reachable)
NEAR_MISS    = 9                 # px, passing within this of a pipe lip counts as a "close call"

MILESTONES   = (10, 25, 50, 100) # scores that fire the LEVEL fanfare and raise music intensity
