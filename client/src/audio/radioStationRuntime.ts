import { HEARING_RADIUS, type WorldItem } from '../state/gameState';
import { EFFECT_IDS, clampEffectLevel, connectEffectChain, disconnectEffectRuntime, type EffectId, type EffectRuntime } from './effects';
import { AudioEngine } from './audioEngine';
import {
  connectDistanceReflections,
  disconnectDistanceReflections,
  updateDistanceReflections,
  type DistanceReflectionRuntime,
} from './distanceReflections';
import { freshRadioPlaybackUrl, getProxyUrlForMedia, shouldProxyExternalMediaUrl } from './mediaUrl';
import { applySpatialMixToNodes, resolveSpatialMix } from './spatial';
import { volumePercentToGain } from './volume';
import Hls from 'hls.js';

export const RADIO_CHANNEL_OPTIONS = ['stereo', 'mono', 'left', 'right'] as const;
export type RadioChannelMode = (typeof RADIO_CHANNEL_OPTIONS)[number];
export const RADIO_SPEAKER_ROLE_OPTIONS = ['primary', 'sub', 'low', 'mid', 'high', 'high_low_bass'] as const;
export type RadioSpeakerRole = (typeof RADIO_SPEAKER_ROLE_OPTIONS)[number];
const RADIO_SWITCH_SOUND_BASE = 'sounds/radio/station-switch';

type RadioBodyFilters = {
  highpass: BiquadFilterNode;
  lowpass: BiquadFilterNode;
  presence: BiquadFilterNode;
  tone: BiquadFilterNode;
};

type RadioToneProfile = 'low' | 'mid' | 'high';

type SharedRadioSource = {
  streamUrl: string;
  element: HTMLAudioElement;
  source: MediaElementAudioSourceNode;
  hls: Hls | null;
  refCount: number;
  playStartedAt: number;
  resumeApplied: boolean;
  failureTimer: number | null;
  failureSignaled: boolean;
  signalFailure: () => void;
};

type ItemRadioOutput = {
  streamUrl: string;
  channel: RadioChannelMode;
  sharedSource: MediaElementAudioSourceNode;
  sourceInput: GainNode;
  channelSplitter: ChannelSplitterNode | null;
  channelMerger: ChannelMergerNode | null;
  channelLeftGain: GainNode | null;
  channelRightGain: GainNode | null;
  effectInput: GainNode;
  effectRuntime: EffectRuntime | null;
  effect: EffectId;
  effectValue: number;
  speakerRole: RadioSpeakerRole;
  speakerFilterInput: GainNode;
  speakerFilterNodes: BiquadFilterNode[];
  radioBodyInput: GainNode;
  radioBodyFilters: RadioBodyFilters;
  radioToneProfile: RadioToneProfile | null;
  gain: GainNode;
  panner: StereoPannerNode | null;
  reflections: DistanceReflectionRuntime;
};

type EffectiveRadioItem = {
  streamUrl: string;
  enabled: boolean;
  stationIndex: number;
  stationName: string;
  mediaChannel: unknown;
  mediaVolume: unknown;
  mediaEffect: unknown;
  mediaEffectValue: unknown;
  speakerRole: RadioSpeakerRole;
  playStartedAt: number;
};

export function normalizeRadioEffect(effect: unknown): EffectId {
  if (typeof effect !== 'string') return 'off';
  const normalized = effect.trim().toLowerCase() as EffectId;
  return EFFECT_IDS.has(normalized) ? normalized : 'off';
}

export function normalizeRadioEffectValue(effectValue: unknown): number {
  if (typeof effectValue !== 'number' || !Number.isFinite(effectValue)) {
    return 50;
  }
  return clampEffectLevel(effectValue);
}

export function normalizeRadioChannel(channel: unknown): RadioChannelMode {
  if (typeof channel !== 'string') return 'stereo';
  const normalized = channel.trim().toLowerCase() as RadioChannelMode;
  return (RADIO_CHANNEL_OPTIONS as readonly string[]).includes(normalized) ? normalized : 'stereo';
}

export function normalizeRadioSpeakerRole(role: unknown): RadioSpeakerRole {
  if (typeof role !== 'string') return 'primary';
  const normalized = role.trim().toLowerCase();
  if (normalized === 'bass' || normalized === 'subwoofer') return 'sub';
  if (normalized === 'hi' || normalized === 'treble') return 'high';
  if (normalized === 'high_low' || normalized === 'highlow' || normalized === 'hi_low_bass' || normalized === 'hilowbass') {
    return 'high_low_bass';
  }
  return (RADIO_SPEAKER_ROLE_OPTIONS as readonly string[]).includes(normalized)
    ? (normalized as RadioSpeakerRole)
    : 'primary';
}

/** Connects a shared radio media source according to channel mode. */
function connectRadioChannelSource(
  audioCtx: AudioContext,
  sharedSource: MediaElementAudioSourceNode,
  channel: RadioChannelMode,
  destination: GainNode,
): {
  sourceInput: GainNode;
  channelSplitter: ChannelSplitterNode | null;
  channelMerger: ChannelMergerNode | null;
  channelLeftGain: GainNode | null;
  channelRightGain: GainNode | null;
} {
  const sourceInput = audioCtx.createGain();
  sourceInput.gain.value = 1;

  if (channel === 'stereo') {
    sharedSource.connect(sourceInput);
    sourceInput.connect(destination);
    return {
      sourceInput,
      channelSplitter: null,
      channelMerger: null,
      channelLeftGain: null,
      channelRightGain: null,
    };
  }

  const splitter = audioCtx.createChannelSplitter(2);
  const merger = audioCtx.createChannelMerger(1);
  sharedSource.connect(splitter);

  let leftGain: GainNode | null = null;
  let rightGain: GainNode | null = null;
  if (channel === 'mono') {
    leftGain = audioCtx.createGain();
    rightGain = audioCtx.createGain();
    leftGain.gain.value = 0.5;
    rightGain.gain.value = 0.5;
    splitter.connect(leftGain, 0);
    splitter.connect(rightGain, 1);
    leftGain.connect(merger, 0, 0);
    rightGain.connect(merger, 0, 0);
  } else if (channel === 'left') {
    splitter.connect(merger, 0, 0);
  } else {
    splitter.connect(merger, 1, 0);
  }

  merger.connect(sourceInput);
  sourceInput.connect(destination);
  return {
    sourceInput,
    channelSplitter: splitter,
    channelMerger: merger,
    channelLeftGain: leftGain,
    channelRightGain: rightGain,
  };
}

