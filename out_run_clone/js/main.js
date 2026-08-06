import {
  WIDTH, HEIGHT, STEP, SEGMENT_LENGTH, ROAD_WIDTH, LANES, CAMERA_DEPTH,
  DRAW_DISTANCE, FOG_DENSITY, STATE, GEAR, RADIO_STATIONS,
} from './constants.js';
import { renderRoad, projectPoint } from './render/road.js';
import { drawBackground } from './render/background.js';
import { getSprite, drawRoadsideSprite, drawTrafficCar, drawPlayerCar } from './render/sprites.js';
import { drawHUD } from './render/hud.js';
import { Player } from './game/player.js';
import { Camera } from './game/camera.js';
import { TrafficManager } from './game/traffic.js';
import { checkTrafficCollision, isOffRoad } from './game/collision.js';
import {
  ROOT_STAGE, buildStageTrack, getStageConfig, getTotalTimeStart,
} from './game/stages.js';
import { Input } from './utils/input.js';
import { AudioManager } from './audio/audio.js';

const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');
canvas.width = WIDTH;
canvas.height = HEIGHT;

const input = new Input();
const audio = new AudioManager();

let state = STATE.TITLE;
let highScore = Number(localStorage.getItem('outrun_highscore') || 0);
let blink = 0;

const demoTrack = buildStageTrack(ROOT_STAGE, 1);
let demoPosition = 0;

const G = {
  stageId: ROOT_STAGE,
  row: 1,
  track: null,
  position: 0,
  player: new Player(),
  camera: new Camera(),
  traffic: new TrafficManager(1),
  score: 0,
  timeLeft: getTotalTimeStart(),
  radioIndex: 0,
  forkHandled: false,
  ending: null,
};

function findSegment(position, segments) {
  return segments[Math.floor(position / SEGMENT_LENGTH) % segments.length];
}

function newGame() {
  G.stageId = ROOT_STAGE;
  const cfg = getStageConfig(G.stageId);
  G.row = cfg.row;
  G.track = buildStageTrack(G.stageId, G.row);
  G.position = 0;
  G.player = new Player();
  G.camera = new Camera();
  G.traffic = new TrafficManager(42);
  G.traffic.populate(G.track.length, cfg.trafficDensity);
  G.score = 0;
  G.timeLeft = getTotalTimeStart();
  G.forkHandled = false;
  G.ending = null;
}

function transitionStage(nextId) {
  const cfg = getStageConfig(nextId);
  G.stageId = nextId;
  G.row = cfg.row;
  G.track = buildStageTrack(nextId, cfg.row);
  G.position = 0;
  G.forkHandled = false;
  G.player.x *= 0.3;
  G.traffic.populate(G.track.length, cfg.trafficDensity);
}

function endGame(won, goal) {
  state = won ? STATE.COURSE_CLEAR : STATE.GAME_OVER;
  G.ending = { won, goal };
  audio.stopEngine();
  if (G.score > highScore) {
    highScore = Math.floor(G.score);
    localStorage.setItem('outrun_highscore', String(highScore));
  }
}

function handleGlobalRadioKeys() {
  if (input.wasPressed('radio1') && G.radioIndex !== 0) { G.radioIndex = 0; audio.playRadio(0); }
  if (input.wasPressed('radio2') && G.radioIndex !== 1) { G.radioIndex = 1; audio.playRadio(1); }
  if (input.wasPressed('radio3') && G.radioIndex !== 2) { G.radioIndex = 2; audio.playRadio(2); }
}

function updateTitle(dt) {
  demoPosition += 6200 * dt;
  if (demoPosition > demoTrack.length - SEGMENT_LENGTH * 50) demoPosition = 0;
  blink += dt;
  if (input.wasPressed('start')) {
    audio.ensureContext();
    audio.sfx('start');
    state = STATE.RADIO;
  }
}

function updateRadio(dt) {
  blink += dt;
  if (input.wasPressed('left')) { G.radioIndex = (G.radioIndex + RADIO_STATIONS.length - 1) % RADIO_STATIONS.length; audio.sfx('select'); }
  if (input.wasPressed('right')) { G.radioIndex = (G.radioIndex + 1) % RADIO_STATIONS.length; audio.sfx('select'); }
  handleGlobalRadioKeys();
  if (input.wasPressed('start')) {
    newGame();
    audio.playRadio(G.radioIndex);
    audio.sfx('start');
    state = STATE.PLAYING;
  }
}

