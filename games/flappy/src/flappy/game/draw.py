"""
Procedural graphics: parallax backdrop, pipes, bird sprites and HUD.
Sprites and backdrops are rendered once to Surfaces; each frame only blits them.
"""

import random

import pygame

from flappy.config import BASE_H, BASE_W, BLACK, UI_ACCENT, WHITE
from flappy.engine.state import APP
from flappy.engine.ui import text
from flappy.game.pipes import pipe_rects
from flappy.game.rules import SKINS
from flappy.game.state import _BG
from flappy.game.tuning import BIRD_X, GROUND_H, GROUND_Y

PIPE_C, PIPE_HI, PIPE_LO = (96, 196, 70), (160, 236, 120), (52, 128, 40)   # body, highlight, shadow

OUTLINE = (30, 40, 30)

# ---- pre-rendered graphics (built once, blitted per frame) ----------------
def _build_layers():
    sky = pygame.Surface((BASE_W, BASE_H))
    for y in range(BASE_H):                       # vertical gradient: deep blue -> warm horizon
        k = y / BASE_H
        pygame.draw.line(sky, (int(70 + 120 * k), int(150 + 60 * k), int(225 + 10 * k)), (0, y), (BASE_W, y))
    _BG["sky"] = sky
    rng = random.Random(11)                       # seeded: same skyline every launch
    city = pygame.Surface((BASE_W, 160), pygame.SRCALPHA)
    x = 0
    while x < BASE_W:                             # buildings must tile seamlessly -> stop exactly at BASE_W
        w = min(rng.randint(22, 48), BASE_W - x)
        h = rng.randint(50, 140)
        pygame.draw.rect(city, (150, 196, 210), (x, 160 - h, w, h))
        for wy in range(160 - h + 8, 150, 14):    # little lit windows
            for wx in range(x + 5, x + w - 6, 10):
                if rng.random() < 0.55:
                    pygame.draw.rect(city, (190, 226, 236), (wx, wy, 4, 6))
        x += w
    _BG["city"] = city
    clouds = pygame.Surface((BASE_W, 90), pygame.SRCALPHA)
    for i in range(7):
        cx, cy, r = rng.randint(0, BASE_W), rng.randint(30, 60), rng.randint(18, 30)
        for dx in (-r, 0, r):                     # 3 overlapping circles = cartoon cloud;
            for off in (-BASE_W, 0, BASE_W):      # drawn at +-BASE_W too so the strip tiles
                pygame.draw.circle(clouds, (250, 252, 255), (cx + dx + off, cy + (0 if dx else -8)), r)
    _BG["clouds"] = clouds
    ground = pygame.Surface((BASE_W + 24, GROUND_H))   # 24 px wider: one stripe period of slack
    ground.fill((222, 206, 140))
    pygame.draw.rect(ground, (110, 190, 70), (0, 0, BASE_W + 24, 16))
    for sx in range(-24, BASE_W + 48, 24):        # diagonal stripes, period 24 px
        pygame.draw.polygon(ground, (130, 210, 80), [(sx, 0), (sx + 12, 0), (sx + 4, 16), (sx - 8, 16)])
    pygame.draw.line(ground, OUTLINE, (0, 0), (BASE_W + 24, 0), 3)
    pygame.draw.line(ground, (180, 160, 100), (0, 17), (BASE_W + 24, 17), 2)
    _BG["ground"] = ground

def _bird_frames(skin):
    """3 wing poses per skin (up / mid / down), drawn once with an outline so the
    bird reads clearly at phone size. Rotation happens per frame on these."""
    key = "bird%d" % skin
    if key in _BG:
        return _BG[key]
    body, wing = SKINS[skin][2]
    frames = []
    for wy in (-7, 0, 6):                         # wing vertical offset per pose
        s = pygame.Surface((48, 40), pygame.SRCALPHA)
        c = (24, 20)                              # body centre inside the sprite
        pygame.draw.ellipse(s, OUTLINE, (c[0] - 17, c[1] - 14, 34, 28))
        pygame.draw.ellipse(s, body, (c[0] - 15, c[1] - 12, 30, 24))
        pygame.draw.ellipse(s, (255, 245, 210), (c[0] - 9, c[1] + 1, 18, 9))      # belly
        pygame.draw.ellipse(s, OUTLINE, (c[0] - 17, c[1] - 5 + wy, 18, 12))
        pygame.draw.ellipse(s, wing, (c[0] - 16, c[1] - 4 + wy, 16, 10))          # wing
        pygame.draw.circle(s, OUTLINE, (c[0] + 7, c[1] - 5), 7)
        pygame.draw.circle(s, WHITE, (c[0] + 7, c[1] - 5), 6)                    # eye
        pygame.draw.circle(s, BLACK, (c[0] + 9, c[1] - 5), 3)                    # pupil
        pygame.draw.polygon(s, OUTLINE, [(c[0] + 11, c[1] - 1), (c[0] + 24, c[1] + 3), (c[0] + 11, c[1] + 8)])
        pygame.draw.polygon(s, (255, 120, 40), [(c[0] + 12, c[1]), (c[0] + 22, c[1] + 3), (c[0] + 12, c[1] + 6)])
        frames.append(s)
    _BG[key] = frames
    return frames

