# FLAPPY: a Flappy Bird clone for Pydroid 3

`flappy.py` is one self-contained Python file. It needs only `pygame` and the
standard library, and it loads no image or sound files:

- every sprite is drawn with `pygame.draw`
- every sound effect and the music are synthesized into PCM buffers at startup
- scores, settings and trophies are stored in SQLite

## Running it

| where | how |
|---|---|
| Pydroid 3 (Android) | Open `flappy.py` and press the yellow ▶ button. Pygame is already installed. |
| Desktop | `pip install pygame`, then `python3 flappy.py` |
| Headless self-test | `python3 flappy.py --selftest` runs the menus, play under autopilot, pause/resume, background, death, initials, leaderboard and settings persistence. Exit code 0 means all 18 checks passed. |

The first launch spends 1–3 s on a phone synthesizing audio. A progress bar
shows during that time, and the event queue keeps being pumped so Android
doesn't flag the app as frozen.

## Controls

| action | touch | keyboard (desktop) |
|---|---|---|
| flap / start the run | tap anywhere | `SPACE`, `UP`, `W` |
| pause | ⏸ button (top right), or Android **back** | `P` or `ESC` |
| menus | tap the buttons | `SPACE` / `ENTER` = play or retry |

**Why taps register on press, not release:** waiting for the release adds
about 100 ms of latency. In a timing game you can feel that. Menu buttons
work the other way and fire on release, so you can cancel a menu tap by
sliding your finger off the button.

**Why `MOUSEBUTTONDOWN` and `FINGERDOWN` don't cause double flaps:** Android
reports a single touch twice: once as a `FINGERDOWN` and once as a synthesized
`MOUSEBUTTONDOWN`. `collect_input()` handles this in two steps:

1. Within each frame, it uses mouse events if there are any and falls back to
   finger events otherwise.
2. It drops a second "down" that arrives within 80 ms and 30 px of the first.

So one tap always produces exactly one flap.

## State machine

```
 app modes (section 5/7)          game phases inside "play" (section 6)
 ------------------------          ------------------------------------
 title --PLAY--> play  ---------->  READY   bird hovers on a sine bob, no gravity
                  |                   | first tap = flap + start
                  |                   v
                  |                 PLAYING gravity, pipes, scoring, collision
                  |                   | hit pipe / ground
                  |                   v
                  |                 DEAD    pipes freeze, bird tumbles (slow-mo beat 1.3 s)
                  v
 initials (if top-10) -> scores  /  over (GAME OVER: score, best, run summary)
                  \___________ RETRY / tap -> new run ____________/
 pause <-> play   (button, back key, or app sent to background; resume = 3-2-1 countdown)
```

**Why the first tap in READY also flaps:** if that tap only started the
run, the bird would begin falling right away and your first deliberate tap
would already be a correction.

## Tuning the difficulty (section 0 of `flappy.py`)

Units are logical pixels (the canvas is 360×640) and seconds.

| knob | default | raise it → | lower it → |
|---|---|---|---|
| `GRAVITY` | 1500 px/s² | heavier bird, faster falls, harder | floatier, easier |
| `FLAP_V` | 440 px/s | each tap lifts higher | shorter hops, more taps needed |
| `MAX_FALL` | 620 px/s | missed taps punish harder | more time to recover |
| `GAP_START` | 168 px | easier opening | harder opening |
| `GAP_MIN` | 122 px | easier late game | harder late game |
| `GAP_SHRINK` | 1.5 px/pipe | reaches the minimum gap sooner | gentler ramp |
| `SPEED_START` | 140 px/s | less reaction time | more |
| `SPEED_RAMP` / `SPEED_MAX` | 1.6 px/s per pipe / 215 | faster ramp / higher ceiling | gentler ramp |
| `PIPE_SPACING` | 215 px | more air between pipes, easier | denser pipes |
| `GAP_JUMP_MAX` | 190 px | allows bigger height swings between pipes | smoother course |
| `HITBOX_HALF` | 10 px | less forgiving | more forgiving (the drawn bird has radius 14) |

