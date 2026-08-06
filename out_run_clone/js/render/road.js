// Pseudo-3D road projection & drawing. Segments are projected from camera
// space to screen space and painted back-to-front (nearest first) with a
// running Y-clip, which is what naturally hides road behind hill crests.

import { project } from '../utils/math.js';
import { SEGMENT_LENGTH } from '../constants.js';

function rumbleWidth(projectedWidth, lanes) {
  return projectedWidth / Math.max(6, 2 * lanes);
}

function laneMarkerWidth(projectedWidth, lanes) {
  return projectedWidth / Math.max(32, 8 * lanes);
}

function polygon(ctx, x1, y1, x2, y2, x3, y3, x4, y4, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.lineTo(x3, y3);
  ctx.lineTo(x4, y4);
  ctx.closePath();
  ctx.fill();
}

function drawSegmentSlice(ctx, width, lanes, x1, y1, w1, x2, y2, w2, color, fog) {
  const r1 = rumbleWidth(w1, lanes);
  const r2 = rumbleWidth(w2, lanes);
  const l1 = laneMarkerWidth(w1, lanes);
  const l2 = laneMarkerWidth(w2, lanes);

  ctx.fillStyle = color.grass;
  ctx.fillRect(0, y2, width, y1 - y2);

  polygon(ctx, x1 - w1 - r1, y1, x1 - w1, y1, x2 - w2, y2, x2 - w2 - r2, y2, color.rumble);
  polygon(ctx, x1 + w1 + r1, y1, x1 + w1, y1, x2 + w2, y2, x2 + w2 + r2, y2, color.rumble);
  polygon(ctx, x1 - w1, y1, x1 + w1, y1, x2 + w2, y2, x2 - w2, y2, color.road);

  if (color.lane) {
    const lanaW1 = w1 * 2 / lanes;
    const lanaW2 = w2 * 2 / lanes;
    let lanex1 = x1 - w1 + lanaW1;
    let lanex2 = x2 - w2 + lanaW2;
    for (let lane = 1; lane < lanes; lane++) {
      polygon(ctx, lanex1 - l1 / 2, y1, lanex1 + l1 / 2, y1, lanex2 + l2 / 2, y2, lanex2 - l2 / 2, y2, color.lane);
      lanex1 += lanaW1;
      lanex2 += lanaW2;
    }
  }

  if (fog < 1) {
    ctx.globalAlpha = 1 - fog;
    ctx.fillStyle = '#e8f0f5';
    ctx.fillRect(0, y2, width, y1 - y2);
    ctx.globalAlpha = 1;
  }
}

// 1 = fully clear (near camera), approaches 0 towards the draw-distance horizon.
export function fogAt(depthIndex, drawDistance, density) {
  const t = depthIndex / drawDistance;
  return Math.max(0, Math.min(1, Math.exp(-density * t * t)));
}

// Projects an arbitrary world point (given as a lateral road-width fraction,
// absolute world Z, and elevation) using the same camera parameters a
// segment was projected with. Lets roadside sprites / traffic cars line up
// with the road even mid-curve.
export function projectPoint(xFraction, worldZ, worldY, camX, camY, camZ, cameraDepth, width, height, roadWidth) {
  const p = { world: { x: xFraction * roadWidth, y: worldY, z: worldZ }, camera: {}, screen: {} };
  project(p, camX, camY, camZ, cameraDepth, width, height, roadWidth);
  return p.screen;
}

// Renders the visible road slice and invokes onSegment for every segment
// (farthest-to-nearest) so caller code can layer roadside objects, traffic,
// etc. at the correct point in the painter's algorithm.
export function renderRoad(ctx, opts) {
  const {
    segments, trackLength, position, playerX, playerY,
    cameraHeight, cameraDepth, fogDensity, drawDistance,
    width, height, roadWidth, lanes, findSegment, onSegment,
  } = opts;

  const baseSegment = findSegment(position);
  const basePercent = (position % SEGMENT_LENGTH) / SEGMENT_LENGTH;
  let maxy = height;
  let x = 0;
  let dx = -(baseSegment.curve * basePercent);

  const cameraX = playerX * roadWidth;
  const cameraZ = position;
  const camY = cameraHeight + playerY;

  for (let n = 0; n < drawDistance; n++) {
    const segment = segments[(baseSegment.index + n) % segments.length];
    segment.looped = segment.index < baseSegment.index;
    segment.fog = fogAt(n, drawDistance, fogDensity);
    segment.clip = maxy;
    segment.visible = false;

    const zOffset = segment.looped ? trackLength : 0;
    const p1CamX = cameraX - x;
    const p1CamZ = cameraZ - zOffset;

    project(segment.p1, p1CamX, camY, p1CamZ, cameraDepth, width, height, roadWidth);
    project(segment.p2, cameraX - x - dx, camY, p1CamZ, cameraDepth, width, height, roadWidth);

    // Stash the camera params used for THIS segment so onSegment can project
    // roadside sprites / cars that live at this depth with matching curve offset.
    segment.projCamX = p1CamX;
    segment.projCamY = camY;
    segment.projCamZ = p1CamZ;

    x += dx;
    dx += segment.curve;

    segment.screenX1 = segment.p1.screen.x;
    segment.screenY1 = segment.p1.screen.y;
    segment.screenW1 = segment.p1.screen.w;
    segment.screenX2 = segment.p2.screen.x;
    segment.screenY2 = segment.p2.screen.y;
    segment.screenW2 = segment.p2.screen.w;
    segment.scale = segment.p2.screen.scale;

    if (segment.p1.camera.z <= cameraDepth) continue; // behind camera
    if (segment.screenY2 >= segment.screenY1) continue; // occluded by nearer segment
    if (segment.screenY1 >= maxy) continue;

    drawSegmentSlice(
      ctx, width, lanes,
      segment.screenX1, segment.screenY1, segment.screenW1,
      segment.screenX2, segment.screenY2, segment.screenW2,
      segment.color, segment.fog,
    );

    maxy = segment.screenY1;
    segment.visible = true;
  }

  // Sprites/traffic are painted farthest-to-nearest so nearer objects
  // correctly overlap farther ones.
  for (let n = drawDistance - 1; n >= 0; n--) {
    const segment = segments[(baseSegment.index + n) % segments.length];
    if (onSegment) onSegment(segment, n);
  }
}
