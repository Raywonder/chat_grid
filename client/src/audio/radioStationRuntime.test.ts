import { beforeEach, describe, expect, it, vi } from 'vitest';
import { type WorldItem } from '../state/gameState';
import { RadioStationRuntime } from './radioStationRuntime';

vi.hoisted(() => {
  Object.defineProperty(globalThis, 'HTMLMediaElement', {
    configurable: true,
    value: { HAVE_CURRENT_DATA: 2 },
  });
});

const storage = new Map<string, string>();

function installLocalStorage(): void {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => {
        storage.set(key, value);
      }),
      removeItem: vi.fn((key: string) => {
        storage.delete(key);
      }),
      clear: vi.fn(() => {
        storage.clear();
      }),
    },
  });
}

function radio(overrides: Partial<WorldItem> = {}, params: Record<string, unknown> = {}): WorldItem {
  return {
    id: 'living-room-radio',
    type: 'radio_station',
    title: 'Living room radio',
    locationId: 'living-room',
    x: 5,
    y: 5,
    createdBy: 'system',
    updatedBy: 'system',
    createdAt: 0,
    updatedAt: 0,
    version: 1,
    capabilities: [],
    params: {
      enabled: true,
      streamUrl: 'https://example.test/station-one.mp3',
      stationIndex: 0,
      stationName: 'One',
      ...params,
    },
    ...overrides,
  };
}

function runtime(playSpatialSample = vi.fn().mockResolvedValue(true)): RadioStationRuntime {
  return new RadioStationRuntime(
    {
      context: null,
      ensureContext: vi.fn().mockResolvedValue(undefined),
      playSample: vi.fn().mockResolvedValue(true),
      playSpatialSample,
      getOutputDestinationNode: vi.fn(() => null),
      getOutputMode: vi.fn(() => 'stereo'),
      supportsStereoPanner: vi.fn(() => false),
    } as never,
    () => ({ range: 8, directional: false, facingDeg: 0 }),
  );
}

describe('RadioStationRuntime station switch cues', () => {
  beforeEach(() => {
    storage.clear();
    installLocalStorage();
  });

  it('does not play station static when reconnect recovery rebuilds the same radio station', async () => {
    const playSpatialSample = vi.fn().mockResolvedValue(true);
    const subject = runtime(playSpatialSample);
    const item = radio();

    await subject.sync([item], { x: 50, y: 50, locationId: 'hallway' });
    subject.resetPlaybackRecovery();
    await subject.sync([item], { x: 50, y: 50, locationId: 'hallway' });

    expect(playSpatialSample).not.toHaveBeenCalled();
  });

  it('does not play station static when a room radio disappears and rejoins with the same station', async () => {
    const playSpatialSample = vi.fn().mockResolvedValue(true);
    const subject = runtime(playSpatialSample);
    const item = radio();

    await subject.sync([item], { x: 50, y: 50, locationId: 'hallway' });
    await subject.sync([], { x: 50, y: 50, locationId: 'kitchen' });
    await subject.sync([item], { x: 50, y: 50, locationId: 'hallway' });

    expect(playSpatialSample).not.toHaveBeenCalled();
  });

  it('plays the station cue when the radio station actually changes', async () => {
    const playSpatialSample = vi.fn().mockResolvedValue(true);
    const subject = runtime(playSpatialSample);

    await subject.sync([radio()], { x: 50, y: 50, locationId: 'hallway' });
    await subject.sync([
      radio({}, {
        streamUrl: 'https://example.test/station-two.mp3',
        stationIndex: 1,
        stationName: 'Two',
      }),
    ], { x: 50, y: 50, locationId: 'hallway' });

    expect(playSpatialSample).toHaveBeenCalledOnce();
    expect(playSpatialSample.mock.calls[0][0]).toBe('sounds/radio/station-switch/two.mp3');
  });
});