/** Connects an item's speaker-role EQ chain between the effect output and final gain. */
function connectSpeakerRoleFilter(
  audioCtx: AudioContext,
  destination: GainNode,
  speakerRole: RadioSpeakerRole,
): { input: GainNode; filters: BiquadFilterNode[] } {
  const input = audioCtx.createGain();
  input.gain.value = 1;
  if (speakerRole === 'primary') {
    input.connect(destination);
    return { input, filters: [] };
  }

  const filters: BiquadFilterNode[] = [];
  const addFilter = (type: BiquadFilterType, frequency: number, q = 0.707): BiquadFilterNode => {
    const filter = audioCtx.createBiquadFilter();
    filter.type = type;
    filter.frequency.value = frequency;
    filter.Q.value = q;
    filters.push(filter);
    return filter;
  };

  if (speakerRole === 'sub') {
    addFilter('lowpass', 130, 0.9);
  } else if (speakerRole === 'low') {
    addFilter('highpass', 90, 0.7);
    addFilter('lowpass', 420, 0.9);
  } else if (speakerRole === 'mid') {
    addFilter('bandpass', 950, 1.1);
  } else if (speakerRole === 'high') {
    addFilter('highpass', 2600, 0.8);
  } else if (speakerRole === 'high_low_bass') {
    addFilter('highpass', 90, 0.7);
    addFilter('lowpass', 420, 0.9);
  }

  let previous: AudioNode = input;
  for (const filter of filters) {
    previous.connect(filter);
    previous = filter;
  }
  previous.connect(destination);
  return { input, filters };
}

/** Adds the constant radio-speaker body EQ after stream/effects/speaker-role processing. */
function connectRadioBodyEq(
  audioCtx: AudioContext,
  destination: GainNode,
): { input: GainNode; filters: RadioBodyFilters } {
  const input = audioCtx.createGain();
  input.gain.value = 1;

  const highpass = audioCtx.createBiquadFilter();
  highpass.type = 'highpass';
  highpass.frequency.value = 170;
  highpass.Q.value = 0.7;

  const presence = audioCtx.createBiquadFilter();
  presence.type = 'peaking';
  presence.frequency.value = 1550;
  presence.Q.value = 1.25;
  presence.gain.value = 3.5;

  const tone = audioCtx.createBiquadFilter();
  tone.type = 'peaking';
  tone.frequency.value = 850;
  tone.Q.value = 1.1;
  tone.gain.value = 0;

  const lowpass = audioCtx.createBiquadFilter();
  lowpass.type = 'lowpass';
  lowpass.frequency.value = 5200;
  lowpass.Q.value = 0.7;

  input.connect(highpass).connect(presence).connect(tone).connect(lowpass).connect(destination);
  return { input, filters: { highpass, lowpass, presence, tone } };
}

export function shouldProxyStreamUrl(streamUrl: string): boolean {
  return shouldProxyExternalMediaUrl(streamUrl);
}

export function getProxyUrlForStream(streamUrl: string): string {
  return getProxyUrlForMedia(streamUrl);
}

/** Appends a cache-buster query parameter to avoid stale stream buffers between sessions. */
function freshStreamUrl(streamUrl: string): string {
  return freshRadioPlaybackUrl(streamUrl);
}

/** Returns whether a URL path or proxied target points at an HLS playlist. */
function urlLooksLikeHlsPlaylist(parsed: URL): boolean {
  if (parsed.pathname.toLowerCase().endsWith('.m3u8')) return true;
  const proxiedUrl = parsed.searchParams.get('url');
  if (!proxiedUrl) return false;
  try {
    return new URL(proxiedUrl).pathname.toLowerCase().endsWith('.m3u8');
  } catch {
    return proxiedUrl.toLowerCase().split('?')[0].endsWith('.m3u8');
  }
}

type RadioSpatialConfig = {
  range: number;
  directional: boolean;
  facingDeg: number;
};

type ListenerPosition = {
  x: number;
  y: number;
  locationId?: string;
};

const SUBSCRIBE_PRELOAD_SQUARES = 5;
const UNSUBSCRIBE_HYSTERESIS_SQUARES = 8;
const STREAM_PLAY_RETRY_MS = 5000;
const STREAM_PLAY_MAX_RETRIES = 6;
const STREAM_STALLED_READY_STATE = HTMLMediaElement.HAVE_CURRENT_DATA;
const STATION_SWITCH_GAIN = 0.22;
const STATION_SWITCH_PLAYBACK_RATE = 1.42;
const STATION_SWITCH_MAX_RANGE = 6;
const RADIO_RESUME_STORAGE_KEY = 'chatGridRadioResumeState';
const RADIO_RESUME_MAX_ITEMS = 80;
const RADIO_RESUME_MAX_AGE_MS = 1000 * 60 * 60 * 24 * 30;
const RADIO_SPEAKER_SPATIAL_FADE_SECONDS = 0.45;
const RADIO_SPEAKER_MUTE_FADE_SECONDS = 0.45;
const RADIO_STREAM_REPLACE_FADE_MS = 1100;

