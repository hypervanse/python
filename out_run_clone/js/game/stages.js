// Stage definitions (the 15-stage Out Run "pyramid") and procedural track
// generation. Each stage's road layout is generated deterministically from
// a seed so it's stable across plays but still varied stage-to-stage.

import { SEGMENT_LENGTH, RUMBLE_LENGTH, TOTAL_TIME_START } from '../constants.js';
import { SeededRandom, easeInOut, easeIn } from '../utils/math.js';

const THEMES = {
  coconut_beach: {
    name: 'Coconut Beach', sky: { skyTop: '#2fa9e8', skyBottom: '#bdf0ff', sun: '#ffe27a', cloud: '#ffffff', hillFar: '#1f8fbd', hillNear: '#17a86b', ground: '#0f8a3d' },
    road: { road: '#666666', roadAlt: '#646464', rumble: '#e0442e', rumbleAlt: '#f2f2f2', lane: '#f2f2f2', grass: '#12ad12', grassAlt: '#0a9a0a' },
    sprites: ['palm', 'sign'], curviness: 0.35, hilliness: 0.2,
  },
  gateway: {
    name: 'Gateway', sky: { skyTop: '#e8712f', skyBottom: '#ffd7a0', sun: '#fff2c0', cloud: '#ffcf9e', hillFar: '#7a4a2f', hillNear: '#5a3a2f', ground: '#4a3a2a' },
    road: { road: '#5c5c5c', roadAlt: '#5a5a5a', rumble: '#e0442e', rumbleAlt: '#f2f2f2', lane: '#f2f2f2', grass: '#3a6a2a', grassAlt: '#2f5a20' },
    sprites: ['building', 'sign'], curviness: 0.4, hilliness: 0.25,
  },
  devils_canyon: {
    name: "Devil's Canyon", sky: { skyTop: '#b8232f', skyBottom: '#ff9a5a', sun: '#ffdca0', cloud: '#e08a6a', hillFar: '#7a3020', hillNear: '#5c2418', ground: '#6a4a2a' },
    road: { road: '#6a5a4a', roadAlt: '#685848', rumble: '#f2f2f2', rumbleAlt: '#e0442e', lane: '#f2f2f2', grass: '#8a5a3a', grassAlt: '#7a4a2a' },
    sprites: ['rock', 'cactus'], curviness: 0.55, hilliness: 0.45,
  },
  desert: {
    name: 'Desert', sky: { skyTop: '#cfe8f2', skyBottom: '#fdf3d0', sun: '#fff6d0', cloud: '#f2e6c0', hillFar: '#d8c48a', hillNear: '#c9a86a', ground: '#e2c98a' },
    road: { road: '#8a7a5a', roadAlt: '#887858', rumble: '#f2f2f2', rumbleAlt: '#c94a2a', lane: '#f2f2f2', grass: '#d8b878', grassAlt: '#caa868' },
    sprites: ['cactus', 'rock'], curviness: 0.3, hilliness: 0.15,
  },
  alps: {
    name: 'Alps', sky: { skyTop: '#4a86c8', skyBottom: '#cfe8ff', sun: '#ffffff', cloud: '#ffffff', hillFar: '#8aa8c8', hillNear: '#e8f2ff', ground: '#eef6ff' },
    road: { road: '#5a5a5a', roadAlt: '#585858', rumble: '#e0442e', rumbleAlt: '#f2f2f2', lane: '#f2f2f2', grass: '#e8f2ff', grassAlt: '#d8ecff' },
    sprites: ['pine', 'building'], curviness: 0.5, hilliness: 0.6,
  },
  cloudy_mountain: {
    name: 'Cloudy Mountain', sky: { skyTop: '#8a96a0', skyBottom: '#cdd6dc', sun: '#dfe6ea', cloud: '#f4f6f8', hillFar: '#6a7680', hillNear: '#4a5560', ground: '#5a6a5a' },
    road: { road: '#575757', roadAlt: '#555555', rumble: '#cfcfcf', rumbleAlt: '#8a8a8a', lane: '#dedede', grass: '#4a6a4a', grassAlt: '#3f5f3f' },
    sprites: ['pine', 'rock'], curviness: 0.5, hilliness: 0.7,
  },
  wilderness: {
    name: 'Wilderness', sky: { skyTop: '#274b7a', skyBottom: '#7fa8c9', sun: '#ffe9b0', cloud: '#b8cbe0', hillFar: '#25422f', hillNear: '#1c3524', ground: '#1a3020' },
    road: { road: '#555555', roadAlt: '#535353', rumble: '#e0442e', rumbleAlt: '#f2f2f2', lane: '#f2f2f2', grass: '#1e4a24', grassAlt: '#173d1c' },
    sprites: ['tree', 'rock'], curviness: 0.55, hilliness: 0.4,
  },
  old_capital: {
    name: 'Old Capital', sky: { skyTop: '#e8b25a', skyBottom: '#ffe3a8', sun: '#fff6d8', cloud: '#f2cf9e', hillFar: '#8a6a4a', hillNear: '#6a4e34', ground: '#6a5a42' },
    road: { road: '#736357', roadAlt: '#716155', rumble: '#f2f2f2', rumbleAlt: '#8a3a2a', lane: '#f2f2f2', grass: '#7a6a4a', grassAlt: '#6a5a3e' },
    sprites: ['building', 'sign'], curviness: 0.45, hilliness: 0.3,
  },
  wheat_field: {
    name: 'Wheat Field', sky: { skyTop: '#e8c85a', skyBottom: '#fff0b0', sun: '#fffbe0', cloud: '#f6e2a0', hillFar: '#c8a848', hillNear: '#d8b858', ground: '#e0c060' },
    road: { road: '#6a5a45', roadAlt: '#685843', rumble: '#f2f2f2', rumbleAlt: '#c94a2a', lane: '#f2f2f2', grass: '#e2c258', grassAlt: '#d4b448' },
    sprites: ['windmill', 'tree'], curviness: 0.3, hilliness: 0.2,
  },
  seaside_town: {
    name: 'Seaside Town', sky: { skyTop: '#7ec8e0', skyBottom: '#dff5f5', sun: '#fff6d8', cloud: '#ffffff', hillFar: '#3a8ab0', hillNear: '#eae0c8', ground: '#e6dcc0' },
    road: { road: '#68666a', roadAlt: '#666468', rumble: '#e0442e', rumbleAlt: '#f2f2f2', lane: '#f2f2f2', grass: '#3ab08a', grassAlt: '#2fa07a' },
    sprites: ['building', 'palm'], curviness: 0.4, hilliness: 0.2,
  },
  vineyard: {
    name: 'Vineyard (Goal A)', goal: 'A', sky: { skyTop: '#e89a4a', skyBottom: '#ffd9a0', sun: '#fff2c8', cloud: '#f2c69e', hillFar: '#5a6a3a', hillNear: '#4a5a2f', ground: '#5a4a2a' },
    road: { road: '#665c4a', roadAlt: '#645a48', rumble: '#f2f2f2', rumbleAlt: '#8a3a2a', lane: '#f2f2f2', grass: '#5a7a3a', grassAlt: '#4c6c30' },
    sprites: ['tree', 'building'], curviness: 0.45, hilliness: 0.35,
  },
  death_valley: {
    name: 'Death Valley (Goal B)', goal: 'B', sky: { skyTop: '#e0603a', skyBottom: '#ffb27a', sun: '#ffe0a0', cloud: '#d88a5a', hillFar: '#7a3a20', hillNear: '#5c2a18', ground: '#7a5a34' },
    road: { road: '#7a6a52', roadAlt: '#786850', rumble: '#f2f2f2', rumbleAlt: '#e0442e', lane: '#f2f2f2', grass: '#8a6a3a', grassAlt: '#7a5c30' },
    sprites: ['cactus', 'rock'], curviness: 0.4, hilliness: 0.3,
  },
  desolation_hill: {
    name: 'Desolation Hill (Goal C)', goal: 'C', sky: { skyTop: '#6a6a72', skyBottom: '#b0b0b8', sun: '#d8d8d8', cloud: '#dcdce0', hillFar: '#4a4a50', hillNear: '#3a3a40', ground: '#4a4640' },
    road: { road: '#4f4f52', roadAlt: '#4d4d50', rumble: '#cfcfcf', rumbleAlt: '#8a8a8a', lane: '#dedede', grass: '#5a564a', grassAlt: '#4c483e' },
    sprites: ['rock', 'tree'], curviness: 0.5, hilliness: 0.5,
  },
  autobahn: {
    name: 'Autobahn (Goal D)', goal: 'D', sky: { skyTop: '#3a5a7a', skyBottom: '#8aa8c0', sun: '#e0dcc0', cloud: '#a8b8c8', hillFar: '#3a4048', hillNear: '#2a3038', ground: '#3a3e42' },
    road: { road: '#454545', roadAlt: '#434343', rumble: '#e0442e', rumbleAlt: '#f2f2f2', lane: '#f2f2f2', grass: '#3a4a3a', grassAlt: '#304030' },
    sprites: ['building', 'sign'], curviness: 0.25, hilliness: 0.15,
  },
  lakeside: {
    name: 'Lakeside (Goal E)', goal: 'E', sky: { skyTop: '#3a6ab0', skyBottom: '#a8d0e8', sun: '#ffe9b0', cloud: '#dceaf5', hillFar: '#2a5a80', hillNear: '#1e6a9a', ground: '#2a4a3a' },
    road: { road: '#5c5c5c', roadAlt: '#5a5a5a', rumble: '#e0442e', rumbleAlt: '#f2f2f2', lane: '#f2f2f2', grass: '#1e6a4a', grassAlt: '#175a3e' },
    sprites: ['tree', 'palm'], curviness: 0.35, hilliness: 0.25,
  },
};

