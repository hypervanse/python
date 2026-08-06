import { CAMERA_HEIGHT, CAMERA_DEPTH, PLAYER_Z } from '../constants.js';

// Tracks camera height/lookahead plus a decaying shake offset triggered on
// crashes.
export class Camera {
  constructor() {
    this.height = CAMERA_HEIGHT;
    this.depth = CAMERA_DEPTH;
    this.playerZ = PLAYER_Z;
    this.shake = 0;
  }

  triggerShake(amount = 18) {
    this.shake = amount;
  }

  update(dt) {
    if (this.shake > 0) {
      this.shake = Math.max(0, this.shake - dt * 40);
    }
  }

  shakeOffset() {
    if (this.shake <= 0) return { x: 0, y: 0 };
    return {
      x: (Math.random() - 0.5) * this.shake,
      y: (Math.random() - 0.5) * this.shake,
    };
  }
}
