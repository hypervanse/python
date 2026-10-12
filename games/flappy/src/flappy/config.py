"""
Identity, resolution, timing and palette shared by the engine and the game.
Edit GAME_ID and GAME_TITLE to start a new game. Game tuning lives in game/tuning.py.
"""

GAME_ID    = "flappy"            # slug: names the database file -> one DB per game

GAME_TITLE = "FLAPPY"

BASE_W, BASE_H = 360, 640        # logical canvas, portrait. All coordinates use this space.

FPS        = 60

DT_MAX     = 1.0 / 30.0          # clamp simulation dt: a GC pause / app switch can't teleport objects

SR         = 22050               # audio sample rate; 22.05 kHz halves synthesis time vs 44.1 kHz

TOP_N      = 10                  # rows in the high-score table

# palette (shared by UI; the game section may define its own)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)

UI_BG      = (18, 20, 38)

UI_PANEL   = (32, 36, 66)

UI_EDGE    = (90, 100, 170)

UI_ACCENT  = (255, 200, 60)

UI_GOOD    = (90, 230, 140)

UI_BAD     = (255, 90, 90)

UI_DIM     = (130, 135, 165)
