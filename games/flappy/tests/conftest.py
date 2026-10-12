"""
Shared test setup, loaded by pytest before any test module.

The headless SDL drivers let the tests open a window and a mixer on a machine with no display
or sound card (a CI runner, a server, a laptop with the lid closed).
"""

import os

# SDL reads these when its subsystems start, so they must be set before pygame is first used.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")         # draw into memory, no window
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")         # mix into nothing, no sound card
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # keep the console quiet

import pytest  # noqa: E402  (imported after the environment is set on purpose)


@pytest.fixture(autouse=True)
def throwaway_database(tmp_path, monkeypatch):
    """Every test gets its own high-score file, so no test can touch real scores."""
    monkeypatch.setenv("FLAPPY_DB", str(tmp_path / "test.sqlite3"))
    yield


@pytest.fixture
def app_ready():
    """Start the engine state, sounds and menus the way the real program does."""
    from flappy.app import init_app

    init_app()
    yield