### Why these numbers suit touch

- **One flap rises `FLAP_V² / (2·GRAVITY)` ≈ 65 px and reaches its apex in
  `FLAP_V / GRAVITY` ≈ 0.29 s.** Few people tap faster than about 6–7 Hz for
  long. Each tap has to do real work, so the game never turns into a test of
  how fast you can mash.
- **A tap sets the velocity instead of adding to it.** A tap while diving
  hard lifts you exactly as much as a tap while hovering. Every tap behaves
  the same way, which is what makes the timing learnable.
- **Pipes spawn by distance, not on a timer.** Spacing stays at exactly
  `PIPE_SPACING` px even as the speed ramps up or a frame hitches.
- **The gap centre moves by at most `GAP_JUMP_MAX` between pipes.** That
  guarantees every pipe pair can physically be reached.
- **Physics are dt-based and clamped by `DT_MAX = 1/30 s`.** The game plays
  the same on 60, 90 and 120 Hz screens. After a garbage-collection pause or
  an app switch, the bird can't tunnel through a pipe.

## Scoring, collisions and rendering

- **Score:** +1 when a pipe pair's centre line passes the bird's centre.
- **Collision:** the bird uses a square hitbox. Each pipe pair is four
  rectangles: top body, top lip, bottom lip, bottom body. `pipe_rects()`
  produces them, and both the drawing code and the collision code use that
  same function, so what you see is exactly what kills you. The top pipe
  extends 2000 px above the screen, so you can't cheat by flying over it.
  The ground line is also lethal.
- **Close calls:** when you pass a pipe with 9 px of clearance or less, it
  counts as a close call. You get a rising-pitch chime and a stat that one
  trophy is based on. Close calls don't change the score.
- **Performance:** the sky, skyline, clouds, ground strip and bird frames
  are each rendered to a Surface once. Each frame only blits those Surfaces
  and draws the pipes. Pipes that leave the screen are removed every frame
  by rebuilding the list.

## The layer around the game

This is what makes it feel finished rather than like a demo.

- **Sound:** flap whoosh, point ding, hit thump, fall glide, a rising chime
  on close calls, a milestone fanfare at 10, 25, 50 and 100, and the menu,
  trophy and record jingles.
- **Adaptive music:** each run gets a freshly generated tune. It gets denser
  at a score of 10 and again at 25. The game-over screen switches to a calm
  mood, and pause drops the music to its ambient layer.
- **Top-10 leaderboard with 3-letter arcade initials:** the initials are
  pre-filled with the last ones you used, and your new row is highlighted.
- **10 trophies**, which can pop up in the middle of a run.
- **5 bird skins**, unlocked by the lifetime number of pipes passed (0, 50,
  150, 400, 1000). You cycle through them on the title screen.
- **Daily streak and lifetime stats.**
- **Settings:** music volume, SFX volume, screen shake on or off, and a
  reset-scores option that only goes through if you tap it twice.

## What is saved, and where

Everything goes into `~/.pydroid_games/flappy.sqlite3`. In Pydroid 3, `~`
is the app's private storage, which persists between launches. The folder a
script is opened from may be only a temporary copy.

The file contains:

- the high-score table
- your settings
- lifetime stats: games played, play time, best score, total pipes, streak,
  last initials
- unlocked trophies

SQLite writes are atomic. If Android kills the app in the middle of a save,
the scores survive. A JSON file could be corrupted in the same situation.

## Verification status

- **Verified headless:** all 18 self-test checks pass. The static feature
  gate passes. Screenshots of the title, ready, play and initials screens were
  inspected for overlaps. A naive autopilot that just flaps below the gap
  centre scored between 24 and 101 over five random seeds, so the course is
  playable all the way to the minimum gap.
- **Not verified:** how it plays on a real phone. That includes touch
  latency, audio latency on your particular device, and frame rate on a slow
  phone. Tune `GRAVITY`, `FLAP_V` and `GAP_START` to taste once you've played
  it on a device.
