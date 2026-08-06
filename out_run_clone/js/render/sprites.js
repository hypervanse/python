// Procedurally-drawn vector sprites (trees, signs, rocks, buildings, cars).
// No external image assets — everything is drawn with canvas primitives and
// cached to an offscreen canvas per (type, variant, theme) the first time
// it's requested, then blitted+scaled like a normal sprite would be.

const cache = new Map();

function getCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.ceil(w));
  c.height = Math.max(1, Math.ceil(h));
  return c;
}

function drawTree(ctx, w, h, palette) {
  const trunkW = w * 0.12;
  ctx.fillStyle = palette.trunk || '#5a3a22';
  ctx.fillRect(w / 2 - trunkW / 2, h * 0.6, trunkW, h * 0.4);
  ctx.fillStyle = palette.leaf || '#0d7a0d';
  for (let i = 0; i < 3; i++) {
    const cy = h * (0.55 - i * 0.18);
    const r = w * (0.5 - i * 0.08);
    ctx.beginPath();
    ctx.ellipse(w / 2, cy, r, r * 0.85, 0, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawPalm(ctx, w, h, palette) {
  ctx.strokeStyle = palette.trunk || '#8a6a3a';
  ctx.lineWidth = w * 0.09;
  ctx.beginPath();
  ctx.moveTo(w * 0.5, h);
  ctx.quadraticCurveTo(w * 0.35, h * 0.55, w * 0.55, h * 0.15);
  ctx.stroke();
  ctx.fillStyle = palette.leaf || '#0d8a0d';
  const tipX = w * 0.55, tipY = h * 0.15;
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2;
    ctx.beginPath();
    ctx.moveTo(tipX, tipY);
    ctx.quadraticCurveTo(
      tipX + Math.cos(angle) * w * 0.5, tipY + Math.sin(angle) * h * 0.25 - h * 0.05,
      tipX + Math.cos(angle) * w * 0.65, tipY + Math.sin(angle) * h * 0.35,
    );
    ctx.quadraticCurveTo(tipX, tipY + h * 0.05, tipX, tipY);
    ctx.fill();
  }
}

function drawPine(ctx, w, h, palette) {
  ctx.fillStyle = palette.trunk || '#4a3222';
  ctx.fillRect(w / 2 - w * 0.05, h * 0.85, w * 0.1, h * 0.15);
  ctx.fillStyle = palette.leaf || '#1a5c3a';
  for (let i = 0; i < 4; i++) {
    const tierH = h * 0.28;
    const y = h * 0.15 + i * tierH * 0.62;
    const wgt = w * (0.55 - i * 0.09);
    ctx.beginPath();
    ctx.moveTo(w / 2, y);
    ctx.lineTo(w / 2 - wgt, y + tierH);
    ctx.lineTo(w / 2 + wgt, y + tierH);
    ctx.closePath();
    ctx.fill();
  }
}

function drawRock(ctx, w, h, palette) {
  ctx.fillStyle = palette.rock || '#8a7a6a';
  ctx.beginPath();
  ctx.moveTo(w * 0.05, h);
  ctx.lineTo(w * 0.1, h * 0.45);
  ctx.lineTo(w * 0.4, h * 0.1);
  ctx.lineTo(w * 0.75, h * 0.25);
  ctx.lineTo(w * 0.95, h * 0.6);
  ctx.lineTo(w * 0.9, h);
  ctx.closePath();
  ctx.fill();
}

function drawCactus(ctx, w, h, palette) {
  ctx.fillStyle = palette.leaf || '#2f8f4f';
  ctx.fillRect(w * 0.4, h * 0.15, w * 0.2, h * 0.85);
  ctx.fillRect(w * 0.08, h * 0.35, w * 0.2, h * 0.4);
  ctx.fillRect(w * 0.72, h * 0.25, w * 0.2, h * 0.5);
}

function drawSign(ctx, w, h, palette) {
  ctx.fillStyle = '#cccccc';
  ctx.fillRect(w * 0.46, h * 0.3, w * 0.08, h * 0.7);
  ctx.fillStyle = palette.sign || '#1155cc';
  ctx.fillRect(w * 0.05, 0, w * 0.9, h * 0.35);
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = Math.max(1, w * 0.02);
  ctx.strokeRect(w * 0.05, 0, w * 0.9, h * 0.35);
}

function drawBuilding(ctx, w, h, palette) {
  ctx.fillStyle = palette.wall || '#c9a67a';
  ctx.fillRect(0, h * 0.15, w, h * 0.85);
  ctx.fillStyle = palette.roof || '#8a4a3a';
  ctx.beginPath();
  ctx.moveTo(-w * 0.05, h * 0.18);
  ctx.lineTo(w / 2, 0);
  ctx.lineTo(w * 1.05, h * 0.18);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = palette.window || '#4a6a8a';
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 2; c++) {
      ctx.fillRect(w * (0.15 + c * 0.45), h * (0.32 + r * 0.22), w * 0.25, h * 0.14);
    }
  }
}

