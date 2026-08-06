import { ROAD_WIDTH, PLAYER_X_MAX } from '../constants.js';
import { CAR_WIDTH, CAR_LENGTH } from './traffic.js';

const PLAYER_WIDTH = 460;

// All checks operate in world space (player.x is in road-widths, car.x too).
export function checkTrafficCollision(playerZ, playerX, cars) {
  const halfPlayer = (PLAYER_WIDTH / 2) / (ROAD_WIDTH / 2);
  const halfCar = (CAR_WIDTH / 2) / (ROAD_WIDTH / 2);
  for (const car of cars) {
    if (Math.abs(car.z - playerZ) > CAR_LENGTH) continue;
    if (Math.abs(car.x - playerX) < halfPlayer + halfCar) {
      return car;
    }
  }
  return null;
}

export function isOffRoad(playerX) {
  return Math.abs(playerX) > 1;
}

export function isOutOfBounds(playerX) {
  return Math.abs(playerX) > PLAYER_X_MAX - 0.05;
}