type PersistedRadioResumeState = {
  itemId: string;
  streamUrl: string;
  stationIndex: number;
  enabled: boolean;
  playStartedAt: number;
  currentTime: number;
  savedAt: number;
};

function resolveRadioPlaybackUrl(item: WorldItem): string {
  return String(item.params.playbackUrl || item.params.streamUrl || '').trim();
}

function isTvMediaItem(item: WorldItem): boolean {
  return item.type === 'house_object' && String(item.params.objectKind ?? '').trim().toLowerCase() === 'tv';
}

function isSpatialMediaItem(item: WorldItem): boolean {
  return item.type === 'radio_station' || isTvMediaItem(item);
}

function linkedMediaGroup(item: WorldItem): string {
  return String(item.params.linkedMediaGroup ?? '').trim().toLowerCase();
}

function normalizeStationIndex(value: unknown): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.round(parsed));
}

function normalizeStationName(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function normalizePlayStartedAt(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.round(parsed)) : 0;
}

function stationSoundSlug(value: string): string {
  const slug = value
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'radio';
}

function resolveStationSwitchSound(item: WorldItem, stationName: string): string | null {
  const explicit = String(item.params.stationSwitchSound ?? '').trim();
  if (explicit) return explicit;
  const presets = Array.isArray(item.params.stationPresets) ? item.params.stationPresets : [];
  const index = normalizeStationIndex(item.params.stationIndex);
  const preset = presets.length > 0 ? presets[index % presets.length] : null;
  if (preset && typeof preset === 'object') {
    const presetSound = String((preset as Record<string, unknown>).switchSound ?? '').trim();
    if (presetSound) return presetSound;
  }
  const name = stationName || normalizeStationName(item.params.stationName);
  return name ? `${RADIO_SWITCH_SOUND_BASE}/${stationSoundSlug(name)}.mp3` : null;
}

function isHlsPlaybackUrl(streamUrl: string): boolean {
  try {
    return urlLooksLikeHlsPlaylist(new URL(streamUrl));
  } catch {
    return streamUrl.toLowerCase().split('?')[0].endsWith('.m3u8');
  }
}

function loadRadioResumeState(): Map<string, PersistedRadioResumeState> {
  const raw = localStorage.getItem(RADIO_RESUME_STORAGE_KEY);
  if (!raw) return new Map();
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Map();
    const cutoff = Date.now() - RADIO_RESUME_MAX_AGE_MS;
    const entries = parsed
      .filter((entry): entry is PersistedRadioResumeState => {
        if (!entry || typeof entry !== 'object') return false;
        const record = entry as Record<string, unknown>;
        return (
          typeof record.itemId === 'string' &&
          typeof record.streamUrl === 'string' &&
          Number.isFinite(Number(record.savedAt)) &&
          Number(record.savedAt) >= cutoff
        );
      })
      .slice(-RADIO_RESUME_MAX_ITEMS);
    return new Map(entries.map((entry) => [entry.itemId, entry]));
  } catch {
    return new Map();
  }
}

function saveRadioResumeState(values: Map<string, PersistedRadioResumeState>): void {
  const cutoff = Date.now() - RADIO_RESUME_MAX_AGE_MS;
  const entries = Array.from(values.values())
    .filter((entry) => entry.savedAt >= cutoff)
    .slice(-RADIO_RESUME_MAX_ITEMS);
  localStorage.setItem(RADIO_RESUME_STORAGE_KEY, JSON.stringify(entries));
}

function resolveResumeOffsetSeconds(
  streamUrl: string,
  playStartedAt: number,
  fallback?: PersistedRadioResumeState,
): number {
  if (playStartedAt > 0) {
    return Math.max(0, (Date.now() - playStartedAt) / 1000);
  }
  if (fallback && fallback.streamUrl === streamUrl && fallback.enabled) {
    const elapsed = Math.max(0, (Date.now() - fallback.savedAt) / 1000);
    return Math.max(0, fallback.currentTime + elapsed);
  }
  return 0;
}

export class RadioStationRuntime {
  private readonly sharedRadioSources = new Map<string, SharedRadioSource>();
  private readonly itemRadioOutputs = new Map<string, ItemRadioOutput>();
  private readonly lastRadioStates = new Map<string, { streamUrl: string; enabled: boolean; stationIndex: number }>();
  private readonly persistedResumeStates = loadRadioResumeState();
  private readonly pendingSharedStarts = new Set<string>();
  private readonly nextSharedStartAtMs = new Map<string, number>();
  private readonly sharedStartFailureCount = new Map<string, number>();
  private layerEnabled = true;
  private listenerPositions: ListenerPosition[] = [];

  constructor(
    private readonly audio: AudioEngine,
    private readonly getSpatialConfig: (item: WorldItem) => RadioSpatialConfig,
    private readonly callbacks: { onStationFailure?: (itemId: string) => void } = {},
  ) {}

  cleanup(itemId: string, fadeMs = 0): void {
    const output = this.itemRadioOutputs.get(itemId);
    if (!output) return;
    this.itemRadioOutputs.delete(itemId);
    this.releaseOutput(output, fadeMs);
  }

  cleanupAll(): void {
    for (const id of Array.from(this.itemRadioOutputs.keys())) {
      this.cleanup(id);
    }
  }

  /**
   * Clears local playback runtimes and retry backoff before rebuilding streams
   * after a transport reconnect.
   */
  resetPlaybackRecovery(): void {
    this.cleanupAll();
    this.pendingSharedStarts.clear();
    this.nextSharedStartAtMs.clear();
    this.sharedStartFailureCount.clear();
  }

  /** Force paused, errored, or stalled active media elements to reload cleanly. */
  recoverActivePlayback(): void {
    for (const shared of this.sharedRadioSources.values()) {
      if (
        shared.element.error ||
        shared.element.paused ||
        shared.element.readyState <= STREAM_STALLED_READY_STATE
      ) {
        this.hardReloadSharedPlayback(shared);
      } else {
        this.tryStartSharedPlayback(shared);
      }
    }
  }