function drawWindmill(ctx, w, h, palette) {
  ctx.fillStyle = palette.wall || '#e8d9b0';
  ctx.beginPath();
  ctx.moveTo(w * 0.35, h);
  ctx.lineTo(w * 0.42, h * 0.35);
  ctx.lineTo(w * 0.58, h * 0.35);
  ctx.lineTo(w * 0.65, h);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = palette.blade || '#8a7a5a';
  ctx.lineWidth = w * 0.05;
  const cx = w / 2, cy = h * 0.32;
  for (let i = 0; i < 4; i++) {
    const a = (Math.PI / 2) * i + Math.PI / 6;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a) * w * 0.4, cy + Math.sin(a) * w * 0.4);
    ctx.stroke();
  }
}

const DRAWERS = {
  tree: drawTree,
  palm: drawPalm,
  pine: drawPine,
  rock: drawRock,
  cactus: drawCactus,
  sign: drawSign,
  building: drawBuilding,
  windmill: drawWindmill,
};

export function getSprite(type, palette = {}, w = 200, h = 300) {
  const key = `${type}:${JSON.stringify(palette)}:${w}x${h}`;
  if (cache.has(key)) return cache.get(key);
  const canvas = getCanvas(w, h);
  const ctx = canvas.getContext('2d');
  (DRAWERS[type] || drawTree)(ctx, w, h, palette);
  cache.set(key, canvas);
  return canvas;
}

// Draws a roadside sprite at screen position (x,y) = bottom-center, scaled
// by `scale`, offset sideways by `offset` road-widths (matches classic
// Outrun-style roadside object placement).
export function drawRoadsideSprite(ctx, sprite, x, y, scale, roadWidth, offset, destW, destH) {
  const spriteScale = scale * roadWidth / 2;
  const w = destW * spriteScale * 0.9;
  const h = destH * spriteScale * 0.9;
  const destX = x + (spriteScale * offset * destW) - (offset < 0 ? w : 0);
  const destY = y - h;
  ctx.drawImage(sprite, destX, destY, w, h);
}

export function drawTrafficCar(ctx, x, y, scale, width, color, type = 'sedan') {
  const w = width;
  const h = width * 0.62;
  ctx.save();
  ctx.translate(x, y);
  ctx.fillStyle = 'rgba(0,0,0,0.35)';
  ctx.beginPath();
  ctx.ellipse(0, h * 0.05, w * 0.42, h * 0.14, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = color;
  roundRect(ctx, -w / 2, -h * 0.85, w, h * 0.75, h * 0.18);
  ctx.fill();

  ctx.fillStyle = 'rgba(20,20,25,0.9)';
  if (type === 'truck') {
    roundRect(ctx, -w * 0.3, -h * 1.3, w * 0.6, h * 0.55, h * 0.08);
  } else {
    roundRect(ctx, -w * 0.32, -h * 1.15, w * 0.64, h * 0.42, h * 0.12);
  }
  ctx.fill();

  ctx.fillStyle = '#ffcc33';
  ctx.fillRect(-w * 0.42, -h * 0.55, w * 0.12, h * 0.14);
  ctx.fillRect(w * 0.3, -h * 0.55, w * 0.12, h * 0.14);
  ctx.restore();
}

export function drawPlayerCar(ctx, x, y, scale, steer, crashed, bounce) {
  const w = 420 * scale;
  const h = 260 * scale;
  ctx.save();
  ctx.translate(x, y + bounce);
  if (crashed) ctx.rotate(Math.sin(performance.now() / 60) * 0.6);
  else ctx.rotate(steer * 0.08);

  ctx.fillStyle = 'rgba(0,0,0,0.4)';
  ctx.beginPath();
  ctx.ellipse(0, h * 0.32, w * 0.46, h * 0.12, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = '#c81010';
  roundRect(ctx, -w / 2, -h * 0.25, w, h * 0.5, h * 0.15);
  ctx.fill();

  ctx.fillStyle = '#f4f4f4';
  roundRect(ctx, -w * 0.28, -h * 0.55, w * 0.56, h * 0.45, h * 0.1);
  ctx.fill();

  ctx.fillStyle = '#222';
  ctx.fillRect(-w * 0.5, h * 0.1, w * 0.15, h * 0.18);
  ctx.fillRect(w * 0.35, h * 0.1, w * 0.15, h * 0.18);

  ctx.fillStyle = '#ffe38a';
  ctx.fillRect(-w * 0.46, -h * 0.05, w * 0.1, h * 0.1);
  ctx.fillRect(w * 0.36, -h * 0.05, w * 0.1, h * 0.1);
  ctx.restore();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
