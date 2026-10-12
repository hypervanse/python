"""
Flappy: the game-specific half of the project.

The engine (flappy/engine) calls into this package through the names listed below. To make a
different game, replace this package and keep these names: the engine stays unchanged.

Contract (what the engine calls):
  state.game_new(skin)            -> run state dict gs (score, over, phase, stats, ...)
  state.game_input(gs, ev)        pointer events during play: {'type', 'x', 'y'} in logical px
  state.game_key(gs, e)           KEYDOWN events during play (desktop testing)
  physics.game_update(gs, dt)     advance one step; set gs['over'] = True when the run ends
  draw.game_bg(surf, t)           backdrop, drawn first, never shaken
  draw.game_draw(surf, gs)        world layer, gets the screen shake
  draw.game_hud(surf, gs)         score and HUD, never shaken
  bot.game_bot(gs)                autopilot events for the self-test and the screenshot tool
  rules.ACHIEVEMENTS, CURRENCY, LIFE_BEST, SKINS, RUN_SUMMARY   data tables
  sfx.GAME_SFX                    extra sound builders, merged into the sound bank

Run state machine (gs["phase"]):
  ready   the bird hovers on a sine bob and the world scrolls; no gravity. The first tap
          flaps AND starts the run, so the player's first tap is never wasted.
  play    gravity, pipes spawned by distance, scoring, collisions.
  dead    pipes freeze and the bird tumbles in slow motion. gs["over"] = True hands control
          to the engine: a 1.3 s death beat, then the initials screen (top-N score) or the
          game-over screen.
"""