  async setLayerEnabled(
    enabled: boolean,
    items: Iterable<WorldItem>,
    listenerPosition: ListenerPosition | null = null,
  ): Promise<void> {
    this.layerEnabled = enabled;
    this.listenerPositions = listenerPosition ? [{ ...listenerPosition }] : [];
    if (!enabled) {
      this.cleanupAll();
      return;
    }
    await this.sync(items, this.listenerPositions);
  }

  async sync(
    items: Iterable<WorldItem>,
    listenerPositions: ListenerPosition[] | ListenerPosition | null = null,
  ): Promise<void> {
    if (!this.layerEnabled) {
      this.cleanupAll();
      return;
    }
    if (Array.isArray(listenerPositions)) {
      this.listenerPositions = listenerPositions.map((listener) => ({ ...listener }));
    } else if (listenerPositions) {
      this.listenerPositions = [{ ...listenerPositions }];
    }
    const listeners = this.listenerPositions;
    const itemList = Array.from(items);
    const validIds = new Set<string>();
    for (const item of itemList) {
      if (!isSpatialMediaItem(item)) continue;
      validIds.add(item.id);
      const effective = this.resolveEffectiveRadioItem(item, itemList);
      this.persistRadioResumeState(item, effective);
      this.playStateChangeCue(item, effective);
      if (!this.shouldKeepRuntime(item, effective, listeners, this.itemRadioOutputs.has(item.id), itemList)) {
        this.cleanup(item.id, effective.enabled ? 1200 : 300);
        continue;
      }
      await this.ensureRuntime(item, effective);
    }
    for (const id of Array.from(this.itemRadioOutputs.keys())) {
      if (!validIds.has(id)) {
        this.cleanup(id);
      }
    }
  }

  updateSpatialAudio(items: Map<string, WorldItem>, playerPosition: ListenerPosition): void {
    if (!this.layerEnabled) return;
    const audioCtx = this.audio.context;
    if (!audioCtx) return;
    for (const [itemId, output] of this.itemRadioOutputs.entries()) {
      const item = items.get(itemId);
      if (!item || !isSpatialMediaItem(item)) {
        this.cleanup(itemId);
        continue;
      }
      const effective = this.resolveEffectiveRadioItem(item, items.values());
      const streamUrl = effective.streamUrl;
      const enabled = effective.enabled;
      const normalizedVolume = volumePercentToGain(effective.mediaVolume, 50);
      const effect = normalizeRadioEffect(effective.mediaEffect);
      const effectValue = normalizeRadioEffectValue(effective.mediaEffectValue);
      this.applyEffect(output, audioCtx, effect, effectValue);
      this.applySpeakerRole(output, audioCtx, effective.speakerRole);
      if (!streamUrl || !enabled) {
        output.gain.gain.linearRampToValueAtTime(0, audioCtx.currentTime + RADIO_SPEAKER_MUTE_FADE_SECONDS);
        continue;
      }
      const shared = this.sharedRadioSources.get(output.streamUrl);
      if (shared) {
        this.tryStartSharedPlayback(shared);
      }
      const spatialConfig = this.getSpatialConfig(item);
      const inAdjacentRoom = this.isAdjacentRoomTv(item, playerPosition, items.values());
      const dx = item.x - playerPosition.x;
      const dy = item.y - playerPosition.y;
      const range = Math.max(1, spatialConfig.range || HEARING_RADIUS);
      this.applyRadioBodyTone(output, audioCtx, this.resolveRadioToneProfile(dx, dy, range, spatialConfig));
      const mix = resolveSpatialMix({
        // Room-to-room TV audio has no trustworthy shared coordinates. Keep it
        // centered and quieter rather than inventing a direction from unrelated
        // room-local grids.
        dx: inAdjacentRoom ? 0 : dx,
        dy: inAdjacentRoom ? Math.min(range, 4) : dy,
        range,
        baseGain: normalizedVolume * (inAdjacentRoom ? 0.42 : 1),
        nearFieldDistance: 1,
        nearFieldGain: 1,
        nearFieldCenterPan: true,
        farFieldRangeMultiplier: 2.2,
        farFieldFloorGain: 0.04,
        directional: {
          enabled: spatialConfig.directional,
          facingDeg: spatialConfig.facingDeg,
          coneDeg: 120,
          rearGain: 0.4,
        },
      });
      applySpatialMixToNodes({
        audioCtx,
        gainNode: output.gain,
        pannerNode: output.panner,
        mix,
        outputMode: this.audio.getOutputMode(),
        transition: 'target',
        transitionSeconds: RADIO_SPEAKER_SPATIAL_FADE_SECONDS,
      });
      updateDistanceReflections({
        audioCtx,
        runtime: output.reflections,
        mix,
        range,
        outputMode: this.audio.getOutputMode(),
        maxWetGain: 0.14,
      });
    }
  }

