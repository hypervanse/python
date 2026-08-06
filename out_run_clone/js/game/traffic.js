import { SEGMENT_LENGTH } from '../constants.js';
import { SeededRandom } from '../utils/math.js';

const CAR_TYPES = [
  { type: 'sedan', colors: ['#2255cc', '#22aa55', '#dddddd', '#333333', '#cc9922'] },
  { type: 'sedan', colors: ['#aa2244', '#557799'] },
  { type: 'truck', colors: ['#886644', '#445566', '#996633'] },
];

export const CAR_WIDTH = 320;
export const CAR_LENGTH = SEGMENT_LENGTH * 1.1;

export class TrafficManager {
  constructor(seed) {
    this.rng = new SeededRandom(seed);
    this.cars = [];
  }

  populate(trackLength, density, startZ = SEGMENT_LENGTH * 20) {
    this.cars = [];
    const count = Math.floor((trackLength / SEGMENT_LENGTH) * density * 0.12);
    const lanes = [-0.55, 0, 0.55];
    for (let i = 0; i < count; i++) {
      const group = this.rng.pick(CAR_TYPES);
      this.cars.push({
        z: startZ + this.rng.next() * (trackLength - startZ - SEGMENT_LENGTH * 10),
        x: this.rng.pick(lanes) + this.rng.range(-0.08, 0.08),
        speed: SEGMENT_LENGTH * this.rng.range(16, 34),
        color: this.rng.pick(group.colors),
        type: group.type,
      });
    }
    this.cars.sort((a, b) => a.z - b.z);
  }

  update(dt) {
    for (const car of this.cars) {
      car.z += car.speed * dt;
    }
  }

  carsInRange(fromZ, toZ) {
    // cars array stays roughly sorted; linear scan is fine at this scale (<200 cars)
    return this.cars.filter((c) => c.z >= fromZ && c.z <= toZ);
  }

  reset() {
    this.cars = [];
  }
}
