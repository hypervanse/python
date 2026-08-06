import {
  ACCEL_LOW, ACCEL_HIGH, BRAKE, DECEL, OFFROAD_DECEL, OFFROAD_LIMIT,
  MAX_SPEED_LOW, MAX_SPEED_HIGH, CENTRIFUGAL, STEER_SPEED, PLAYER_X_MAX,
  CRASH_DURATION, GEAR, KM_PER_WORLD_UNIT,
} from '../constants.js';
import { clamp, accelerate } from '../utils/math.js';

export class Player {
  constructor() {
    this.x = 0; // -1..1 within the road, can exceed for off-road
    this.speed = 0;
    this.gear = GEAR.LOW;
    this.crashed = false;
    this.crashTimer = 0;
    this.bounce = 0;
    this.steerDir = 0;
    this.grace = 0;
  }

  get maxSpeed() {
    return this.gear === GEAR.HIGH ? MAX_SPEED_HIGH : MAX_SPEED_LOW;
  }

  get speedKmh() {
    return Math.round(this.speed * KM_PER_WORLD_UNIT);
  }

  shiftGear() {
    this.gear = this.gear === GEAR.LOW ? GEAR.HIGH : GEAR.LOW;
  }

  get invulnerable() {
    return this.crashed || this.grace > 0;
  }

  crash() {
    if (this.crashed) return;
    this.crashed = true;
    this.crashTimer = CRASH_DURATION;
    this.speed *= 0.2;
    // Pull back toward the road and hold off further collision checks for a
    // moment so a crash near a fixed obstacle can't re-trigger every frame.
    this.x = clamp(this.x, -0.85, 0.85);
    this.grace = 1.2;
  }

  update(dt, input, curve, isOffRoad, forceStop = false) {
    if (this.grace > 0) this.grace = Math.max(0, this.grace - dt);

    if (this.crashed) {
      this.crashTimer -= dt;
      this.bounce = Math.sin(performance.now() / 40) * 4;
      this.speed = accelerate(this.speed, DECEL, dt);
      this.speed = Math.max(0, this.speed);
      if (this.crashTimer <= 0) {
        this.crashed = false;
        this.bounce = 0;
      }
      return;
    }

    this.steerDir = 0;
    if (!forceStop && input.isDown('left')) this.steerDir = -1;
    if (!forceStop && input.isDown('right')) this.steerDir = 1;

    if (forceStop) {
      this.speed = accelerate(this.speed, DECEL, dt);
      this.speed = clamp(this.speed, 0, this.maxSpeed);
      const speedPercent = this.speed / MAX_SPEED_HIGH;
      this.x -= (curve || 0) * speedPercent * CENTRIFUGAL * dt;
      this.x = clamp(this.x, -PLAYER_X_MAX, PLAYER_X_MAX);
      return;
    }

    if (input.isDown('accelerate')) {
      const accel = this.gear === GEAR.HIGH ? ACCEL_HIGH : ACCEL_LOW;
      this.speed = accelerate(this.speed, accel, dt);
    } else if (input.isDown('brake')) {
      this.speed = accelerate(this.speed, BRAKE, dt);
    } else {
      this.speed = accelerate(this.speed, DECEL, dt);
    }

    if (isOffRoad) {
      if (this.speed > OFFROAD_LIMIT) {
        this.speed = accelerate(this.speed, OFFROAD_DECEL, dt);
      }
      this.bounce = Math.sin(performance.now() / 25) * (2 + this.speed / MAX_SPEED_HIGH * 6);
    } else {
      this.bounce = 0;
    }

    this.speed = clamp(this.speed, 0, this.maxSpeed);

    const speedPercent = this.speed / MAX_SPEED_HIGH;
    this.x += this.steerDir * STEER_SPEED * speedPercent * dt;
    this.x -= (curve || 0) * speedPercent * CENTRIFUGAL * dt;
    this.x = clamp(this.x, -PLAYER_X_MAX, PLAYER_X_MAX);
  }
}
