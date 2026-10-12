"""
Turns SDL events into one clean input frame per tick.
Why: Android sends each touch twice (FINGER* and MOUSE*), and the game must see
exactly one press per touch.
"""

import pygame

from flappy.engine.display import finger_to_logical, phys_to_logical
from flappy.engine.state import APP

DOWN_DEBOUNCE_MS = 80       # a 2nd 'down' this soon and this close = the same touch reported twice

DOWN_DEBOUNCE_PX = 30

# lifecycle events differ between pygame/SDL versions -> resolve with getattr
_BG_EVENTS = {getattr(pygame, n) for n in ("APP_WILLENTERBACKGROUND", "APP_DIDENTERBACKGROUND",
                                            "WINDOWFOCUSLOST", "WINDOWMINIMIZED") if hasattr(pygame, n)}

_FG_EVENTS = {getattr(pygame, n) for n in ("APP_DIDENTERFOREGROUND", "WINDOWFOCUSGAINED",
                                            "WINDOWRESTORED") if hasattr(pygame, n)}

_BACK_KEYS = {pygame.K_ESCAPE, getattr(pygame, "K_AC_BACK", -999)}

def collect_input():
    """Drain the SDL queue into one normalized frame of input:
         ptr  : [{'type': 'down'|'move'|'up', 'x', 'y'}]  in logical coords
         keys : [pygame KEYDOWN events] (non-back keys)
         back, quit : bool;  life : 'bg' | 'fg' | None
    Android reports one touch as BOTH a FINGER* event and a synthesized MOUSE* event.
    Policy: per frame, use mouse events if any arrived (they are logical-mapped under
    SCALED and exist on desktop too), else finger events; then debounce 'down's so a
    twin arriving one frame later is dropped."""
    mouse, finger, keys = [], [], []
    back = quit_ = False
    life = None
    for e in pygame.event.get():
        t = e.type
        if t == pygame.QUIT:
            quit_ = True
        elif t == pygame.KEYDOWN:
            if e.key in _BACK_KEYS:
                back = True
            else:
                keys.append(e)
        elif t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and getattr(e, "button", 1) == 1:
            x, y = e.pos if APP["scaled"] else phys_to_logical(*e.pos)
            mouse.append({"type": "down" if t == pygame.MOUSEBUTTONDOWN else "up", "x": x, "y": y})
        elif t == pygame.MOUSEMOTION and e.buttons and e.buttons[0]:
            x, y = e.pos if APP["scaled"] else phys_to_logical(*e.pos)
            mouse.append({"type": "move", "x": x, "y": y})
        elif t in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
            x, y = finger_to_logical(e)
            kind = {pygame.FINGERDOWN: "down", pygame.FINGERUP: "up"}.get(t, "move")
            finger.append({"type": kind, "x": x, "y": y})
        elif t in _BG_EVENTS:
            life = "bg"
        elif t in _FG_EVENTS:
            life = "fg"
    ptr = mouse if mouse else finger
    out = []
    now = pygame.time.get_ticks()
    for ev in ptr:
        if ev["type"] == "down":
            lx, ly, lt = APP["last_down"]
            if now - lt < DOWN_DEBOUNCE_MS and abs(ev["x"] - lx) + abs(ev["y"] - ly) < DOWN_DEBOUNCE_PX:
                continue
            APP["last_down"] = (ev["x"], ev["y"], now)
        out.append(ev)
    return {"ptr": out, "keys": keys, "back": back, "quit": quit_, "life": life}