const SPRITE_CANVAS_SIZE = { w: 240, h: 340 };

function nearbySprites(segments, segIndex, radius) {
  const list = [];
  for (let i = -radius; i <= radius; i++) {
    const s = segments[((segIndex + i) % segments.length + segments.length) % segments.length];
    if (s.sprites.length) for (const sp of s.sprites) list.push({ ...sp, z: s.p1.world.z });
  }
  return list;
}

function updatePlaying(dt) {
  handleGlobalRadioKeys();
  if (input.wasPressed('gear')) { G.player.shiftGear(); audio.sfx('gear'); }

  const track = G.track;
  const segments = track.segments;
  const segIndex = Math.floor(G.position / SEGMENT_LENGTH) % segments.length;
  const seg = segments[segIndex];
  const offRoad = isOffRoad(G.player.x);
  const forceStop = G.timeLeft <= 0;

  G.player.update(dt, input, seg.curve, offRoad, forceStop);
  G.camera.update(dt);

  if (!G.player.crashed) {
    G.position += G.player.speed * dt;
    G.score += (G.player.gear === GEAR.HIGH ? 2 : 1) * G.player.speed * dt * 0.012;
  }

  G.traffic.update(dt);
  const cars = G.traffic.carsInRange(G.position - SEGMENT_LENGTH * 4, G.position + SEGMENT_LENGTH * DRAW_DISTANCE);
  if (!G.player.invulnerable) {
    const hit = checkTrafficCollision(G.position, G.player.x, cars);
    if (hit) { G.player.crash(); G.camera.triggerShake(); audio.sfx('crash'); }
    if (offRoad) {
      const nearby = nearbySprites(segments, segIndex, 2);
      for (const sp of nearby) {
        if (Math.abs(sp.z - G.position) < SEGMENT_LENGTH * 1.5 && Math.abs(G.player.x - sp.offset) < 0.45) {
          G.player.crash();
          G.camera.triggerShake();
          audio.sfx('crash');
          break;
        }
      }
    }
  }

  audio.setEngineSpeed(G.player.speed / G.player.maxSpeed);

  if (!forceStop) {
    G.timeLeft -= dt;
    if (G.timeLeft <= 10 && G.timeLeft + dt > 10) audio.sfx('countdown');
    if (G.timeLeft < 0) G.timeLeft = 0;
  } else if (G.player.speed <= 2) {
    endGame(false);
    return;
  }

  const forkZ = track.forkAt * SEGMENT_LENGTH;
  if (!G.forkHandled && G.position >= forkZ) {
    G.forkHandled = true;
    const cfg = getStageConfig(G.stageId);
    if (cfg.isGoal) {
      endGame(true, cfg.goal);
    } else {
      const goLeft = G.player.x <= 0;
      const nextId = goLeft ? cfg.leftChild : cfg.rightChild;
      G.timeLeft += cfg.timeBonus;
      G.score += 400 * cfg.row;
      audio.sfx('checkpoint');
      transitionStage(nextId);
    }
  }
}

function updateEndScreen() {
  blink += STEP;
  if (input.wasPressed('start')) {
    state = STATE.TITLE;
    demoPosition = 0;
  }
}

function update(dt) {
  if (state === STATE.TITLE) updateTitle(dt);
  else if (state === STATE.RADIO) updateRadio(dt);
  else if (state === STATE.PLAYING) updatePlaying(dt);
  else updateEndScreen(dt);
  input.consume();
}