  private resolveEffectiveRadioItem(item: WorldItem, items: Iterable<WorldItem>): EffectiveRadioItem {
    const group = linkedMediaGroup(item);
    const syncWithPrimary = item.params.syncWithPrimary === true && group.length > 0;
    const primary =
      syncWithPrimary && normalizeRadioSpeakerRole(item.params.speakerRole) !== 'primary'
        ? Array.from(items)
            .filter(
              (candidate) =>
                candidate.id !== item.id &&
                isSpatialMediaItem(candidate) &&
                candidate.locationId === item.locationId &&
                linkedMediaGroup(candidate) === group &&
                normalizeRadioSpeakerRole(candidate.params.speakerRole) === 'primary',
            )
            .sort((left, right) => left.id.localeCompare(right.id))[0] ?? null
        : null;
    return {
      streamUrl: primary ? resolveRadioPlaybackUrl(primary) : resolveRadioPlaybackUrl(item),
      enabled: item.params.enabled !== false && (!primary || primary.params.enabled !== false),
      stationIndex: normalizeStationIndex(item.params.stationIndex),
      stationName: primary
        ? normalizeStationName(primary.params.stationName)
        : normalizeStationName(item.params.stationName),
      mediaChannel: item.params.mediaChannel,
      mediaVolume: item.params.mediaVolume,
      mediaEffect: item.params.mediaEffect,
      mediaEffectValue: item.params.mediaEffectValue,
      speakerRole: normalizeRadioSpeakerRole(item.params.speakerRole),
      playStartedAt: primary
        ? normalizePlayStartedAt(primary.params.playStartedAt)
        : normalizePlayStartedAt(item.params.playStartedAt),
    };
  }

  private applyEffect(
    output: ItemRadioOutput,
    audioCtx: AudioContext,
    effect: EffectId,
    effectValue: number,
  ): void {
    if (output.effect === effect && output.effectValue === effectValue) {
      return;
    }
    output.effectInput.disconnect();
    disconnectEffectRuntime(output.effectRuntime);
    output.effectRuntime = connectEffectChain(audioCtx, output.effectInput, output.speakerFilterInput, effect, effectValue);
    output.effect = effect;
    output.effectValue = effectValue;
  }

  private applySpeakerRole(
    output: ItemRadioOutput,
    audioCtx: AudioContext,
    speakerRole: RadioSpeakerRole,
  ): void {
    if (output.speakerRole === speakerRole) {
      return;
    }
    output.effectInput.disconnect();
    output.speakerFilterInput.disconnect();
    for (const filter of output.speakerFilterNodes) {
      filter.disconnect();
    }
    disconnectEffectRuntime(output.effectRuntime);
    const filterChain = connectSpeakerRoleFilter(audioCtx, output.radioBodyInput, speakerRole);
    output.speakerFilterInput = filterChain.input;
    output.speakerFilterNodes = filterChain.filters;
    output.effectRuntime = connectEffectChain(audioCtx, output.effectInput, output.speakerFilterInput, output.effect, output.effectValue);
    output.speakerRole = speakerRole;
  }

  private applyRadioBodyTone(
    output: ItemRadioOutput,
    audioCtx: AudioContext,
    toneProfile: RadioToneProfile,
  ): void {
    if (output.radioToneProfile === toneProfile) return;
    const now = audioCtx.currentTime;
    const filters = output.radioBodyFilters;
    const profiles: Record<
      RadioToneProfile,
      { lowpass: number; presenceGain: number; toneFrequency: number; toneGain: number }
    > = {
      low: { lowpass: 1050, presenceGain: -3.5, toneFrequency: 260, toneGain: 5.5 },
      mid: { lowpass: 2850, presenceGain: 1.5, toneFrequency: 920, toneGain: 3 },
      high: { lowpass: 6100, presenceGain: 4.5, toneFrequency: 2350, toneGain: 4 },
    };
    const profile = profiles[toneProfile];
    filters.lowpass.frequency.setTargetAtTime(profile.lowpass, now, 0.12);
    filters.presence.gain.setTargetAtTime(profile.presenceGain, now, 0.12);
    filters.tone.frequency.setTargetAtTime(profile.toneFrequency, now, 0.12);
    filters.tone.gain.setTargetAtTime(profile.toneGain, now, 0.12);
    output.radioToneProfile = toneProfile;
  }

  private resolveRadioToneProfile(
    dx: number,
    dy: number,
    range: number,
    spatialConfig: RadioSpatialConfig,
  ): RadioToneProfile {
    const distanceRatio = Math.min(1, Math.hypot(dx, dy) / Math.max(1, range));
    if (!spatialConfig.directional || (dx === 0 && dy === 0)) {
      if (distanceRatio < 0.26) return 'high';
      if (distanceRatio < 0.68) return 'mid';
      return 'low';
    }
    const sourceToListenerDeg = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
    const diff = Math.abs((((sourceToListenerDeg - spatialConfig.facingDeg + 540) % 360) - 180));
    const facingScore = Math.max(0, 1 - diff / 150);
    const clarity = (1 - distanceRatio) * 0.58 + facingScore * 0.42;
    if (clarity > 0.68) return 'high';
    if (clarity > 0.34) return 'mid';
    return 'low';
  }

  private releaseSharedSource(streamUrl: string): void {
    const shared = this.sharedRadioSources.get(streamUrl);
    if (!shared) return;
    shared.refCount -= 1;
    if (shared.refCount > 0) return;
    if (shared.failureTimer !== null) window.clearTimeout(shared.failureTimer);
    shared.element.pause();
    if (shared.hls) {
      shared.hls.destroy();
    }
    shared.element.src = '';
    shared.source.disconnect();
    this.sharedRadioSources.delete(streamUrl);
    this.pendingSharedStarts.delete(streamUrl);
    this.nextSharedStartAtMs.delete(streamUrl);
    this.sharedStartFailureCount.delete(streamUrl);
  }

