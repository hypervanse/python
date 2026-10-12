"""
Window creation and logical-to-physical coordinate mapping.
Why SCALED: the game always draws BASE_W x BASE_H and SDL stretches that to any
phone screen, so layout code never needs the real pixel size.
"""

import os
import sys

import pygame

from flappy.config import BASE_H, BASE_W, BLACK
from flappy.engine.state import APP


def is_android():
    # Pydroid 3 exposes the Android environment; CPython-on-Android has getandroidapilevel
    return ("ANDROID_ROOT" in os.environ or "ANDROID_ARGUMENT" in os.environ
            or hasattr(sys, "getandroidapilevel"))

def open_display():
    """Prefer pygame.SCALED: draw at BASE_W x BASE_H, SDL upscales on the GPU with
    letterboxing, and mouse coordinates arrive already in logical space.
    Fallback: native-size window + our own CPU scaling of a logical canvas."""
    fs = pygame.FULLSCREEN if is_android() else 0
    try:
        screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.SCALED | fs)
        return screen, True
    except (pygame.error, AttributeError):
        size = (0, 0) if is_android() else (BASE_W, BASE_H)
        return pygame.display.set_mode(size, fs), False

def view_transform():
    """Scale k and offsets (ox, oy) of the logical canvas inside the physical window."""
    try:
        ww, wh = pygame.display.get_window_size()
    except (AttributeError, pygame.error):
        ww, wh = APP["screen"].get_size()
    k = min(ww / BASE_W, wh / BASE_H)
    return k, (ww - BASE_W * k) / 2.0, (wh - BASE_H * k) / 2.0

def phys_to_logical(px, py):
    k, ox, oy = view_transform()
    return (px - ox) / k, (py - oy) / k

def finger_to_logical(e):
    # FINGER* events carry normalized (0..1) window coords, never logical ones
    try:
        ww, wh = pygame.display.get_window_size()
    except (AttributeError, pygame.error):
        ww, wh = APP["screen"].get_size()
    return phys_to_logical(e.x * ww, e.y * wh)

def present():
    """Flip the frame. In the CPU fallback path, scale the logical canvas to the window."""
    if not APP["scaled"]:
        scr = APP["screen"]
        k, ox, oy = view_transform()
        scr.fill(BLACK)
        scr.blit(pygame.transform.scale(APP["canvas"], (int(BASE_W * k), int(BASE_H * k))), (int(ox), int(oy)))
    pygame.display.flip()
