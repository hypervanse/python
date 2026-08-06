# 🏎️ OUT RUN — Arcade Clone Build Plan

> A faithful browser-based recreation of Sega's 1986 Out Run arcade game using HTML5 Canvas and vanilla JavaScript. No frameworks, no dependencies — just pure pseudo-3D driving bliss.

This document is the design/build plan for the `out_run_clone/` project. The current implementation covers the pseudo-3D road engine (curves + hills), player physics with gear shifting, procedural roadside sprites and traffic with collision detection, the full 15-stage branching pyramid with fork choices, a HUD, title/radio-select/game-over/course-clear screens, and Web-Audio-based engine sound, procedural radio music, and SFX — all with keyboard and touch controls.

See the project README for how to run it. The sections below are the original design reference used while building it.

## Tech Stack
- **Rendering**: HTML5 `<canvas>` (2D context)
- **Logic**: Vanilla JavaScript (ES modules)
- **Styling**: Vanilla CSS
- **Audio**: Web Audio API (procedural — no external audio files)
- **Assets**: Procedurally drawn canvas sprites (no external image files)

## Architecture

```
out_run_clone/
├── index.html              # Entry point
├── index.css               # Global styles, CRT/retro effects
├── js/
│   ├── main.js              # Bootstrap, game loop, state machine
│   ├── constants.js         # All tuning constants in one place
│   ├── render/
│   │   ├── road.js          # Pseudo-3D road projection & drawing
│   │   ├── background.js    # Parallax sky/horizon/ground layers
│   │   ├── sprites.js       # Procedural sprite drawing/scaling/positioning
│   │   └── hud.js           # Speedometer, timer, score, gear indicator
│   ├── game/
│   │   ├── player.js        # Player car: physics, steering, acceleration
│   │   ├── traffic.js       # AI traffic cars: spawning, movement, lanes
│   │   ├── collision.js     # Collision detection (car↔car, car↔roadside)
│   │   ├── stages.js        # Stage pyramid, theming, track generation
│   │   └── camera.js        # Camera height/depth, crash screen-shake
│   ├── audio/
│   │   └── audio.js         # Engine sound, procedural radio music, SFX
│   └── utils/
│       ├── math.js          # Interpolation, easing, projection, seeded RNG
│       └── input.js         # Keyboard/touch input handler
└── BUILD.md                 # This file
```

## Controls

| Key | Action |
|---|---|
| `↑` / `W` | Accelerate |
| `↓` / `S` | Brake |
| `←` / `A` | Steer left / choose left fork |
| `→` / `D` | Steer right / choose right fork |
| `Space` | Shift gear (toggle Low ↔ High) |
| `Enter` | Start / select |
| `1` / `2` / `3` | Quick-select radio station |

Touch controls (steer, gas, brake, gear, start) appear automatically on coarse-pointer (mobile/tablet) devices.

## Stage Pyramid

15 stages across 5 rows, forking left/right at the end of each non-goal stage (adjacent parents share a child, matching the original arcade map):

```
Row 1:  Coconut Beach
Row 2:  Gateway · Devil's Canyon
Row 3:  Desert · Alps · Cloudy Mountain
Row 4:  Wilderness · Old Capital · Wheat Field · Seaside Town
Row 5:  Vineyard(A) · Death Valley(B) · Desolation Hill(C) · Autobahn(D) · Lakeside(E)
```

Reaching a goal stage's end completes the run; running out of time coasts the car to a stop and ends the game.

## Stretch ideas not yet implemented
- Gamepad support
- Night mode / weather effects
- Two-road (wide highway) rendering
- Replay system / online leaderboard
