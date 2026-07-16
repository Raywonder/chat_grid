import { afterEach, describe, expect, it, vi } from 'vitest';
import { type Player } from '../state/gameState';
import { HumanPresenceRuntime } from './humanPresenceRuntime';

const player = (posture: Player['posture'], mood = 'settled'): Player => ({
  id: 'dom',
  nickname: 'Dominique',
  x: 10,
  y: 12,
  posture,
  mood,
  seatedItemId: posture === 'standing' ? null : 'bed',
  seatedOffset: 0,
  handHeldById: null,
  lastMoveTime: 0,
});

describe('HumanPresenceRuntime', () => {
  afterEach(() => vi.restoreAllMocks());

  it('plays a subtle settle cue when a person lies down', () => {
    const playSpatialSample = vi.fn().mockResolvedValue(true);
    const runtime = new HumanPresenceRuntime({ playSpatialSample }, (path) => `/chatgrid/${path}`);
    runtime.update({ player: player('standing'), peers: [], currentLocationId: 'bedroom', listenerPosition: { x: 10, y: 12 }, nowMs: 0 });
    runtime.update({ player: player('lying'), peers: [], currentLocationId: 'bedroom', listenerPosition: { x: 10, y: 12 }, nowMs: 100 });

    expect(playSpatialSample).toHaveBeenCalledOnce();
    expect(playSpatialSample.mock.calls[0][0]).toContain('bedding-settle.mp3');
  });

  it('stays silent while a person remains standing', () => {
    const playSpatialSample = vi.fn().mockResolvedValue(true);
    const runtime = new HumanPresenceRuntime({ playSpatialSample }, (path) => path);
    runtime.update({ player: player('standing'), peers: [], currentLocationId: 'hall', listenerPosition: { x: 10, y: 12 }, nowMs: 0 });
    runtime.update({ player: player('standing'), peers: [], currentLocationId: 'hall', listenerPosition: { x: 10, y: 12 }, nowMs: 120_000 });

    expect(playSpatialSample).not.toHaveBeenCalled();
  });

  it('uses sleepy breathing for a dreamy person who is lying down', () => {
    vi.spyOn(Math, 'random').mockReturnValue(0);
    const playSpatialSample = vi.fn().mockResolvedValue(true);
    const runtime = new HumanPresenceRuntime({ playSpatialSample }, (path) => path);
    runtime.update({ player: player('lying', 'dreamy'), peers: [], currentLocationId: 'bedroom', listenerPosition: { x: 10, y: 12 }, nowMs: 0 });
    runtime.update({ player: player('lying', 'dreamy'), peers: [], currentLocationId: 'bedroom', listenerPosition: { x: 10, y: 12 }, nowMs: 7_000 });

    expect(playSpatialSample).toHaveBeenCalledOnce();
    expect(playSpatialSample.mock.calls[0][0]).toContain('sleepy-breath.mp3');
  });

  it('does not render presence sounds while the world layer is disabled', () => {
    const playSpatialSample = vi.fn().mockResolvedValue(true);
    const runtime = new HumanPresenceRuntime({ playSpatialSample }, (path) => path);
    runtime.update({ player: player('standing'), peers: [], currentLocationId: 'bedroom', listenerPosition: { x: 10, y: 12 }, nowMs: 0 });
    runtime.setEnabled(false);
    runtime.update({ player: player('lying'), peers: [], currentLocationId: 'bedroom', listenerPosition: { x: 10, y: 12 }, nowMs: 100 });

    expect(playSpatialSample).not.toHaveBeenCalled();
  });
});