  private releaseOutput(output: ItemRadioOutput, fadeMs: number): void {
    const audioCtx = this.audio.context;
    const disconnect = (): void => {
      if (output.channelSplitter) {
        try {
          output.sharedSource.disconnect(output.channelSplitter);
        } catch {
          // Ignore stale graph disconnects.
        }
      } else {
        try {
          output.sharedSource.disconnect(output.sourceInput);
        } catch {
          // Ignore stale graph disconnects.
        }
      }
      output.channelLeftGain?.disconnect();
      output.channelRightGain?.disconnect();
      output.channelSplitter?.disconnect();
      output.channelMerger?.disconnect();
      output.sourceInput.disconnect();
      output.effectInput.disconnect();
      disconnectEffectRuntime(output.effectRuntime);
      output.speakerFilterInput.disconnect();
      for (const filter of output.speakerFilterNodes) {
        filter.disconnect();
      }
      output.radioBodyInput.disconnect();
      output.radioBodyFilters.highpass.disconnect();
      output.radioBodyFilters.lowpass.disconnect();
      output.radioBodyFilters.presence.disconnect();
      output.radioBodyFilters.tone.disconnect();
      output.gain.disconnect();
      output.panner?.disconnect();
      disconnectDistanceReflections(output.reflections);
      this.releaseSharedSource(output.streamUrl);
    };
    if (!audioCtx || fadeMs <= 0) {
      disconnect();
      return;
    }
    const now = audioCtx.currentTime;
    try {
      output.gain.gain.cancelScheduledValues(now);
      output.gain.gain.setValueAtTime(output.gain.gain.value, now);
      output.gain.gain.linearRampToValueAtTime(0, now + fadeMs / 1000);
    } catch {
      // If the automation fails, immediate cleanup is safer than leaking nodes.
      disconnect();
      return;
    }
    window.setTimeout(disconnect, fadeMs + 80);
  }

  private getOrCreateSharedSource(
    streamUrl: string,
    playStartedAt: number,
    fallback?: PersistedRadioResumeState,
  ): SharedRadioSource | null {
    const existing = this.sharedRadioSources.get(streamUrl);
    if (existing) {
      existing.refCount += 1;
      if (playStartedAt > 0 && existing.playStartedAt !== playStartedAt) {
        existing.playStartedAt = playStartedAt;
        existing.resumeApplied = false;
        this.applyResumeOffset(existing, resolveResumeOffsetSeconds(streamUrl, playStartedAt, fallback));
      }
      return existing;
    }
    const audioCtx = this.audio.context;
    if (!audioCtx) return null;
    const element = new Audio();
    element.crossOrigin = 'anonymous';
    element.loop = true;
    element.preload = 'none';
    let hls: Hls | null = null;
    const playbackUrl = freshStreamUrl(streamUrl);
    if (isHlsPlaybackUrl(playbackUrl) && Hls.isSupported()) {
      hls = new Hls({
        enableWorker: true,
        lowLatencyMode: false,
        maxBufferLength: 20,
        maxMaxBufferLength: 40,
        backBufferLength: 30,
      });
      hls.loadSource(playbackUrl);
      hls.attachMedia(element);
    } else {
      element.src = playbackUrl;
    }
    const source = audioCtx.createMediaElementSource(element);
    const shared: SharedRadioSource = {
      streamUrl,
      element,
      source,
      hls,
      refCount: 1,
      playStartedAt,
      resumeApplied: false,
      failureTimer: null,
      failureSignaled: false,
    };
    this.sharedRadioSources.set(streamUrl, shared);
    const signalFailure = (): void => {
      if (shared.failureSignaled || shared.refCount <= 0) return;
      shared.failureSignaled = true;
      void this.audio.playSample('sounds/radio/vinyl-static.mp3', 0.58, 0);
      shared.failureTimer = window.setTimeout(() => {
        shared.failureTimer = null;
        const itemId = this.findItemIdForStream(streamUrl);
        if (itemId) this.callbacks.onStationFailure?.(itemId);
      }, 2800);
    };
    element.addEventListener('error', signalFailure);
    element.addEventListener('stalled', () => {
      if (shared.element.paused && shared.element.readyState <= STREAM_STALLED_READY_STATE) signalFailure();
    });
    shared.signalFailure = signalFailure;
    this.applyResumeOffset(shared, resolveResumeOffsetSeconds(streamUrl, playStartedAt, fallback));
    this.tryStartSharedPlayback(shared);
    return shared;
  }

  private findItemIdForStream(streamUrl: string): string {
    for (const [itemId, output] of this.itemRadioOutputs.entries()) {
      if (output.streamUrl === streamUrl) return itemId;
    }
    return '';
  }

  private applyResumeOffset(shared: SharedRadioSource, offsetSeconds: number): void {
    if (shared.resumeApplied || offsetSeconds <= 0 || isHlsPlaybackUrl(shared.streamUrl)) {
      shared.resumeApplied = true;
      return;
    }
    const seek = (): void => {
      if (shared.resumeApplied) return;
      const duration = shared.element.duration;
      if (!Number.isFinite(duration) || duration <= 0) {
        shared.resumeApplied = true;
        return;
      }
      const target = duration > 2 ? offsetSeconds % duration : 0;
      try {
        shared.element.currentTime = Math.max(0, Math.min(duration - 0.5, target));
      } catch {
        // Some remote media streams reject seeking even when duration is exposed.
      }
      shared.resumeApplied = true;
    };
    if (shared.element.readyState >= HTMLMediaElement.HAVE_METADATA) {
      seek();
      return;
    }
    shared.element.addEventListener('loadedmetadata', seek, { once: true });
  }

  private tryStartSharedPlayback(shared: SharedRadioSource): void {
    if (!shared.element.paused) {
      this.nextSharedStartAtMs.delete(shared.streamUrl);
      return;
    }
    if (this.pendingSharedStarts.has(shared.streamUrl)) {
      return;
    }
    const now = Date.now();
    const retryAt = this.nextSharedStartAtMs.get(shared.streamUrl) ?? 0;
    if (now < retryAt) {
      return;
    }
    this.pendingSharedStarts.add(shared.streamUrl);
    if (shared.element.error) {
      this.hardReloadSharedPlayback(shared);
    }
    void shared.element
      .play()
      .then(() => {
        this.nextSharedStartAtMs.delete(shared.streamUrl);
        this.sharedStartFailureCount.delete(shared.streamUrl);
      })
      .catch(() => {
        const failures = (this.sharedStartFailureCount.get(shared.streamUrl) ?? 0) + 1;
        if (failures >= STREAM_PLAY_MAX_RETRIES) {
          this.hardReloadSharedPlayback(shared);
          this.sharedStartFailureCount.set(shared.streamUrl, 0);
          this.nextSharedStartAtMs.set(shared.streamUrl, Date.now() + STREAM_PLAY_RETRY_MS);
          return;
        }
        this.sharedStartFailureCount.set(shared.streamUrl, failures);
        this.nextSharedStartAtMs.set(shared.streamUrl, Date.now() + STREAM_PLAY_RETRY_MS);
      })
      .finally(() => {
        this.pendingSharedStarts.delete(shared.streamUrl);
      });
  }