function drawScene(track, position, player, camera, traffic, theme) {
  const shake = camera.shakeOffset();
  ctx.save();
  ctx.translate(shake.x, shake.y);

  const segIndex = Math.floor(position / SEGMENT_LENGTH) % track.segments.length;
  const seg = track.segments[segIndex];
  drawBackground(ctx, WIDTH, HEIGHT, theme.sky, position * 0.02, seg.curve * 4000);

  const carsByIndex = new Map();
  if (traffic) {
    for (const car of traffic.carsInRange(position - SEGMENT_LENGTH * 4, position + SEGMENT_LENGTH * DRAW_DISTANCE)) {
      const idx = Math.floor(car.z / SEGMENT_LENGTH) % track.segments.length;
      if (!carsByIndex.has(idx)) carsByIndex.set(idx, []);
      carsByIndex.get(idx).push(car);
    }
  }

  renderRoad(ctx, {
    segments: track.segments,
    trackLength: track.length,
    position,
    playerX: player.x,
    playerY: 0,
    cameraHeight: camera.height,
    cameraDepth: camera.depth,
    fogDensity: FOG_DENSITY,
    drawDistance: DRAW_DISTANCE,
    width: WIDTH,
    height: HEIGHT,
    roadWidth: ROAD_WIDTH,
    lanes: LANES,
    findSegment: (z) => findSegment(z, track.segments),
    onSegment: (segment) => {
      if (!segment.visible) return;
      for (const sp of segment.sprites) {
        const sprite = getSprite(sp.type, sp.palette, SPRITE_CANVAS_SIZE.w, SPRITE_CANVAS_SIZE.h);
        const s = projectPoint(sp.offset, segment.p1.world.z, 0, segment.projCamX, segment.projCamY, segment.projCamZ, camera.depth, WIDTH, HEIGHT, ROAD_WIDTH);
        if (s.scale > 0) drawRoadsideSprite(ctx, sprite, s.x, s.y, s.scale, ROAD_WIDTH, sp.offset > 0 ? 1 : -1, SPRITE_CANVAS_SIZE.w, SPRITE_CANVAS_SIZE.h);
      }
      const carsHere = carsByIndex.get(segment.index);
      if (carsHere) {
        for (const car of carsHere) {
          const s = projectPoint(car.x, car.z, 0, segment.projCamX, segment.projCamY, segment.projCamZ, camera.depth, WIDTH, HEIGHT, ROAD_WIDTH);
          if (s.scale > 0) drawTrafficCar(ctx, s.x, s.y, s.scale, s.w * 1.15, car.color, car.type);
        }
      }
    },
  });

  // Player car: fixed screen position, only steering/crash affects its pose.
  const px = WIDTH / 2 + player.x * WIDTH * 0.12;
  const py = HEIGHT - 118;
  drawPlayerCar(ctx, px, py, 1.05, player.steerDir, player.crashed, player.bounce);

  if (player.speed > 0 && !player.crashed) {
    ctx.globalAlpha = Math.min(0.35, (player.speed / player.maxSpeed) * 0.4);
    ctx.strokeStyle = '#ffffff';
    for (let i = 0; i < 10; i++) {
      const lx = Math.random() * WIDTH;
      ctx.beginPath();
      ctx.moveTo(lx, 0);
      ctx.lineTo(lx + (lx - WIDTH / 2) * 0.15, HEIGHT * 0.4);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  ctx.restore();
}

function render() {
  if (state === STATE.TITLE) {
    const demoPlayer = { x: Math.sin(demoPosition * 0.0006) * 0.5, crashed: false, steerDir: 0, bounce: 0, speed: 6000, maxSpeed: 6000 };
    drawScene(demoTrack, demoPosition, demoPlayer, G.camera, null, demoTrack.theme);
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.25)';
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ff5a1f';
    ctx.strokeStyle = '#4a0f00';
    ctx.lineWidth = 8;
    ctx.font = '900 96px "Arial Black", sans-serif';
    ctx.strokeText('OUT RUN', WIDTH / 2, HEIGHT * 0.32);
    ctx.fillText('OUT RUN', WIDTH / 2, HEIGHT * 0.32);
    ctx.font = '600 22px "Courier New", monospace';
    ctx.fillStyle = '#ffffff';
    ctx.fillText('A BROWSER ARCADE DRIVING EXPERIENCE', WIDTH / 2, HEIGHT * 0.32 + 46);
    if (Math.floor(blink * 2) % 2 === 0) {
      ctx.font = '700 32px "Courier New", monospace';
      ctx.fillStyle = '#fff200';
      ctx.fillText('PRESS ENTER TO START', WIDTH / 2, HEIGHT * 0.62);
    }
    ctx.font = '400 18px "Courier New", monospace';
    ctx.fillStyle = '#cccccc';
    ctx.fillText(`HIGH SCORE: ${String(highScore).padStart(7, '0')}`, WIDTH / 2, HEIGHT * 0.7);
    ctx.textAlign = 'left';
    ctx.restore();
  } else if (state === STATE.RADIO) {
    ctx.fillStyle = '#0a0a1a';
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    ctx.save();
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ffffff';
    ctx.font = '700 40px "Courier New", monospace';
    ctx.fillText('SELECT YOUR MUSIC', WIDTH / 2, HEIGHT * 0.18);

    RADIO_STATIONS.forEach((st, i) => {
      const y = HEIGHT * 0.38 + i * 90;
      const active = i === G.radioIndex;
      ctx.font = active ? '700 34px "Courier New", monospace' : '400 26px "Courier New", monospace';
      ctx.fillStyle = active ? '#fff200' : '#8899aa';
      ctx.fillText(`${active ? '▶ ' : ''}${st.name}${active ? ' ◀' : ''}`, WIDTH / 2, y);
    });

    if (Math.floor(blink * 2) % 2 === 0) {
      ctx.font = '700 26px "Courier New", monospace';
      ctx.fillStyle = '#fff200';
      ctx.fillText('PRESS ENTER TO DRIVE', WIDTH / 2, HEIGHT * 0.85);
    }
    ctx.textAlign = 'left';
    ctx.restore();
  } else if (state === STATE.PLAYING) {
    drawScene(G.track, G.position, G.player, G.camera, G.traffic, G.track.theme);
    const cfg = getStageConfig(G.stageId);
    drawHUD(ctx, WIDTH, HEIGHT, {
      score: G.score,
      timeLeft: G.timeLeft,
      stageName: cfg.name,
      stageNumber: cfg.row,
      speedKmh: G.player.speedKmh,
      gear: G.player.gear,
      radioName: RADIO_STATIONS[G.radioIndex].name,
      crashed: G.player.crashed,
      forkChoice: G.position >= G.track.forkAt * SEGMENT_LENGTH - SEGMENT_LENGTH * 30 && !G.forkHandled && !cfg.isGoal,
    });
  } else if (state === STATE.GAME_OVER || state === STATE.COURSE_CLEAR) {
    drawScene(G.track, G.position, G.player, G.camera, G.traffic, G.track.theme);
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    ctx.textAlign = 'center';
    if (state === STATE.GAME_OVER) {
      ctx.fillStyle = '#ff3333';
      ctx.font = '900 72px "Arial Black", sans-serif';
      ctx.fillText('GAME OVER', WIDTH / 2, HEIGHT * 0.38);
    } else {
      ctx.fillStyle = '#3dff8a';
      ctx.font = '900 56px "Arial Black", sans-serif';
      ctx.fillText('CONGRATULATIONS!', WIDTH / 2, HEIGHT * 0.32);
      ctx.font = '600 26px "Courier New", monospace';
      ctx.fillStyle = '#ffffff';
      ctx.fillText(`YOU REACHED GOAL ${G.ending?.goal || ''}`, WIDTH / 2, HEIGHT * 0.32 + 50);
    }
    ctx.font = '600 30px "Courier New", monospace';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(`SCORE: ${Math.floor(G.score)}`, WIDTH / 2, HEIGHT * 0.55);
    ctx.fillText(`HIGH SCORE: ${highScore}`, WIDTH / 2, HEIGHT * 0.62);
    if (Math.floor(blink * 2) % 2 === 0) {
      ctx.font = '700 26px "Courier New", monospace';
      ctx.fillStyle = '#fff200';
      ctx.fillText('PRESS ENTER FOR TITLE', WIDTH / 2, HEIGHT * 0.78);
    }
    ctx.textAlign = 'left';
    ctx.restore();
  }
}

let lastTime = performance.now();
let acc = 0;
function loop(now) {
  const dt = Math.min(0.05, (now - lastTime) / 1000);
  lastTime = now;
  acc += dt;
  while (acc >= STEP) {
    update(STEP);
    acc -= STEP;
  }
  render();
  requestAnimationFrame(loop);
}

requestAnimationFrame((t) => { lastTime = t; requestAnimationFrame(loop); });
