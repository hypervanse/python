// Parallax sky/hill/cloud layers. Purely procedural gradients + shapes,
// scrolled opposite to road curvature to sell the sense of turning.

function hillPath(ctx, width, height, baseY, amplitude, seedOffset, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(0, height);
  const points = 8;
  for (let i = 0; i <= points; i++) {
    const px = (i / points) * width;
    const py = baseY + Math.sin(i * 1.3 + seedOffset) * amplitude;
    ctx.lineTo(px, py);
  }
  ctx.lineTo(width, height);
  ctx.closePath();
  ctx.fill();
}

export function drawBackground(ctx, width, height, theme, skyOffset, hillOffset) {
  const t = theme;
  const horizon = height * 0.42;

  const grad = ctx.createLinearGradient(0, 0, 0, horizon);
  grad.addColorStop(0, t.skyTop);
  grad.addColorStop(1, t.skyBottom);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, width, horizon);

  // Sun/moon disc
  ctx.fillStyle = t.sun;
  ctx.beginPath();
  ctx.arc(width * 0.78, horizon * 0.55, height * 0.09, 0, Math.PI * 2);
  ctx.fill();

  // Clouds (simple parallax ellipses, wrap with skyOffset)
  ctx.fillStyle = t.cloud;
  for (let i = 0; i < 6; i++) {
    const baseX = (i * 260 - (skyOffset * 0.5) % 1560 + 1560 * 3) % 1560 - 260;
    const cy = horizon * (0.18 + (i % 3) * 0.12);
    ctx.globalAlpha = 0.8;
    ctx.beginPath();
    ctx.ellipse(baseX, cy, 70, 22, 0, 0, Math.PI * 2);
    ctx.ellipse(baseX + 40, cy + 6, 45, 16, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;

  // Distant hills / terrain silhouette layers, offset by curve-driven hillOffset
  hillPath(ctx, width, height, horizon * 0.92, height * 0.03, hillOffset * 0.001, t.hillFar);
  hillPath(ctx, width, height, horizon * 0.97, height * 0.045, hillOffset * 0.002 + 2, t.hillNear);

  // Ground fill below horizon (road renderer draws grass over this, but this
  // avoids a seam while segments stream in)
  ctx.fillStyle = t.ground;
  ctx.fillRect(0, horizon, width, height - horizon);
}
