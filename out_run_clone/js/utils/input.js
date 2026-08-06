// Keyboard + touch input handler. Exposes a small boolean action map so the
// rest of the game never touches raw key codes.

const KEY_MAP = {
  ArrowUp: 'accelerate',
  KeyW: 'accelerate',
  ArrowDown: 'brake',
  KeyS: 'brake',
  ArrowLeft: 'left',
  KeyA: 'left',
  ArrowRight: 'right',
  KeyD: 'right',
  Space: 'gear',
  Enter: 'start',
  Digit1: 'radio1',
  Digit2: 'radio2',
  Digit3: 'radio3',
};

export class Input {
  constructor(target = window) {
    this.state = {};
    this.pressed = {}; // edge-triggered, cleared each frame via consume()
    this._down = (e) => {
      const action = KEY_MAP[e.code];
      if (!action) return;
      if (['accelerate', 'brake', 'left', 'right', 'gear', 'start'].includes(action)) e.preventDefault();
      if (!this.state[action]) this.pressed[action] = true;
      this.state[action] = true;
    };
    this._up = (e) => {
      const action = KEY_MAP[e.code];
      if (!action) return;
      this.state[action] = false;
    };
    target.addEventListener('keydown', this._down);
    target.addEventListener('keyup', this._up);

    this._setupTouch();
  }

  _setupTouch() {
    this.touch = { left: false, right: false, accelerate: false, brake: false, gear: false, start: false };
    const el = document.getElementById('touch-controls');
    if (!el) return;
    const bind = (id, action) => {
      const btn = document.getElementById(id);
      if (!btn) return;
      const on = (e) => { e.preventDefault(); this.touch[action] = true; if (!this.state[action]) this.pressed[action] = true; this.state[action] = true; };
      const off = (e) => { e.preventDefault(); this.touch[action] = false; this.state[action] = false; };
      btn.addEventListener('touchstart', on, { passive: false });
      btn.addEventListener('touchend', off, { passive: false });
      btn.addEventListener('touchcancel', off, { passive: false });
      btn.addEventListener('mousedown', on);
      btn.addEventListener('mouseup', off);
      btn.addEventListener('mouseleave', off);
    };
    bind('btn-left', 'left');
    bind('btn-right', 'right');
    bind('btn-accel', 'accelerate');
    bind('btn-brake', 'brake');
    bind('btn-gear', 'gear');
    bind('btn-start', 'start');
  }

  isDown(action) {
    return !!this.state[action];
  }

  wasPressed(action) {
    return !!this.pressed[action];
  }

  consume() {
    this.pressed = {};
  }
}
