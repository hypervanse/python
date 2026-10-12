"""
Renders each screen to a PNG so the layout can be checked by eye.

Usage, from the project folder:   uv run python tools/snapshot.py shots

Why it works on any machine: the dummy SDL drivers draw into memory, so no display is needed.
The bot plays the game, so the play screen shows real pipes and not an empty sky.
"""

import os
import random
import sys
from pathlib import Path

out = Path(sys.argv[1] if len(sys.argv) > 1 else "shots")
out.mkdir(parents=True, exist_ok=True)

# Headless drivers and a throwaway database. These must be set BEFORE pygame is imported.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ["FLAPPY_DB"] = str(out / "snapshot.sqlite3")   # keeps real scores out of the picture

import pygame  # noqa: E402  (after the environment is set on purpose)

from flappy import app  # noqa: E402
from flappy.engine import loop  # noqa: E402
from flappy.engine.screens import do_action, enter_pause  # noqa: E402
from flappy.engine.state import APP  # noqa: E402
from flappy.game.bot import game_bot  # noqa: E402


def run(seconds, bot=None):
    # advance the app by `seconds` of simulated time, one 60 Hz frame at a time
    for _ in range(int(seconds * 60)):
        ptr = bot() if bot else []
        loop.frame(1 / 60, {"ptr": ptr, "keys": [], "back": False, "quit": False, "life": None})
        loop.render()


def snap(name):
    # save the logical canvas (the 360 x 640 picture the player would see, before any window scaling)
    pygame.image.save(APP["canvas"], str(out / (name + ".png")))
    print("wrote", out / (name + ".png"))


def autopilot():
    # the bot's touches while playing; nothing once the mode changes
    return game_bot(APP["gs"]) if APP["mode"] == "play" else []


def main():
    random.seed(7)                             # fixed seed: the same screenshots on every run
    app.init_app()
    run(0.5)
    snap("1_title")
    do_action("play")                          # the same path a tap on the PLAY button takes
    run(0.8)
    snap("2_ready")
    run(6, autopilot)
    snap("3_play")
    enter_pause()                              # the same path the pause button takes
    run(0.3)
    snap("4_pause")
    do_action("resume")
    APP["gs"]["over"] = True                   # end the run now to reach the results screens
    run(3.5)                                   # 1.5 s resume countdown + 1.3 s death beat + margin
    snap("5_initials")
    do_action("ok")
    run(0.5)
    snap("6_scores")
    do_action("menu")
    do_action("trophies")
    run(0.5)
    snap("7_trophies")
    do_action("back")
    do_action("settings")
    run(0.5)
    snap("8_settings")


if __name__ == "__main__":
    main()
