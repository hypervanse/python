"""
Reusable UI kit: cached text, buttons, toasts, particles, popups and screen shake.
"""

import math
import random

import pygame

from flappy.config import BASE_H, BASE_W, BLACK, UI_ACCENT, UI_EDGE, UI_PANEL, WHITE
from flappy.engine.state import APP

_FONTS, _TXT = {}, {}

def font(size):
    f = _FONTS.get(size)
    if f is None:
        f = _FONTS[size] = pygame.font.SysFont(None, size)   # None = bundled font, always exists
    return f

def text(surf, s, size, x, y, color=WHITE, anchor="center", outline=BLACK):
    """Outlined text, rendered once per (string, size, colour) and cached:
    font.render is the most expensive thing a typical UI does per frame."""
    key = (s, size, color, outline)
    img = _TXT.get(key)
    if img is None:
        if len(_TXT) > 400:
            _TXT.clear()
        fg = font(size).render(s, True, color)
        if outline is None:
            img = fg
        else:
            bg = font(size).render(s, True, outline)
            img = pygame.Surface((fg.get_width() + 4, fg.get_height() + 4), pygame.SRCALPHA)
            for ox in (0, 2, 4):
                for oy in (0, 2, 4):
                    if (ox, oy) != (2, 2):
                        img.blit(bg, (ox, oy))
            img.blit(fg, (2, 2))
        _TXT[key] = img
    r = img.get_rect()
    setattr(r, anchor, (int(x), int(y)))
    surf.blit(img, r)
    return r

def button(x, y, w, h, label, action, style="primary"):
    """A button is plain data: rect + label + action string. Screens build their
    button list every frame; the same list drives both hit-testing and drawing."""
    return {"rect": pygame.Rect(int(x), int(y), int(w), int(h)), "label": label, "action": action, "style": style}

def vstack(items, top, w=230, h=54, gap=12):
    """Centred column of buttons. 54 logical px ~ 9 mm on a typical phone: comfortably tappable."""
    x = (BASE_W - w) // 2
    return [button(x, top + i * (h + gap), w, h, it[0], it[1], it[2] if len(it) > 2 else "primary")
            for i, it in enumerate(items)]

def draw_buttons(surf, btns):
    for b in btns:
        r = b["rect"].copy()
        pressed = APP["pressed"] is not None and APP["pressed"]["action"] == b["action"]
        if pressed:
            r.move_ip(0, 3)
        fill = {"primary": (60, 80, 170), "ghost": UI_PANEL, "danger": (150, 45, 55), "accent": (170, 120, 20)}[b["style"]]
        if pressed:
            fill = tuple(int(c * 0.75) for c in fill)
        if not pressed:
            pygame.draw.rect(surf, BLACK, r.move(0, 4), border_radius=12)       # drop shadow
        pygame.draw.rect(surf, fill, r, border_radius=12)
        pygame.draw.rect(surf, UI_EDGE, r, 2, border_radius=12)
        size = 34 if r.h >= 50 else 28
        text(surf, b["label"], size, r.centerx, r.centery)

def handle_buttons(btns, ev):
    """Fire on RELEASE inside the pressed button: lets a finger slide off to cancel,
    which is what mobile users expect from menus."""
    if ev["type"] == "down":
        for b in btns:
            if b["rect"].collidepoint(ev["x"], ev["y"]):
                APP["pressed"] = b
                return None
    elif ev["type"] == "up":
        p, APP["pressed"] = APP["pressed"], None
        if p is not None and p["rect"].collidepoint(ev["x"], ev["y"]):
            return p["action"]
    return None

def toast(title, sub="", color=UI_ACCENT):
    APP["toasts"].append({"title": title, "sub": sub, "color": color, "t": 0.0})

def burst(x, y, color, n=14, speed=160.0, life=0.6, size=3):
    for _ in range(n):
        a = random.uniform(0, 2 * math.pi)
        v = random.uniform(0.3, 1.0) * speed
        APP["particles"].append({"x": x, "y": y, "vx": math.cos(a) * v, "vy": math.sin(a) * v - 60,
                                 "t": 0.0, "life": life * random.uniform(0.7, 1.2), "c": color, "s": size})

def popup(s, x, y, color=WHITE, size=30):
    APP["popups"].append({"s": s, "x": x, "y": y, "t": 0.0, "c": color, "size": size})

def shake(amount):
    if APP["settings"]["shake"]:
        APP["shake"] = max(APP["shake"], amount)

def update_fx(dt):
    keep = []
    for p in APP["particles"]:
        p["t"] += dt
        if p["t"] < p["life"]:
            p["vy"] += 420 * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            keep.append(p)
    APP["particles"] = keep                      # rebinding frees dead particles immediately
    for p in APP["popups"]:
        p["t"] += dt
        p["y"] -= 40 * dt
    APP["popups"] = [p for p in APP["popups"] if p["t"] < 0.9]
    if APP["toasts"] and APP["mode"] not in TOAST_HOLD:
        APP["toasts"][0]["t"] += dt              # one at a time, queued
        if APP["toasts"][0]["t"] > 2.6:
            APP["toasts"].pop(0)
    APP["shake"] = max(0.0, APP["shake"] - 40 * dt)

def draw_fx(surf):
    for p in APP["particles"]:
        k = 1.0 - p["t"] / p["life"]
        pygame.draw.circle(surf, p["c"], (int(p["x"]), int(p["y"])), max(1, int(p["s"] * k + 0.5)))
    for p in APP["popups"]:
        text(surf, p["s"], p["size"], p["x"], p["y"], p["c"])

TOAST_HOLD = ("scores", "trophies", "settings")    # list screens: queue toasts until we leave

def draw_toast(surf):
    if not APP["toasts"] or APP["mode"] in TOAST_HOLD:
        return
    t = APP["toasts"][0]
    slide = min(1.0, t["t"] / 0.25, (2.6 - t["t"]) / 0.25)        # ease in / out
    r = pygame.Rect(20, int(-62 + 70 * slide), BASE_W - 40, 54)
    pygame.draw.rect(surf, UI_PANEL, r, border_radius=12)
    pygame.draw.rect(surf, t["color"], r, 2, border_radius=12)
    draw_trophy(surf, r.x + 28, r.centery, t["color"])
    text(surf, t["title"], 26, r.x + 54, r.y + 17, t["color"], "midleft")
    if t["sub"]:
        text(surf, t["sub"], 20, r.x + 54, r.y + 38, WHITE, "midleft")

def draw_trophy(surf, cx, cy, color):
    pygame.draw.polygon(surf, color, [(cx - 11, cy - 12), (cx + 11, cy - 12), (cx + 7, cy + 2), (cx - 7, cy + 2)])
    pygame.draw.rect(surf, color, (cx - 2, cy + 2, 4, 6))
    pygame.draw.rect(surf, color, (cx - 8, cy + 8, 16, 4))

def draw_panel(surf, rect):
    pygame.draw.rect(surf, UI_PANEL, rect, border_radius=14)
    pygame.draw.rect(surf, UI_EDGE, rect, 2, border_radius=14)

def dim(surf, alpha=150):
    d = pygame.Surface((BASE_W, BASE_H), pygame.SRCALPHA)
    d.fill((0, 0, 0, alpha))
    surf.blit(d, (0, 0))