  private hardReloadSharedPlayback(shared: SharedRadioSource): void {
    this.pendingSharedStarts.delete(shared.streamUrl);
    this.nextSharedStartAtMs.delete(shared.streamUrl);
    this.sharedStartFailureCount.delete(shared.streamUrl);
    shared.resumeApplied = false;
    const playbackUrl = freshStreamUrl(shared.streamUrl);
    try {
      if (shared.hls) {
        shared.hls.stopLoad();
        shared.hls.recoverMediaError();
        shared.hls.loadSource(playbackUrl);
        shared.hls.startLoad();
      } else {
        shared.element.pause();
        shared.element.src = playbackUrl;
        shared.element.load();
      }
    } catch {
      // Ignore stale media reload failures; the next retry will create a new attempt.
    }
    this.applyResumeOffset(shared, resolveResumeOffsetSeconds(shared.streamUrl, shared.playStartedAt));
  }

  private async ensureRuntime(item: WorldItem, effective: EffectiveRadioItem): Promise<void> {
    const streamUrl = effective.streamUrl;
    if (!streamUrl) {
      this.cleanup(item.id);
      return;
    }
    await this.audio.ensureContext();
    const audioCtx = this.audio.context;
    if (!audioCtx) return;

    const channel = normalizeRadioChannel(effective.mediaChannel);
    const speakerRole = effective.speakerRole;
    const existing = this.itemRadioOutputs.get(item.id);
    if (existing && existing.streamUrl === streamUrl && existing.channel === channel) {
      this.applySpeakerRole(existing, audioCtx, speakerRole);
      const shared = this.sharedRadioSources.get(existing.streamUrl);
      if (shared) {
        this.tryStartSharedPlayback(shared);
      }
      return;
    }
    if (existing) {
      this.cleanup(item.id, RADIO_STREAM_REPLACE_FADE_MS);
    }

    const shared = this.getOrCreateSharedSource(
      streamUrl,
      effective.playStartedAt,
      this.persistedResumeStates.get(item.id),
    );
    if (!shared) return;

    const gain = audioCtx.createGain();
    gain.gain.value = 0;
    const effectInput = audioCtx.createGain();
    const channelSource = connectRadioChannelSource(audioCtx, shared.source, channel, effectInput);
    const effect = normalizeRadioEffect(effective.mediaEffect);
    const effectValue = normalizeRadioEffectValue(effective.mediaEffectValue);
    const radioBody = connectRadioBodyEq(audioCtx, gain);
    const speakerFilter = connectSpeakerRoleFilter(audioCtx, radioBody.input, speakerRole);
    const effectRuntime = connectEffectChain(audioCtx, effectInput, speakerFilter.input, effect, effectValue);
    const destination = this.audio.getOutputDestinationNode() ?? audioCtx.destination;
    let panner: StereoPannerNode | null = null;
    if (this.audio.supportsStereoPanner()) {
      panner = audioCtx.createStereoPanner();
      gain.connect(panner).connect(destination);
    } else {
      gain.connect(destination);
    }
    const reflections = connectDistanceReflections(audioCtx, gain, destination, this.audio.supportsStereoPanner());
    this.itemRadioOutputs.set(item.id, {
      streamUrl,
      channel,
      sharedSource: shared.source,
      sourceInput: channelSource.sourceInput,
      channelSplitter: channelSource.channelSplitter,
      channelMerger: channelSource.channelMerger,
      channelLeftGain: channelSource.channelLeftGain,
      channelRightGain: channelSource.channelRightGain,
      effectInput,
      effectRuntime,
      effect,
      effectValue,
      speakerRole,
      speakerFilterInput: speakerFilter.input,
      speakerFilterNodes: speakerFilter.filters,
      radioBodyInput: radioBody.input,
      radioBodyFilters: radioBody.filters,
      radioToneProfile: null,
      gain,
      panner,
      reflections,
    });
  }

  private persistRadioResumeState(item: WorldItem, effective: EffectiveRadioItem): void {
    const existingOutput = this.itemRadioOutputs.get(item.id);
    const shared = existingOutput ? this.sharedRadioSources.get(existingOutput.streamUrl) : null;
    const currentTime =
      shared && Number.isFinite(shared.element.currentTime) ? Math.max(0, shared.element.currentTime) : 0;
    this.persistedResumeStates.set(item.id, {
      itemId: item.id,
      streamUrl: effective.streamUrl,
      stationIndex: effective.stationIndex,
      enabled: effective.enabled,
      playStartedAt: effective.playStartedAt,
      currentTime,
      savedAt: Date.now(),
    });
    saveRadioResumeState(this.persistedResumeStates);
  }

