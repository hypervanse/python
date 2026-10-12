"""
SQLite persistence: scores, settings, lifetime stats and trophies.
Why SQLite: writes are atomic, so a process killed mid-save cannot corrupt the table,
and ORDER BY gives the leaderboard for free.
"""

import json
import os
import sqlite3
import time

from flappy.config import GAME_ID, TOP_N
from flappy.engine.state import APP

# Why SQLite and not a JSON/text file: writes are atomic (Android may kill the
# process at any moment; a half-written JSON file = lost scores), ORDER BY/LIMIT
# give the leaderboard for free, and the schema can be migrated with user_version.
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS scores(
    id INTEGER PRIMARY KEY, initials TEXT NOT NULL, score INTEGER NOT NULL,
    created REAL NOT NULL, extra TEXT);
CREATE INDEX IF NOT EXISTS scores_by_score ON scores(score DESC, created ASC);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS achievements(id TEXT PRIMARY KEY, unlocked REAL NOT NULL);
"""

DEFAULT_SETTINGS = {"music_vol": 0.6, "sfx_vol": 0.8, "shake": True}

def db_path():
    """Where the high-score database lives.

    Order: the <GAME_ID>_DB environment variable (the self-test sets it so real scores are
    never touched), then ~/.<GAME_ID>/<GAME_ID>.sqlite3.
    Why the home directory: it is private, persistent app storage in Pydroid 3, and it does
    not depend on which folder the project was copied to.
    Why NOT the working directory: on Android the working directory can be shared storage
    (/storage/emulated/0/...), where SQLite's file locking is not reliable."""
    env_name = GAME_ID.upper() + "_DB"                     # FLAPPY_DB for this game
    if os.environ.get(env_name):
        return os.environ[env_name]
    folder = os.path.join(os.path.expanduser("~"), "." + GAME_ID)
    try:
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, GAME_ID + ".sqlite3")
    except OSError:
        return ":memory:"       # home not writable: the game still plays, scores last this session

def db_open():
    try:
        con = sqlite3.connect(db_path())
        con.execute("SELECT 1")
    except sqlite3.Error:
        con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    ver = con.execute("PRAGMA user_version").fetchone()[0]
    # future migrations go here:  if ver < 2: con.execute("ALTER TABLE ..."); ...
    if ver < SCHEMA_VERSION:
        con.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
    con.commit()
    return con

def kv_get(key, default):
    row = APP["con"].execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    try:
        val = json.loads(row[0])
    except ValueError:
        return default
    if isinstance(default, dict):            # merge so newly added keys get defaults
        merged = dict(default)
        merged.update(val)
        return merged
    return val

def kv_set(key, value):
    APP["con"].execute("INSERT OR REPLACE INTO kv(key, value) VALUES(?, ?)", (key, json.dumps(value)))
    APP["con"].commit()

def db_top(n=TOP_N):
    return APP["con"].execute("SELECT id, initials, score, created FROM scores "
                              "ORDER BY score DESC, created ASC LIMIT ?", (n,)).fetchall()

def db_qualifies(score):
    if score <= 0:
        return False
    top = db_top()
    return len(top) < TOP_N or score > top[-1][2]

def db_add_score(initials, score, extra=None):
    cur = APP["con"].execute("INSERT INTO scores(initials, score, created, extra) VALUES(?,?,?,?)",
                             (initials, int(score), time.time(), json.dumps(extra or {})))
    APP["con"].commit()
    return cur.lastrowid

def db_rank(score_id):
    ids = [r[0] for r in db_top(1000)]
    return ids.index(score_id) + 1 if score_id in ids else None

def db_unlocked():
    return {r[0]: r[1] for r in APP["con"].execute("SELECT id, unlocked FROM achievements")}

def db_unlock(aid):
    APP["con"].execute("INSERT OR IGNORE INTO achievements(id, unlocked) VALUES(?, ?)", (aid, time.time()))
    APP["con"].commit()

def db_reset_scores():
    APP["con"].execute("DELETE FROM scores")
    APP["con"].commit()
