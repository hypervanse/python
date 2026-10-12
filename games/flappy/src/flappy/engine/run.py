"""
Run lifecycle: start a run, fold its stats into lifetime totals, check trophies,
then route to the initials screen (top-N score) or the game-over screen.
"""

import datetime
import random
import time

from flappy.config import BASE_W, UI_ACCENT, UI_GOOD
from flappy.engine.music import music_play, set_intensity
from flappy.engine.sfx import sfx
from flappy.engine.state import APP, set_mode
from flappy.engine.storage import db_qualifies, db_unlock, kv_set
from flappy.engine.ui import burst, toast
from flappy.game.rules import ACHIEVEMENTS, CURRENCY, LIFE_BEST, SKINS
from flappy.game.state import game_new


def start_run():
    L = APP["life"]
    today = datetime.date.today()
    if L.get("last_day") != today.isoformat():     # daily streak: consecutive calendar days played
        yday = (today - datetime.timedelta(days=1)).isoformat()
        L["streak"] = L.get("streak", 0) + 1 if L.get("last_day") == yday else 1
        L["last_day"] = today.isoformat()
        if L["streak"] >= 2:
            toast("Day %d streak!" % L["streak"], "come back tomorrow for %d" % (L["streak"] + 1), UI_GOOD)
    L["games"] = L.get("games", 0) + 1
    kv_set("life", L)
    APP["gs"] = game_new(APP["settings"].get("skin", 0))
    APP.update(run_unlocks=[], death_t=0.0, resume_t=0.0, ach_timer=0.0, highlight_id=None, last_rank=None)
    music_play("play", seed=random.randrange(1 << 16))    # fresh tune every run
    set_intensity(1)
    sfx("start")
    set_mode("play")

def run_stats():
    gs = APP["gs"]
    r = dict(gs["stats"])
    r["score"] = gs["score"]
    return r

def check_achievements(r):
    for aid, name, desc, pred in ACHIEVEMENTS:
        if aid in APP["unlocked"]:
            continue
        try:
            ok = pred(r, APP["life"])
        except (KeyError, TypeError, ValueError):
            ok = False
        if ok:
            db_unlock(aid)
            APP["unlocked"][aid] = time.time()
            APP["run_unlocks"].append(name)
            toast("TROPHY: " + name, desc)
            sfx("achieve")

def end_run():
    """Fold the run into lifetime stats, then route: initials (if top-N) or game over."""
    r = run_stats()
    L = APP["life"]
    APP["run"] = r
    prev_best = L.get("best_score", 0)
    APP["is_record"] = r["score"] > prev_best and r["score"] > 0
    L["best_score"] = max(prev_best, r["score"])
    bk = "best_" + LIFE_BEST[0]
    L[bk] = max(L.get(bk, 0), r.get(LIFE_BEST[0], 0))
    L["play_time"] = L.get("play_time", 0) + r.get("time", 0)
    check_achievements(r)                          # before folding stars so totals aren't double counted
    before = L.get("total", 0)
    L["total"] = before + r.get(CURRENCY[0], 0)
    newly = [sk[0] for sk in SKINS if before < sk[1] <= L["total"]]
    for name in newly:
        toast("SKIN UNLOCKED: " + name, "change it on the title screen", UI_GOOD)
    kv_set("life", L)
    music_play("calm")
    set_intensity(1)
    sfx("record" if APP["is_record"] else "gameover")
    if APP["is_record"]:
        burst(BASE_W / 2, 170, UI_ACCENT, 50, 300, 1.3, 4)
    if db_qualifies(r["score"]):
        APP["initials"] = list(L.get("last_initials", "AAA"))
        APP["init_cursor"] = 0
        set_mode("initials")
    else:
        set_mode("over")
