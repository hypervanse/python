"""
Menu screens and the navigation graph. Every button and key ends in do_action(),
so the whole navigation graph can be read in one place.
"""

import datetime
import math

import pygame

from flappy.config import (
    BASE_H,
    BASE_W,
    GAME_TITLE,
    TOP_N,
    UI_ACCENT,
    UI_BAD,
    UI_DIM,
    UI_EDGE,
    UI_GOOD,
    UI_PANEL,
    WHITE,
)
from flappy.engine.music import music_play, set_intensity
from flappy.engine.run import start_run
from flappy.engine.sfx import sfx
from flappy.engine.state import APP, AUDIO, set_mode
from flappy.engine.storage import db_add_score, db_rank, db_reset_scores, db_top, kv_set
from flappy.engine.ui import burst, button, dim, draw_trophy, shake, text, toast, vstack
from flappy.game.rules import ACHIEVEMENTS, CURRENCY, LIFE_BEST, RUN_SUMMARY, SKINS

# modes: title, play, pause, settings, initials, scores, trophies, over
INIT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"

PAUSE_BTN = pygame.Rect(BASE_W - 54, 8, 46, 46)

def buttons_for(mode):
    cx = BASE_W // 2
    if mode == "title":
        skin = SKINS[APP["settings"].get("skin", 0)]
        return vstack([("PLAY", "play", "accent"), ("HIGH SCORES", "scores"), ("TROPHIES", "trophies"),
                       ("SETTINGS", "settings"), ("Skin: %s" % skin[0], "skin", "ghost")], 300)
    if mode == "pause":
        return vstack([("RESUME", "resume", "accent"), ("RESTART", "restart"), ("SETTINGS", "settings"),
                       ("QUIT TO MENU", "menu", "danger")], 230)
    if mode == "settings":
        s = APP["settings"]
        reset_lbl = "TAP AGAIN TO ERASE" if APP["confirm_reset"] > 0 else "Reset high scores"
        return vstack([("Music: %d%%" % round(s["music_vol"] * 100), "music"),
                       ("Sound FX: %d%%" % round(s["sfx_vol"] * 100), "sfxvol"),
                       ("Screen shake: %s" % ("ON" if s["shake"] else "OFF"), "shake"),
                       (reset_lbl, "reset", "danger"), ("BACK", "back", "ghost")], 170)
    if mode == "initials":
        b = []
        for i in range(3):
            x = cx - 100 + i * 100 - 36
            b.append(button(x, 228, 72, 56, "^", "up%d" % i, "ghost"))
            b.append(button(x, 384, 72, 56, "v", "dn%d" % i, "ghost"))
        b.append(button(cx - 90, 480, 180, 58, "OK", "ok", "accent"))
        return b
    if mode == "scores":
        if APP["scores_from_run"]:
            return [button(24, BASE_H - 80, 150, 56, "RETRY", "retry", "accent"),
                    button(BASE_W - 174, BASE_H - 80, 150, 56, "MENU", "menu", "ghost")]
        return [button(cx - 90, BASE_H - 80, 180, 56, "BACK", "back", "ghost")]
    if mode == "trophies":
        return [button(cx - 90, BASE_H - 80, 180, 56, "BACK", "back", "ghost")]
    if mode == "over":
        return [button(24, BASE_H - 150, 150, 56, "RETRY", "retry", "accent"),
                button(BASE_W - 174, BASE_H - 150, 150, 56, "MENU", "menu", "ghost"),
                button(cx - 90, BASE_H - 80, 180, 52, "HIGH SCORES", "scores", "ghost")]
    return []

