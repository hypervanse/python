// Web Audio API based sound: a speed-mapped engine drone, tiny procedural
// radio "music" loops (no external audio files), and short SFX blips.

import { RADIO_STATIONS } from '../constants.js';

const SCALES = {
  latin: [0, 3, 5, 7, 10, 12, 15, 19],
  jazz: [0, 2, 3, 7, 9, 12, 14, 19],
  synth: [0, 2, 4, 7, 9, 12, 16, 19],
};

export class AudioManager {
  constructor() {
    this.ctx = null;
    this.engineOsc = null;
    this.engineGain = null;
    this.musicTimer = null;
    this.stationIndex = 0;
    this.muted = false;
  }

  ensureContext() {
    if (this.ctx) return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.ctx = new Ctx();
    this._setupEngine();
  }

  _setupEngine() {
    const ctx = this.ctx;
    this.engineOsc = ctx.createOscillator();
    this.engineOsc.type = 'sawtooth';
    this.engineGain = ctx.createGain();
    this.engineGain.gain.value = 0.0;
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 800;
    this.engineOsc.connect(filter);
    filter.connect(this.engineGain);
    this.engineGain.connect(ctx.destination);
    this.engineOsc.frequency.value = 60;
    this.engineOsc.start();
  }

  setEngineSpeed(speedPercent) {
    if (!this.ctx || this.muted) return;
    const freq = 60 + speedPercent * 260;
    this.engineOsc.frequency.setTargetAtTime(freq, this.ctx.currentTime, 0.05);
    this.engineGain.gain.setTargetAtTime(0.05 + speedPercent * 0.05, this.ctx.currentTime, 0.05);
  }

  stopEngine() {
    if (this.engineGain) this.engineGain.gain.setTargetAtTime(0, this.ctx.currentTime, 0.1);
  }

  playRadio(index) {
    this.ensureContext();
    this.stationIndex = index;
    this._stopMusic();
    if (this.muted) return;
    const station = RADIO_STATIONS[index];
    const scale = SCALES[station.style];
    const root = 220;
    const stepMs = 60000 / station.tempo / 2;
    let step = 0;
    this.musicTimer = setInterval(() => {
      const note = scale[Math.floor(Math.random() * scale.length) % scale.length];
      const octave = (step % 8 < 6) ? 0 : 12;
      this._pluck(root * Math.pow(2, (note + octave) / 12), stepMs / 1000 * 1.6, step % 4 === 0 ? 0.09 : 0.05);
      step++;
    }, stepMs);
  }

  _stopMusic() {
    if (this.musicTimer) clearInterval(this.musicTimer);
    this.musicTimer = null;
  }

  _pluck(freq, duration, gainAmount) {
    if (!this.ctx) return;
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    osc.type = 'triangle';
    osc.frequency.value = freq;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(gainAmount, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  }

  sfx(name) {
    this.ensureContext();
    if (this.muted) return;
    const ctx = this.ctx;
    if (name === 'crash') {
      const bufferSize = ctx.sampleRate * 0.35;
      const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < bufferSize; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize);
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      const gain = ctx.createGain();
      gain.gain.value = 0.5;
      src.connect(gain);
      gain.connect(ctx.destination);
      src.start();
    } else if (name === 'checkpoint') {
      this._pluck(880, 0.12, 0.2);
      setTimeout(() => this._pluck(1320, 0.15, 0.2), 90);
    } else if (name === 'gear') {
      this._pluck(200, 0.06, 0.15);
    } else if (name === 'countdown') {
      this._pluck(1000, 0.08, 0.2);
    } else if (name === 'select') {
      this._pluck(660, 0.08, 0.15);
    } else if (name === 'start') {
      this._pluck(440, 0.1, 0.2);
      setTimeout(() => this._pluck(660, 0.12, 0.2), 100);
      setTimeout(() => this._pluck(880, 0.18, 0.2), 200);
    }
  }

  toggleMute() {
    this.muted = !this.muted;
    if (this.muted) this._stopMusic();
    return this.muted;
  }
}
