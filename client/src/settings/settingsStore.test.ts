import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsStore } from './settingsStore';

const STORAGE_KEY = 'chatGridAudioAnnouncementSettings';

describe('SettingsStore media announcement preferences', () => {
  const values = new Map<string, string>();

  beforeEach(() => {
    values.clear();
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('defaults radio and TV readouts to full', () => {
    const settings = new SettingsStore().loadAudioAnnouncementSettings();

    expect(settings.radioAnnouncementMode).toBe('full');
    expect(settings.tvAnnouncementMode).toBe('full');
  });

  it('preserves an existing radio choice while adding the TV default', () => {
    values.set(STORAGE_KEY, JSON.stringify({
      mode: 'full',
      radioAnnouncementMode: 'sounds_only',
      itemBeacons: true,
      movementDirections: false,
    }));

    const settings = new SettingsStore().loadAudioAnnouncementSettings();

    expect(settings.radioAnnouncementMode).toBe('sounds_only');
    expect(settings.tvAnnouncementMode).toBe('full');
  });

  it('persists independent radio and TV choices', () => {
    const store = new SettingsStore();
    store.saveAudioAnnouncementSettings({
      mode: 'full',
      radioAnnouncementMode: 'off',
      tvAnnouncementMode: 'sounds_only',
      itemBeacons: true,
      movementDirections: false,
    });

    expect(store.loadAudioAnnouncementSettings()).toMatchObject({
      radioAnnouncementMode: 'off',
      tvAnnouncementMode: 'sounds_only',
    });
  });
});
