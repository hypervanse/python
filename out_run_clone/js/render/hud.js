// Speedometer, timer, score, gear indicator, stage name overlay.

function digits(n, len) {
  return String(Math.max(0, Math.floor(n))).padStart(len, '0');
}

export function drawHUD(ctx, width, height, state) {
  ctx.save();
  ctx.textBaseline = 'top';
  ctx.font = '700 28px "Courier New", monospace';
  ctx.fillStyle = '#fff200';
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 4;
  const scoreText = `SCORE ${digits(state.score, 7)}`;
  ctx.strokeText(scoreText, 24, 20);
  ctx.fillText(scoreText, 24, 20);

  const timeText = `TIME ${digits(state.timeLeft, 2)}`;
  const timeColor = state.timeLeft <= 10 ? '#ff3333' : '#fff200';
  ctx.fillStyle = timeColor;
  ctx.strokeText(timeText, width - 200, 20);
  ctx.fillText(timeText, width - 200, 20);

  ctx.font = '600 18px "Courier New", monospace';
  ctx.fillStyle = '#ffffff';
  ctx.strokeText(state.stageName.toUpperCase(), 24, 58);
  ctx.fillText(state.stageName.toUpperCase(), 24, 58);
  ctx.strokeText(`STAGE ${state.stageNumber}/5`, width - 200, 58);
  ctx.fillText(`STAGE ${state.stageNumber}/5`, width - 200, 58);

  // Speedometer
  const sx = 110, sy = height - 90;
  ctx.font = '700 46px "Courier New", monospace';
  ctx.fillStyle = '#ffffff';
  const speedText = digits(state.speedKmh, 3);
  ctx.strokeText(speedText, sx - 60, sy - 20);
  ctx.fillText(speedText, sx - 60, sy - 20);
  ctx.font = '400 14px "Courier New", monospace';
  ctx.fillText('KM/H', sx - 60, sy + 26);

  // Gear
  ctx.font = '700 30px "Courier New", monospace';
  ctx.fillStyle = state.gear === 'HIGH' ? '#ff6a3d' : '#3dd6ff';
  const gearText = `GEAR ${state.gear === 'HIGH' ? 'H' : 'L'}`;
  ctx.strokeText(gearText, width - 200, height - 60);
  ctx.fillText(gearText, width - 200, height - 60);

  // Radio station
  ctx.font = '400 16px "Courier New", monospace';
  ctx.fillStyle = '#9be7ff';
  ctx.strokeText(`♪ ${state.radioName}`, 24, height - 40);
  ctx.fillText(`♪ ${state.radioName}`, 24, height - 40);

  if (state.crashed) {
    ctx.font = '700 42px "Courier New", monospace';
    ctx.fillStyle = '#ff3333';
    ctx.textAlign = 'center';
    ctx.strokeText('CRASH!', width / 2, height / 2 - 20);
    ctx.fillText('CRASH!', width / 2, height / 2 - 20);
    ctx.textAlign = 'left';
  }

  if (state.forkChoice) {
    ctx.font = '700 24px "Courier New", monospace';
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.strokeText('◀ STEER TO CHOOSE ROUTE ▶', width / 2, height * 0.3);
    ctx.fillText('◀ STEER TO CHOOSE ROUTE ▶', width / 2, height * 0.3);
    ctx.textAlign = 'left';
  }

  ctx.restore();
}