// Pyramid tree: adjacent parents share a child, matching the classic Out Run map.
export const STAGE_TREE = {
  coconut_beach: { left: 'gateway', right: 'devils_canyon', row: 1 },
  gateway: { left: 'desert', right: 'alps', row: 2 },
  devils_canyon: { left: 'alps', right: 'cloudy_mountain', row: 2 },
  desert: { left: 'wilderness', right: 'old_capital', row: 3 },
  alps: { left: 'old_capital', right: 'wheat_field', row: 3 },
  cloudy_mountain: { left: 'wheat_field', right: 'seaside_town', row: 3 },
  wilderness: { left: 'vineyard', right: 'death_valley', row: 4 },
  old_capital: { left: 'death_valley', right: 'desolation_hill', row: 4 },
  wheat_field: { left: 'desolation_hill', right: 'autobahn', row: 4 },
  seaside_town: { left: 'autobahn', right: 'lakeside', row: 4 },
  vineyard: { row: 5 },
  death_valley: { row: 5 },
  desolation_hill: { row: 5 },
  autobahn: { row: 5 },
  lakeside: { row: 5 },
};

export const ROOT_STAGE = 'coconut_beach';

function hashSeed(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function colorSetFor(theme, index, isLaneSet) {
  return {
    road: theme.road.road,
    grass: (Math.floor(index / RUMBLE_LENGTH) % 2) ? theme.road.grass : theme.road.grassAlt,
    rumble: (Math.floor(index / RUMBLE_LENGTH) % 2) ? theme.road.rumble : theme.road.rumbleAlt,
    lane: isLaneSet ? theme.road.lane : null,
  };
}

export function buildStageTrack(stageId, row) {
  const theme = THEMES[stageId];
  const rng = new SeededRandom(hashSeed(stageId));
  const segments = [];
  const CURVE_UNIT = 0.7 * (1 + row * 0.12);
  const HILL_UNIT = 900 * (1 + row * 0.1);

  const addSegment = (curve, y) => {
    const n = segments.length;
    const prevY = n > 0 ? segments[n - 1].p2.world.y : 0;
    const isLaneSet = Math.floor(n / RUMBLE_LENGTH) % 2 === 0;
    segments.push({
      index: n,
      p1: { world: { x: 0, y: prevY, z: n * SEGMENT_LENGTH }, camera: {}, screen: {} },
      p2: { world: { x: 0, y, z: (n + 1) * SEGMENT_LENGTH }, camera: {}, screen: {} },
      curve,
      sprites: [],
      color: colorSetFor(theme, n, isLaneSet),
    });
  };

  const addRoad = (enter, hold, leave, curve, hillDelta) => {
    const startY = segments.length ? segments[segments.length - 1].p2.world.y : 0;
    const endY = startY + hillDelta;
    const total = enter + hold + leave;
    for (let i = 0; i < enter; i++) addSegment(easeIn(0, curve, i / enter), easeInOut(startY, endY, i / total));
    for (let i = 0; i < hold; i++) addSegment(curve, easeInOut(startY, endY, (enter + i) / total));
    for (let i = 0; i < leave; i++) addSegment(easeInOut(curve, 0, i / leave), easeInOut(startY, endY, (enter + hold + i) / total));
  };

  const targetSegments = 900 + row * 120;
  addRoad(40, 40, 40, 0, 0); // starting straight
  while (segments.length < targetSegments) {
    const roll = rng.next();
    const curveMag = rng.range(1.5, 4.5) * CURVE_UNIT * (rng.next() < 0.5 ? -1 : 1);
    const hillMag = rng.range(-1, 1) * HILL_UNIT * theme.hilliness;
    if (roll < theme.curviness * 0.5) {
      addRoad(30, 60, 30, curveMag, hillMag);
    } else if (roll < theme.curviness) {
      addRoad(20, 30, 20, curveMag * 1.6, hillMag);
    } else if (roll < theme.curviness + theme.hilliness * 0.4) {
      addRoad(40, 50, 40, 0, hillMag * 1.4);
    } else {
      addRoad(30, 40, 30, 0, 0);
    }
  }
  addRoad(30, 60, 30, 0, -((segments[segments.length - 1]?.p2.world.y) || 0)); // ease back to ground before fork
  addRoad(20, 60, 20, 0, 0); // final straight for the fork

  // Roadside sprite placement
  const spriteTypes = theme.sprites;
  for (let n = 20; n < segments.length - 60; n += 1) {
    if (rng.next() < 0.09) {
      const side = rng.next() < 0.5 ? -1 : 1;
      const type = rng.pick(spriteTypes);
      segments[n].sprites.push({ type, offset: side * rng.range(1.3, 2.6), palette: theme.road });
    }
  }

  const forkAt = segments.length - 45;
  return { segments, theme, forkAt, length: segments.length * SEGMENT_LENGTH };
}

export function getStageConfig(stageId) {
  const node = STAGE_TREE[stageId];
  const theme = THEMES[stageId];
  return {
    id: stageId,
    name: theme.name,
    row: node.row,
    leftChild: node.left || null,
    rightChild: node.right || null,
    isGoal: !node.left && !node.right,
    goal: theme.goal || null,
    trafficDensity: 0.25 + node.row * 0.18,
    timeBonus: 30 + node.row * 8,
  };
}

export function getTotalTimeStart() {
  return TOTAL_TIME_START;
}
