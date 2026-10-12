"""
Startup (loading screen while sounds are synthesized) and the real-time main loop.
"""

import time

import pygame

from flappy.config import BASE_H, BASE_W, FPS, GAME_TITLE, SR, UI_ACCENT, UI_BG, UI_DIM, UI_PANEL
from flappy.engine.display import open_display, present
from flappy.engine.inputs import collect_input
from flappy.engine.loop import frame, render
from flappy.engine.music import music_play, set_intensity
from flappy.engine.sfx import audio_init, build_sfx
from flappy.engine.state import APP, set_mode
from flappy.engine.storage import DEFAULT_SETTINGS, db_open, db_unlocked, kv_get
from flappy.engine.ui import text
from flappy.game.sfx import GAME_SFX


def loading(progress, label):
    """Synthesis takes a few seconds on a phone. Draw progress AND pump events:
    Android flags an app that ignores its event queue for ~5 s as not responding."""
    pygame.event.pump()
    c = APP["canvas"]
    c.fill(UI_BG)
    text(c, GAME_TITLE, 52, BASE_W / 2, BASE_H / 2 - 60, UI_ACCENT)
    text(c, label, 24, BASE_W / 2, BASE_H / 2 + 40, UI_DIM)
    bar = pygame.Rect(60, BASE_H / 2, BASE_W - 120, 14)
    pygame.draw.rect(c, UI_PANEL, bar, border_radius=7)
    pygame.draw.rect(c, UI_ACCENT, (bar.x, bar.y, int(bar.w * progress), bar.h), border_radius=7)
    present()

def init_app():
    pygame.mixer.pre_init(SR, -16, 1, 512)        # BEFORE pygame.init(); 512-frame buffer = low latency
    pygame.init()
    pygame.display.set_caption(GAME_TITLE)
    screen, scaled = open_display()
    APP.update(screen=screen, scaled=scaled, running=True, suspended=False, mode="boot", prev_mode=None,
               t=0.0, mode_t=0.0, gs=None, run=None, run_unlocks=[], is_record=False, pressed=None,
               particles=[], popups=[], toasts=[], shake=0.0, last_down=(0, 0, -10 ** 9),
               initials=list("AAA"), init_cursor=0, highlight_id=None, last_rank=None, scores_from_run=False,
               confirm_reset=0.0, resume_t=0.0, death_t=0.0, ach_timer=0.0, paused_intensity=1)
    APP["canvas"] = screen if scaled else pygame.Surface((BASE_W, BASE_H)).convert()
    APP["world"] = pygame.Surface((BASE_W, BASE_H)).convert()
    APP["con"] = db_open()
    APP["settings"] = kv_get("settings", dict(DEFAULT_SETTINGS, skin=0))
    APP["life"] = kv_get("life", {})
    APP["unlocked"] = db_unlocked()
    loading(0.05, "tuning synthesizers...")
    t0 = time.time()
    if audio_init():
        build_sfx(lambda p: loading(p, "synthesizing sound effects..."), GAME_SFX)
        for i, (mood, seed) in enumerate((("title", None), ("calm", None), ("play", 1), ("play", 2))):
            loading(0.4 + 0.15 * i, "composing music...")
            music_play(mood, seed)                 # prewarms every note this key can use
    APP["synth_s"] = time.time() - t0
    loading(1.0, "ready")
    music_play("title")
    set_intensity(2)
    set_mode("title")

def main():
    init_app()
    clock = pygame.time.Clock()
    while APP["running"]:
        raw_dt = clock.tick(FPS) / 1000.0          # real elapsed time (sleeps to cap FPS)
        frame(raw_dt, collect_input())
        render()
        present()
    APP["con"].commit()
    APP["con"].close()
    pygame.quit()
