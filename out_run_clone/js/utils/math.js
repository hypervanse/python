// Interpolation, easing, and small numeric helpers used across the engine.

export function clamp(value, min, max) {
  return Math.max(min, Math.min(value, max));
}

export function lerp(a, b, t) {
  return a + (b - a) * t;
}

export function easeIn(a, b, percent) {
  return a + (b - a) * Math.pow(percent, 2);
}

export function easeOut(a, b, percent) {
  return a + (b - a) * (1 - Math.pow(1 - percent, 2));
}

export function easeInOut(a, b, percent) {
  return a + (b - a) * (-Math.cos(percent * Math.PI) / 2 + 0.5);
}

export function percentRemaining(n, total) {
  return (n % total) / total;
}

export function accelerate(v, accel, dt) {
  return v + accel * dt;
}

// Deterministic PRNG (mulberry32) so stage layouts are reproducible per seed.
export class SeededRandom {
  constructor(seed) {
    this.state = seed >>> 0;
  }

  next() {
    let t = (this.state += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  range(min, max) {
    return min + this.next() * (max - min);
  }

  pick(arr) {
    return arr[Math.floor(this.next() * arr.length) % arr.length];
  }
}

// Projects a world-space point (relative to camera) into screen space.
export function project(p, cameraX, cameraY, cameraZ, cameraDepth, width, height, roadWidth) {
  p.camera.x = (p.world.x || 0) - cameraX;
  p.camera.y = (p.world.y || 0) - cameraY;
  p.camera.z = (p.world.z || 0) - cameraZ;
  p.screen.scale = cameraDepth / p.camera.z;
  p.screen.x = Math.round((width / 2) + (p.screen.scale * p.camera.x * width / 2));
  p.screen.y = Math.round((height / 2) - (p.screen.scale * p.camera.y * height / 2));
  p.screen.w = Math.round(p.screen.scale * roadWidth * width / 2);
}