  private playStateChangeCue(item: WorldItem, effective: EffectiveRadioItem): void {
    const itemId = item.id;
    const previous = this.lastRadioStates.get(itemId);
    this.lastRadioStates.set(itemId, {
      streamUrl: effective.streamUrl,
      enabled: effective.enabled,
      stationIndex: effective.stationIndex,
    });
    if (!previous) return;
    if (previous.enabled !== effective.enabled) {
      this.playPowerCue(effective.enabled);
      return;
    }
    if (
      effective.enabled &&
      (previous.streamUrl !== effective.streamUrl || previous.stationIndex !== effective.stationIndex)
    ) {
      const stationCue = resolveStationSwitchSound(item, effective.stationName);
      const listenerPosition = this.listenerPositions[0] ?? null;
      const spatialConfig = this.getSpatialConfig(item);
      const cueRange = Math.max(2, Math.min(spatialConfig.range || HEARING_RADIUS, STATION_SWITCH_MAX_RANGE));
      if (stationCue) {
        if (listenerPosition) {
          void this.audio.playSpatialSample(
            stationCue,
            { x: item.x, y: item.y },
            listenerPosition,
            STATION_SWITCH_GAIN,
            cueRange,
            STATION_SWITCH_PLAYBACK_RATE,
          );
        } else {
          void this.audio.playSample(stationCue, STATION_SWITCH_GAIN, 6, STATION_SWITCH_PLAYBACK_RATE);
        }
      } else {
        this.playTuneCue(item, listenerPosition, cueRange);
      }
    }
  }

  private playPowerCue(poweredOn: boolean): void {
    const audioCtx = this.audio.context;
    const destination = this.audio.getOutputDestinationNode();
    if (!audioCtx || !destination) return;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'square';
    osc.frequency.setValueAtTime(poweredOn ? 180 : 150, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(poweredOn ? 440 : 70, audioCtx.currentTime + 0.08);
    gain.gain.setValueAtTime(0.0001, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.12, audioCtx.currentTime + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.12);
    osc.connect(gain).connect(destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.13);
    osc.onended = () => {
      osc.disconnect();
      gain.disconnect();
    };
  }

  private playTuneCue(
    item: WorldItem,
    listenerPosition: { x: number; y: number } | null,
    range: number,
  ): void {
    const audioCtx = this.audio.context;
    const destination = this.audio.getOutputDestinationNode();
    if (!audioCtx || !destination) return;
    const mix = listenerPosition
      ? resolveSpatialMix({
          dx: item.x - listenerPosition.x,
          dy: item.y - listenerPosition.y,
          range,
          baseGain: STATION_SWITCH_GAIN,
          nearFieldDistance: 1,
          nearFieldGain: 0.82,
          nearFieldCenterPan: true,
        })
      : null;
    if (listenerPosition && (!mix || mix.gain <= 0)) return;
    const osc = audioCtx.createOscillator();
    const filter = audioCtx.createBiquadFilter();
    const gain = audioCtx.createGain();
    osc.type = 'sawtooth';
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(420, audioCtx.currentTime);
    filter.frequency.exponentialRampToValueAtTime(3200, audioCtx.currentTime + 0.2);
    filter.Q.value = 6;
    osc.frequency.setValueAtTime(95, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(620, audioCtx.currentTime + 0.18);
    const peakGain = mix ? Math.max(0.0001, mix.gain) : STATION_SWITCH_GAIN * 0.36;
    gain.gain.setValueAtTime(0.0001, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(peakGain, audioCtx.currentTime + 0.014);
    gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.24);
    let panner: StereoPannerNode | null = null;
    if (mix && this.audio.supportsStereoPanner() && this.audio.getOutputMode() === 'stereo') {
      panner = audioCtx.createStereoPanner();
      panner.pan.setValueAtTime(Math.max(-1, Math.min(1, mix.pan)), audioCtx.currentTime);
      osc.connect(filter).connect(gain).connect(panner).connect(destination);
    } else {
      osc.connect(filter).connect(gain).connect(destination);
    }
    osc.start();
    osc.stop(audioCtx.currentTime + 0.26);
    osc.onended = () => {
      osc.disconnect();
      filter.disconnect();
      gain.disconnect();
      panner?.disconnect();
    };
  }

  private shouldKeepRuntime(
    item: WorldItem,
    effective: EffectiveRadioItem,
    listenerPositions: ListenerPosition[],
    currentlyActive: boolean,
    items: Iterable<WorldItem>,
  ): boolean {
    if (!effective.streamUrl || !effective.enabled || listenerPositions.length === 0) {
      return false;
    }
    const spatialConfig = this.getSpatialConfig(item);
    const baseRange = Math.max(1, spatialConfig.range || HEARING_RADIUS);
    const audibleRange = baseRange * 2.2;
    const threshold = audibleRange + (currentlyActive ? UNSUBSCRIBE_HYSTERESIS_SQUARES : SUBSCRIBE_PRELOAD_SQUARES);
    return listenerPositions.some((listenerPosition) => {
      if (this.isAdjacentRoomTv(item, listenerPosition, items)) return true;
      if (item.locationId && listenerPosition.locationId && item.locationId !== listenerPosition.locationId) {
        return false;
      }
      return Math.hypot(item.x - listenerPosition.x, item.y - listenerPosition.y) <= threshold;
    });
  }

  /** TVs can carry through a connected doorway; ordinary item layers cannot. */
  private isAdjacentRoomTv(
    item: WorldItem,
    listener: ListenerPosition,
    items: Iterable<WorldItem>,
  ): boolean {
    if (!isTvMediaItem(item) || !item.locationId || !listener.locationId || item.locationId === listener.locationId) {
      return false;
    }
    const adjacent = new Set<string>();
    for (const candidate of items) {
      if (candidate.type !== 'service_link') continue;
      const kind = String(candidate.params.serviceKind ?? '').trim().toLowerCase();
      if (kind !== 'door') continue;
      const source = String(candidate.locationId ?? '').trim();
      const target = String(candidate.params.targetLocation ?? '').trim();
      if (!source || !target) continue;
      if (source === listener.locationId) adjacent.add(target);
      if (target === listener.locationId) adjacent.add(source);
    }
    return adjacent.has(item.locationId);
  }
}