def draw_ground(surf):
    surf.blit(_BG["ground"], (-int(_BG["scroll"] % 24), GROUND_Y))

def game_bg(surf, t):
    """Sky + parallax clouds/city. Each layer scrolls at a fraction of world speed:
    far things move slower, which is the whole depth illusion."""
    if "sky" not in _BG:
        _build_layers()
    if APP.get("gs") is None:                     # title screen: keep the world drifting
        _BG["scroll"] = t * 60
    s = _BG["scroll"]
    surf.blit(_BG["sky"], (0, 0))
    for layer, k, y in (("clouds", 0.10, 70), ("city", 0.25, GROUND_Y - 160)):
        off = -int(s * k) % BASE_W                # wrap: blit twice, side by side
        surf.blit(_BG[layer], (off - BASE_W, y))
        surf.blit(_BG[layer], (off, y))
    draw_ground(surf)

def draw_pipe(surf, p):
    r = pipe_rects(p)
    for body in (r["top_body"], r["bot_body"]):
        if body.h <= 0:
            continue
        vis = body.clip(pygame.Rect(-10, -10, BASE_W + 20, BASE_H + 20))   # don't fill 2000 px offscreen
        pygame.draw.rect(surf, PIPE_C, vis)
        pygame.draw.rect(surf, PIPE_HI, (vis.x + 6, vis.y, 8, vis.h))        # specular stripe
        pygame.draw.rect(surf, PIPE_LO, (vis.right - 12, vis.y, 8, vis.h))   # shadow stripe
        pygame.draw.rect(surf, OUTLINE, vis, 3)
    for lip in (r["top_lip"], r["bot_lip"]):
        pygame.draw.rect(surf, PIPE_C, lip)
        pygame.draw.rect(surf, PIPE_HI, (lip.x + 6, lip.y + 3, 8, lip.h - 6))
        pygame.draw.rect(surf, PIPE_LO, (lip.right - 14, lip.y + 3, 8, lip.h - 6))
        pygame.draw.rect(surf, OUTLINE, lip, 3, border_radius=3)

def game_draw(surf, gs):
    for p in gs["pipes"]:
        draw_pipe(surf, p)
    draw_ground(surf)                             # ground over pipe bottoms
    frames = _bird_frames(gs["skin"])
    if gs["phase"] == "dead":
        img = frames[1]
    else:                                         # wing beats fast right after a flap, then glides
        rate = 18 if gs["wing_t"] < 0.3 or gs["phase"] == "ready" else 8
        img = frames[int(gs["t"] * rate) % 3]
    img = pygame.transform.rotate(img, gs["angle"])
    surf.blit(img, img.get_rect(center=(BIRD_X, int(gs["y"]))))
    if gs["flash"] > 0:                           # white impact flash
        if "white" not in _BG:
            _BG["white"] = pygame.Surface((BASE_W, BASE_H))
            _BG["white"].fill(WHITE)
        _BG["white"].set_alpha(int(200 * gs["flash"]))
        surf.blit(_BG["white"], (0, 0))

def game_hud(surf, gs):
    if gs["phase"] == "ready":
        text(surf, "GET READY", 56, BASE_W / 2, 150, UI_ACCENT)
        text(surf, "best %d" % APP["life"].get("best_score", 0), 28, BASE_W / 2, 196)
        if int(gs["t"] * 2.5) % 2 == 0:
            text(surf, "TAP TO FLAP", 34, BASE_W / 2, 380)
        # "tap" icon drawn with primitives (no emoji glyphs on Android):
        # a fingertip dot plus a ripple ring that expands every 0.6 s
        cx, cy = BASE_W // 2, 450
        ph = (gs["t"] % 0.6) / 0.6
        pygame.draw.circle(surf, WHITE, (cx, cy), int(14 + 22 * ph), 3)
        pygame.draw.circle(surf, OUTLINE, (cx, cy), 12)
        pygame.draw.circle(surf, WHITE, (cx, cy), 9)
        return
    text(surf, str(gs["score"]), 72, BASE_W / 2, 64)
