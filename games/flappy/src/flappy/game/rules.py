"""
Flappy's progression data: trophies, lifetime currency, bird skins, run summary lines.
Pure data plus predicates, so balancing the game never touches engine code.
"""

# (id, name, description, predicate(run_stats, lifetime_stats)) -- checked every 0.5 s and at run end
ACHIEVEMENTS = [
    ("first",     "Liftoff",        "Pass your first pipe",          lambda r, L: r["pipes"] >= 1),
    ("score10",   "Frequent Flyer", "Score 10 in one run",           lambda r, L: r["score"] >= 10),
    ("score25",   "Sky Pilot",      "Score 25 in one run",           lambda r, L: r["score"] >= 25),
    ("score50",   "Ace",            "Score 50 in one run",           lambda r, L: r["score"] >= 50),
    ("score100",  "Legend",         "Score 100 in one run",          lambda r, L: r["score"] >= 100),
    ("close5",    "Feather Touch",  "5 close calls in one run",      lambda r, L: r["close"] >= 5),
    ("survive60", "Endurance",      "Stay airborne for 60 seconds",  lambda r, L: r["time"] >= 60),
    ("regular",   "Regular",        "Play 10 games",                 lambda r, L: L.get("games", 0) >= 10),
    ("streak3",   "Habit",          "Play 3 days in a row",          lambda r, L: L.get("streak", 0) >= 3),
    ("migrate",   "Migration",      "Pass 500 pipes in total",       lambda r, L: L.get("total", 0) + r["pipes"] >= 500),
]

# lifetime currency = pipes passed, summed over all runs -> every run, even a 2-pipe one,
# moves you toward the next bird skin.
CURRENCY  = ("pipes", "pipes passed")

# run stat whose all-time best is kept in L["best_close"] and shown on the scores screen
LIFE_BEST = ("close", "most close calls")

# (name, lifetime pipes needed, (body colour, wing colour)) -- spaced roughly geometrically
SKINS = [("Canary", 0,    ((255, 214, 64),  (240, 160, 40))),
         ("Robin",  50,   ((235, 90, 70),   (170, 50, 50))),
         ("Bluejay", 150, ((80, 160, 255),  (40, 90, 200))),
         ("Parrot", 400,  ((90, 220, 110),  (40, 150, 70))),
         ("Phoenix", 1000, ((255, 130, 40), (230, 50, 140)))]

# lines on the game-over screen: (key, label, formatter)
RUN_SUMMARY = [("close", "close calls", lambda r: r["close"]),
               ("flaps", "flaps", lambda r: r["flaps"]),
               ("time", "time", lambda r: "%ds" % r["time"])]
