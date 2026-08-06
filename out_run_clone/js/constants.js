// All tuning constants live here so the feel of the game can be adjusted
// from a single place.

export const WIDTH = 1024;
export const HEIGHT = 768;
export const FPS = 60;
export const STEP = 1 / FPS;

export const SEGMENT_LENGTH = 200;
export const RUMBLE_LENGTH = 3;
export const LANES = 3;
export const ROAD_WIDTH = 2000;

export const FIELD_OF_VIEW = 100;
export const CAMERA_HEIGHT = 1200;
export const CAMERA_DEPTH = 1 / Math.tan((FIELD_OF_VIEW / 2) * Math.PI / 180);
export const DRAW_DISTANCE = 300;
export const FOG_DENSITY = 5;

// Player physics (world units / second, ~km/h scaled).
export const MAX_SPEED_LOW = SEGMENT_LENGTH * 45; // ≈180 km/h feel
export const MAX_SPEED_HIGH = SEGMENT_LENGTH * 73; // ≈293 km/h feel
export const ACCEL_LOW = MAX_SPEED_LOW / 3.5;
export const ACCEL_HIGH = MAX_SPEED_HIGH / 9;
export const BRAKE = -MAX_SPEED_HIGH / 1.4;
export const DECEL = -MAX_SPEED_HIGH / 6;
export const OFFROAD_DECEL = -MAX_SPEED_HIGH / 3;
export const OFFROAD_LIMIT = MAX_SPEED_LOW / 3;

export const CENTRIFUGAL = 0.3;
export const PLAYER_X_MAX = 3; // in road widths, allows driving well off-road
export const STEER_SPEED = 3.2;

export const PLAYER_Z = CAMERA_HEIGHT * CAMERA_DEPTH; // distance from camera to player sprite

export const CRASH_DURATION = 1.8; // seconds

export const KM_PER_WORLD_UNIT = 293 / MAX_SPEED_HIGH; // converts world speed -> displayed km/h

export const TOTAL_TIME_START = 75;

export const GEAR = { LOW: 'LOW', HIGH: 'HIGH' };

export const STATE = {
  TITLE: 'TITLE',
  RADIO: 'RADIO',
  PLAYING: 'PLAYING',
  GAME_OVER: 'GAME_OVER',
  COURSE_CLEAR: 'COURSE_CLEAR',
};

export const RADIO_STATIONS = [
  { name: 'MAGICAL SOUND SHOWER', tempo: 128, style: 'latin' },
  { name: 'PASSING BREEZE', tempo: 96, style: 'jazz' },
  { name: 'SPLASH WAVE', tempo: 140, style: 'synth' },
];

export const COLORS = {
  base: {
    sky: '#72c6f0',
    road: '#6b6b6b',
    roadAlt: '#696969',
    rumble: '#ff0000',
    rumbleAlt: '#ffffff',
    lane: '#ffffff',
    grass: '#10aa10',
    grassAlt: '#009a00',
  },
};
