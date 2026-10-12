"""
Entry point: `python -m flappy`, or the `flappy` console script defined in pyproject.toml.

SDL reads its environment variables when its subsystems start, so they must be set BEFORE pygame
is imported anywhere. This file sets them at import time, and the engine and game modules are
imported only inside main(), after that.
"""

import os
import sys

if "--selftest" in sys.argv:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")         # no window needed on a headless box
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")         # and no sound card either
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")      # keep pygame's banner out of the console


def main():
    if "--selftest" in sys.argv:
        from flappy.selftest import run_selftest  # late import: after the env vars above
        sys.exit(run_selftest())                              # exit code 0 = every check passed
    from flappy.app import main as run_app  # late import, same reason
    run_app()


if __name__ == "__main__":
    main()