def do_action(a):
    """Every button / key shortcut ends up here: the complete navigation graph."""
    mode = APP["mode"]
    sfx("back" if a in ("back", "menu") else "tap")
    s = APP["settings"]
    if a in ("play", "retry", "restart"):
        start_run()
    elif a == "scores":
        APP["scores_from_run"] = mode == "over"
        set_mode("scores")
    elif a == "trophies":
        set_mode("trophies")
    elif a == "settings":
        APP["settings_return"] = mode
        set_mode("settings")
    elif a == "skin":
        stars = APP["life"].get("total", 0)
        unlocked = [i for i, sk in enumerate(SKINS) if stars >= sk[1]]
        cur = s.get("skin", 0)
        s["skin"] = unlocked[(unlocked.index(cur) + 1) % len(unlocked)] if cur in unlocked else 0
        nxt = next((sk for sk in SKINS if stars < sk[1]), None)
        if nxt and s["skin"] == unlocked[-1]:
            toast("Next skin: %s" % nxt[0], "%d more %s" % (nxt[1] - stars, CURRENCY[1]), UI_DIM)
        kv_set("settings", s)
    elif a == "resume":
        APP["resume_t"] = 1.5                     # 3-2-1 grace period before play continues
        set_intensity(APP["paused_intensity"])
        set_mode("play")
    elif a == "menu":
        APP["gs"] = None
        music_play("title")
        set_intensity(2)
        set_mode("title")
    elif a == "back":
        if mode == "settings":
            set_mode(APP.get("settings_return") or "title")
        elif mode == "scores" and APP["scores_from_run"]:
            do_action("menu")
        else:
            set_mode("title")
    elif a in ("music", "sfxvol"):
        k = "music_vol" if a == "music" else "sfx_vol"
        s[k] = round((s[k] + 0.2) % 1.2, 1)       # 0 -> 20 -> ... -> 100 -> 0 %
        kv_set("settings", s)
        sfx("tick")
    elif a == "shake":
        s["shake"] = not s["shake"]
        kv_set("settings", s)
        shake(8)
    elif a == "reset":
        if APP["confirm_reset"] > 0:
            db_reset_scores()
            APP["confirm_reset"] = 0.0
            toast("High scores erased", "", UI_BAD)
        else:
            APP["confirm_reset"] = 2.5             # second tap within 2.5 s confirms
    elif a[:2] in ("up", "dn"):
        i = int(a[2])
        APP["init_cursor"] = i
        c = APP["initials"][i]
        step = 1 if a[:2] == "up" else -1
        APP["initials"][i] = INIT_CHARS[(INIT_CHARS.index(c) + step) % len(INIT_CHARS)]
        sfx("tick")
    elif a == "ok":
        submit_initials()

def on_back():
    """Android back / ESC: in play it PAUSES (never quits mid-run); in menus it goes back."""
    mode = APP["mode"]
    if mode == "play" and APP["gs"] and not APP["gs"]["over"]:
        enter_pause()
    elif mode == "pause":
        do_action("resume")
    elif mode in ("settings", "scores", "trophies"):
        do_action("back")
    elif mode in ("over", "initials"):
        if mode == "initials":
            submit_initials()
        else:
            do_action("menu")
    elif mode == "title":
        APP["running"] = False

def enter_pause():
    if APP["mode"] != "play":
        return
    APP["paused_intensity"] = AUDIO["intensity"]
    set_intensity(0)                              # music drops to ambient layer while paused
    sfx("back")
    set_mode("pause")

def handle_initials_key(e):
    i = APP["init_cursor"]
    ch = (e.unicode or "").upper()
    if ch and ch in INIT_CHARS:
        APP["initials"][i] = ch
        APP["init_cursor"] = min(2, i + 1)
        sfx("tick")
    elif e.key == pygame.K_BACKSPACE or e.key == pygame.K_LEFT:
        APP["init_cursor"] = max(0, i - 1)
    elif e.key == pygame.K_RIGHT:
        APP["init_cursor"] = min(2, i + 1)
    elif e.key == pygame.K_UP:
        do_action("up%d" % i)
    elif e.key == pygame.K_DOWN:
        do_action("dn%d" % i)
    elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        do_action("ok")

def submit_initials():
    ini = "".join(APP["initials"])
    r = APP["run"]
    sid = db_add_score(ini, r["score"], {k: v for k, v in r.items() if isinstance(v, (int, float))})
    APP["life"]["last_initials"] = ini            # pre-filled next time: fewer taps
    kv_set("life", APP["life"])
    APP["highlight_id"] = sid
    APP["last_rank"] = db_rank(sid)
    if APP["last_rank"] == 1:
        sfx("record")
        burst(BASE_W / 2, 140, UI_ACCENT, 40, 260, 1.2, 4)
    APP["scores_from_run"] = True
    set_mode("scores")

# ---- screen drawing ------------------------------------------------------
def draw_title(c):
    t = APP["t"]
    text(c, GAME_TITLE, 64, BASE_W / 2, 110 + math.sin(t * 2.2) * 6, UI_ACCENT)
    best = APP["life"].get("best_score", 0)
    text(c, "BEST  %d" % best, 30, BASE_W / 2, 170)
    st = APP["life"].get("streak", 0)
    if st >= 2:
        text(c, "Day %d streak - keep it going!" % st, 24, BASE_W / 2, 204, UI_GOOD)
    got, total = len(APP["unlocked"]), len(ACHIEVEMENTS)
    text(c, "Trophies %d / %d" % (got, total), 24, BASE_W / 2, 232, UI_DIM)
    if int(t * 2) % 2 == 0:
        text(c, "tap PLAY", 22, BASE_W / 2, 270, UI_DIM)

def draw_pause(c):
    dim(c)
    text(c, "PAUSED", 60, BASE_W / 2, 150, UI_ACCENT)
    if APP["gs"]:
        text(c, "score %d" % APP["gs"]["score"], 30, BASE_W / 2, 196)

