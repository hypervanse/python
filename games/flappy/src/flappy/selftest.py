"""
Headless end-to-end test: menus, autopilot play, pause, background, death, initials,
leaderboard and settings persistence. Exit code 0 means every check passed.
"""

import os
import random
import tempfile

import pygame

from flappy.app import init_app
from flappy.config import GAME_ID
from flappy.engine.loop import frame, render
from flappy.engine.screens import buttons_for
from flappy.engine.state import APP, AUDIO
from flappy.engine.storage import db_open, db_top, db_unlocked, kv_get
from flappy.game.bot import game_bot


def run_selftest():
    """Returns the process exit code (0 = every check passed) so callers decide what to do with it."""
    """Headless end-to-end run: menus -> play (autopilot) -> pause/resume -> death ->
    initials -> leaderboard -> settings persistence. Exit code 0 = all checks passed.
    Uses a throwaway DB so real high scores are never touched."""
    db = os.path.join(tempfile.mkdtemp(), GAME_ID + "_selftest.sqlite3")   # throwaway database
    os.environ[GAME_ID.upper() + "_DB"] = db                              # db_path() reads this
    random.seed(12345)
    init_app()
    checks = []
    dt = 1.0 / 60

    def run(seconds, ptr_fn=None, **kw):
        for _ in range(int(seconds * 60)):
            ptr = ptr_fn() if ptr_fn else []
            frame(dt, dict({"ptr": ptr, "keys": [], "back": False, "quit": False, "life": None}, **kw))
            render()

    def tap(action):
        b = next((b for b in buttons_for(APP["mode"]) if b["action"] == action), None)
        if b is None:
            checks.append(("button '%s' exists in %s" % (action, APP["mode"]), False))
            return
        x, y = b["rect"].center
        run(0.4)                                   # human reaction time; also clears the tap-swallow window
        run(1 / 60, lambda: [{"type": "down", "x": x, "y": y}])
        run(1 / 60, lambda: [{"type": "up", "x": x, "y": y}])

    def check(name, ok):
        checks.append((name, bool(ok)))

    check("audio initialised (dummy driver ok)", AUDIO["ok"])
    check("sfx bank >= 20 sounds", len(AUDIO["sfx"]) >= 20)
    check("music notes cached", len(AUDIO["notes"]) > 10)
    run(0.5)
    check("boots to title", APP["mode"] == "title")
    tap("play")
    check("PLAY -> play mode", APP["mode"] == "play")
    run(25, lambda: game_bot(APP["gs"]) if APP["gs"] else [])
    check("score increases under autopilot", APP["gs"] and APP["gs"]["score"] > 0)
    check("music sequencer advanced", AUDIO["song"] is None or AUDIO["step"] > 0)
    if APP["mode"] == "play" and not APP["gs"]["over"]:
        run(1 / 60, back=True)
        check("back -> pause", APP["mode"] == "pause")
        tap("resume")
        check("resume -> play with countdown", APP["mode"] == "play" and APP["resume_t"] > 0)
        run(2)
        frame(dt, {"ptr": [], "keys": [], "back": False, "quit": False, "life": "bg"})
        check("background -> auto-pause", APP["mode"] == "pause" and APP["suspended"])
        frame(dt, {"ptr": [], "keys": [], "back": False, "quit": False, "life": "fg"})
        tap("resume")
        run(2)
        APP["gs"]["score"] = max(APP["gs"]["score"], 42)
        APP["gs"]["over"] = True
    run(2)
    check("death -> initials (empty table qualifies)", APP["mode"] == "initials")
    tap("up0")
    tap("up0")
    tap("ok")
    check("initials -> scores", APP["mode"] == "scores")
    rows = db_top()
    check("score row stored with edited initials", rows and rows[0][1] == "CAA")
    tap("menu")
    check("menu -> title", APP["mode"] == "title")
    tap("settings")
    tap("music")
    APP["con"].close()
    APP["con"] = db_open()                         # reopen: proves it was written to disk
    check("settings persisted across reopen", abs(kv_get("settings", {}).get("music_vol", 0) - 0.8) < 1e-6)
    check("lifetime stats persisted", kv_get("life", {}).get("games", 0) >= 1)
    check("at least one trophy unlocked", len(db_unlocked()) >= 1)
    tap("back")
    check("settings back -> title", APP["mode"] == "title")
    print("synthesis time: %.2fs  (sr=%d ch=%d)" % (APP["synth_s"], AUDIO["sr"], AUDIO["ch"]))
    bad = 0
    for name, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + name)
        bad += not ok
    print("%d/%d checks passed" % (len(checks) - bad, len(checks)))
    pygame.quit()
    return 1 if bad else 0
