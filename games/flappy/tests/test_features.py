"""
Feature gate: every feature the skill requires must exist somewhere in the package.

This reads the source text, not the running program, so a feature that was deleted fails here
even when the self-test happens not to exercise it. The patterns match the skill's check_game.py.
"""

import pathlib
import re

import pytest

PKG = pathlib.Path(__file__).resolve().parents[1] / "src" / "flappy"
SOURCE = "\n".join(p.read_text(encoding="utf-8") for p in sorted(PKG.rglob("*.py")))

REQUIRED = [
    ("PCM synthesis into mixer Sounds",   r"mixer\.Sound\(\s*buffer\s*="),
    ("reads back the real mixer format",  r"mixer\.get_init\(\)"),
    ("reserved music channels",           r"set_reserved\("),
    ("procedural music step sequencer",   r"def music_update\("),
    ("adaptive music intensity",          r"def set_intensity\("),
    ("SQLite persistence",                r"import sqlite3"),
    ("high-score table query",            r"ORDER BY\s+score\s+DESC"),
    ("arcade initials entry",             r"initials"),
    ("pause state",                       r"[\"']pause[\"']"),
    ("settings (music and sfx volume)",   r"music_vol"),
    ("Android back key",                  r"K_AC_BACK"),
    ("background/foreground lifecycle",   r"APP_WILLENTERBACKGROUND|WINDOWFOCUSLOST"),
    ("audio paused when backgrounded",    r"mixer\.pause\(\)"),
    ("touch input (FINGER events)",       r"FINGERDOWN"),
    ("logical-resolution scaling",        r"SCALED"),
    ("dt-based timing with a clamp",      r"DT_MAX"),
    ("trophies",                          r"ACHIEVEMENTS"),
    ("lifetime stats persisted",          r"kv_set\(\s*[\"']life[\"']"),
    ("headless self-test entry point",    r"--selftest"),
]
FORBIDDEN = [
    ("image file loads",                  r"pygame\.image\.load\("),
    ("sound or music file loads",         r"mixer\.Sound\(\s*[\"']|mixer\.music\.load\("),
    ("numpy import (not on Pydroid)",     r"^\s*(import|from)\s+numpy\b"),
]


@pytest.mark.parametrize("label,pattern", REQUIRED)
def test_required_feature_is_present(label, pattern):
    assert re.search(pattern, SOURCE, re.M), "missing: " + label


@pytest.mark.parametrize("label,pattern", FORBIDDEN)
def test_forbidden_thing_is_absent(label, pattern):
    assert not re.search(pattern, SOURCE, re.M), "found: " + label