def draw_settings(c):
    dim(c, 200)
    text(c, "SETTINGS", 52, BASE_W / 2, 100, UI_ACCENT)
    text(c, "saved automatically", 22, BASE_W / 2, 136, UI_DIM)

def draw_initials(c):
    dim(c, 190)
    r = APP["run"]
    text(c, "NEW HIGH SCORE!" if APP["is_record"] else "TOP %d!" % TOP_N, 48, BASE_W / 2, 92, UI_ACCENT)
    text(c, "%d" % r["score"], 60, BASE_W / 2, 150)
    text(c, "ENTER YOUR INITIALS", 26, BASE_W / 2, 200, UI_DIM)
    for i in range(3):
        x = BASE_W / 2 - 100 + i * 100
        box = pygame.Rect(x - 36, 294, 72, 80)
        sel = i == APP["init_cursor"]
        pygame.draw.rect(c, UI_PANEL, box, border_radius=10)
        pygame.draw.rect(c, UI_ACCENT if sel else UI_EDGE, box, 3 if sel else 2, border_radius=10)
        blink = sel and int(APP["t"] * 3) % 2 == 0
        text(c, APP["initials"][i], 70, x, 336, UI_ACCENT if blink else WHITE)

def draw_scores(c):
    dim(c, 210)
    text(c, "HIGH SCORES", 50, BASE_W / 2, 52, UI_ACCENT)
    if APP["scores_from_run"] and APP.get("last_rank"):
        text(c, "you placed #%d" % APP["last_rank"], 26, BASE_W / 2, 88, UI_GOOD)
    rows = db_top()
    y0 = 118
    for i, (sid, ini, sc, created) in enumerate(rows):
        y = y0 + i * 30
        hl = sid == APP["highlight_id"]
        col = UI_ACCENT if hl and int(APP["t"] * 4) % 2 == 0 else (WHITE if i < 3 else UI_DIM)
        if hl:
            pygame.draw.rect(c, (60, 60, 20), (20, y - 14, BASE_W - 40, 28), border_radius=6)
        day = datetime.date.fromtimestamp(created).strftime("%d/%m")
        text(c, "%2d." % (i + 1), 26, 52, y, col, "midright")
        text(c, ini, 28, 72, y, col, "midleft")
        text(c, str(sc), 28, 250, y, col, "midright")
        text(c, day, 22, BASE_W - 32, y, UI_DIM, "midright")
    if not rows:
        text(c, "no scores yet - go set one!", 26, BASE_W / 2, 200, UI_DIM)
    L = APP["life"]
    y = y0 + TOP_N * 30 + 18
    mins = int(L.get("play_time", 0) // 60)
    stats = [("games", L.get("games", 0)), ("time played", "%dh%02dm" % divmod(mins, 60)),
             (CURRENCY[1], L.get("total", 0)), (LIFE_BEST[1], L.get("best_" + LIFE_BEST[0], 0)),
             ("day streak", L.get("streak", 0))]
    for i, (k, v) in enumerate(stats):
        text(c, k, 22, 40, y + i * 22, UI_DIM, "midleft")
        text(c, str(v), 22, BASE_W - 40, y + i * 22, WHITE, "midright")

def draw_trophies(c):
    dim(c, 210)
    got = APP["unlocked"]
    text(c, "TROPHIES %d/%d" % (len(got), len(ACHIEVEMENTS)), 46, BASE_W / 2, 52, UI_ACCENT)
    for i, (aid, name, desc, _) in enumerate(ACHIEVEMENTS):
        y = 96 + i * 44
        on = aid in got
        draw_trophy(c, 36, y + 10, UI_ACCENT if on else (70, 70, 90))
        text(c, name, 28, 60, y, WHITE if on else UI_DIM, "midleft")
        text(c, desc if on else "??? " + desc, 20, 60, y + 22, UI_DIM, "midleft")

def draw_over(c):
    dim(c, 170)
    r = APP["run"]
    text(c, "GAME OVER", 58, BASE_W / 2, 90, UI_BAD)
    text(c, "%d" % r["score"], 80, BASE_W / 2, 170, UI_ACCENT if APP["is_record"] else WHITE)
    if APP["is_record"]:
        text(c, "NEW RECORD!", 34, BASE_W / 2, 222, UI_ACCENT)
    else:
        text(c, "best %d" % APP["life"].get("best_score", 0), 28, BASE_W / 2, 222, UI_DIM)
    y = 266
    for k in RUN_SUMMARY:
        text(c, "%s  %s" % (k[1], k[2](r)), 26, BASE_W / 2, y)
        y += 28
    for name in APP["run_unlocks"][:3]:
        draw_trophy(c, 70, y + 12, UI_ACCENT)
        text(c, name, 26, 92, y + 10, UI_ACCENT, "midleft")
        y += 30
