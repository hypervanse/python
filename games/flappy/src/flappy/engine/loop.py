"""
Frame driver and renderer. frame() is a pure function of (state, input), which lets the
self-test drive the whole app with synthetic touches.
"""

import math
import random

import pygame

from flappy.config import BASE_H, BASE_W, BLACK, DT_MAX, UI_ACCENT, UI_PANEL, WHITE
from flappy.engine.music import audio_pause, music_update
from flappy.engine.run import check_achievements, end_run, run_stats
from flappy.engine.screens import (
    PAUSE_BTN,
    buttons_for,
    do_action,
    draw_initials,
    draw_over,
    draw_pause,
    draw_scores,
    draw_settings,
    draw_title,
    draw_trophies,
    enter_pause,
    handle_initials_key,
    on_back,
)
from flappy.engine.sfx import sfx
from flappy.engine.state import APP
from flappy.engine.ui import dim, draw_buttons, draw_fx, draw_toast, handle_buttons, text, update_fx
from flappy.game.draw import game_bg, game_draw, game_hud
from flappy.game.physics import game_update
from flappy.game.state import game_input, game_key


def update_play(dt, raw_dt, inp):
    gs = APP["gs"]
    if APP["resume_t"] > 0:                        # post-pause countdown: world frozen
        before = math.ceil(APP["resume_t"] / 0.5)
        APP["resume_t"] -= raw_dt
        after = math.ceil(max(0, APP["resume_t"]) / 0.5)
        if after != before:
            sfx("go" if after == 0 else "countdown")
        return
    for ev in inp["ptr"]:
        if ev["type"] == "down" and PAUSE_BTN.inflate(16, 16).collidepoint(ev["x"], ev["y"]):
            enter_pause()
            return
        game_input(gs, ev)
    for e in inp["keys"]:
        if e.key == pygame.K_p:
            enter_pause()
            return
        game_key(gs, e)
    if gs["over"]:                                 # death sequence: slow motion, then results
        APP["death_t"] += raw_dt
        game_update_safe(gs, dt * 0.25)
        if APP["death_t"] > 1.3:
            end_run()
        return
    game_update_safe(gs, dt)
    APP["ach_timer"] += dt
    if APP["ach_timer"] >= 0.5:                    # mid-run trophies pop while you play
        APP["ach_timer"] = 0.0
        check_achievements(run_stats())

def game_update_safe(gs, dt):
    was_over = gs["over"]
    game_update(gs, dt)
    if was_over:
        gs["over"] = True

def frame(raw_dt, inp):
    """One tick of the whole app. Pure function of (state, input) -> state, so the
    self-test can drive it with synthetic input exactly like a real finger would."""
    if inp["quit"]:
        APP["running"] = False
        return
    if inp["life"] == "bg":
        APP["suspended"] = True
        enter_pause()                              # never keep playing in the background
        audio_pause(True)
        APP["con"].commit()
    elif inp["life"] == "fg":
        APP["suspended"] = False
        audio_pause(False)
    if APP["suspended"]:
        return
    dt = min(raw_dt, DT_MAX)
    APP["t"] += dt
    APP["mode_t"] += dt
    APP["confirm_reset"] = max(0.0, APP["confirm_reset"] - dt)
    music_update(raw_dt)
    update_fx(dt)
    if inp["back"]:
        on_back()
        return
    mode = APP["mode"]
    if mode == "play":
        update_play(dt, raw_dt, inp)
        return
    if mode == "initials":
        for e in inp["keys"]:
            handle_initials_key(e)
    elif mode == "title":
        for e in inp["keys"]:
            if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                do_action("play")
    elif mode in ("over", "scores") and APP["mode_t"] > 0.6:
        for e in inp["keys"]:
            if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                do_action("retry")
    if APP["mode_t"] < 0.35 and mode in ("over", "initials", "scores"):
        return                                     # swallow taps that were meant for the game
    btns = buttons_for(mode)
    for ev in inp["ptr"]:
        if mode == "initials" and ev["type"] == "down":
            for i in range(3):                     # tapping a letter box selects that slot
                if pygame.Rect(BASE_W / 2 - 136 + i * 100, 294, 72, 80).collidepoint(ev["x"], ev["y"]):
                    APP["init_cursor"] = i
        a = handle_buttons(btns, ev)
        if a:
            do_action(a)
            break

def render():
    c = APP["canvas"]
    w = APP["world"]
    mode = APP["mode"]
    game_bg(w, APP["t"])
    gs = APP["gs"]
    if gs is not None and mode in ("play", "pause", "over", "initials", "settings", "scores"):
        game_draw(w, gs)
    draw_fx(w)
    sx = sy = 0
    if APP["shake"] > 0:
        sx = int(random.uniform(-1, 1) * APP["shake"])
        sy = int(random.uniform(-1, 1) * APP["shake"])
    c.fill(BLACK)
    c.blit(w, (sx, sy))                            # shake moves the world, never the UI
    if mode == "play" and gs is not None:
        game_hud(c, gs)
        pygame.draw.rect(c, UI_PANEL, PAUSE_BTN, border_radius=10)
        pygame.draw.rect(c, WHITE, (PAUSE_BTN.x + 14, PAUSE_BTN.y + 12, 6, 22))
        pygame.draw.rect(c, WHITE, (PAUSE_BTN.x + 26, PAUSE_BTN.y + 12, 6, 22))
        if APP["resume_t"] > 0:
            dim(c, 90)
            text(c, str(math.ceil(APP["resume_t"] / 0.5)), 110, BASE_W / 2, BASE_H / 2, UI_ACCENT)
    {"title": draw_title, "pause": draw_pause, "settings": draw_settings, "initials": draw_initials,
     "scores": draw_scores, "trophies": draw_trophies, "over": draw_over}.get(mode, lambda s: None)(c)
    draw_buttons(c, buttons_for(mode) if mode != "play" else [])
    draw_toast(c)
