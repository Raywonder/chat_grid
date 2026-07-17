import { HEARING_RADIUS } from '../state/gameState';
import {
  EFFECT_SEQUENCE,
  clampEffectLevel,
  connectEffectChain,
  disconnectEffectRuntime,
  type EffectId,
  type EffectRuntime,
} from './effects';
import {
  connectDistanceReflections,
  disconnectDistanceReflections,
  updateDistanceReflections,
  type DistanceReflectionRuntime,
} from './distanceReflections';
import { SPATIAL_TIME_CONSTANT_SECONDS, applySpatialMixToNodes, resolveSpatialMix } from './spatial';

export type SpatialPeerRuntime = {
  nickname: string;
  x: number;
  y: number;
  listenGain?: number;
  gain?: GainNode;
  panner?: StereoPannerNode;
  binauralPanner?: PannerNode;
  audioElement?: HTMLAudioElement;
};

type SoundSpec = {
  freq: number;
  duration: number;
  type?: OscillatorType;
  gain?: number;
  sourcePosition?: { x: number; y: number };
  range?: number;
  delay?: number;
};

type OutputMode = 'stereo' | 'mono';
const ONE_SHOT_ATTACK_SECONDS = 0.02;
const ONE_SHOT_START_BUFFER_SECONDS = 0.035;
const PORTAL_ONE_SHOT_START_BUFFER_SECONDS = 0.02;
const PORTAL_ONE_SHOT_GAIN_CAP = 0.72;
const LOOP_SAMPLE_ATTACK_SECONDS = 0.08;
const LOOP_SAMPLE_RELEASE_SECONDS = 0.08;
const LOCATION_AMBIENCE_FADE_SECONDS = 1.25;
const ACTION_SOUND_URLS = {
  uiConfirm: 'sounds/actions/ui-confirm.mp3?v=20260714-elevenlabs-actions',
  uiCancel: 'sounds/actions/ui-cancel.mp3?v=20260714-elevenlabs-actions',
  uiBlip: 'sounds/actions/ui-blip.mp3?v=20260714-elevenlabs-actions',
  tileItemPing: 'sounds/actions/tile-item-ping.mp3?v=20260714-elevenlabs-actions',
  tileUserPing: 'sounds/actions/tile-user-ping.mp3?v=20260714-elevenlabs-actions',
  wheelFlourish: 'sounds/actions/wheel-flourish.mp3?v=20260714-elevenlabs-actions',
} as const;
const DEVICE_BUTTON_SOUND_URLS = {
  hardwareToggle: 'sounds/device-buttons/hardware_toggle.mp3?v=20260714-device-buttons',
  keypadTactile: 'sounds/device-buttons/keypad_tactile.mp3?v=20260714-device-buttons',
  presetButton: 'sounds/device-buttons/preset_button.mp3?v=20260714-device-buttons',
  radioPower: 'sounds/device-buttons/radio_power.mp3?v=20260714-device-buttons',
  radioTunerStep: 'sounds/device-buttons/radio_tuner_step.mp3?v=20260714-device-buttons',
  softPlasticPress: 'sounds/device-buttons/soft_plastic_press.mp3?v=20260714-device-buttons',
} as const;

type StepSignatureProfile = {
  label: string;
  oscillator: OscillatorType;
  frequencies: [number, number];
  delaySeconds: number;
  durationSeconds: number;
  gain: number;
  filterHz: number;
};

export type LocationAmbienceProfile = {
  key: string;
  name: string;
  loopUrl?: string;
  loopGain?: number;
  rootHz: number;
  colorHz: number;
  airHz: number;
  noiseHz: number;
  noiseQ: number;
  gain: number;
  noiseGain: number;
  wave: OscillatorType;
};

type ActiveSpatialSampleRuntime = {
  sourceX: number;
  sourceY: number;
  range: number;
  baseGain: number;
  gainNode: GainNode;
  pannerNode: StereoPannerNode | null;
  binauralPannerNode: PannerNode | null;
  sourceNode: AudioBufferSourceNode;
  startsAt: number;
  distanceReflections: DistanceReflectionRuntime | null;
};

function isPortalTravelSample(url: string): boolean {
  return /\/sounds\/(?:teleport|portal)[^/]*\.(?:ogg|mp3)(?:[?#].*)?$/i.test(url)
    || /(?:^|\/)(?:teleport|portal)[^/]*\.(?:ogg|mp3)(?:[?#].*)?$/i.test(url);
}

type LocationAmbienceRuntime = {
  key: string;
  masterGain: GainNode;
  nodes: Array<AudioScheduledSourceNode | AudioNode>;
};

export class AudioEngine {
  private audioCtx: AudioContext | null = null;
  private masterGainNode: GainNode | null = null;
  private sfxGainNode: GainNode | null = null;
  private readonly sampleCache = new Map<string, AudioBuffer>();
  private readonly sampleLoaders = new Map<string, Promise<AudioBuffer>>();
  private readonly activeSpatialSamples = new Set<ActiveSpatialSampleRuntime>();
  private locationAmbience: LocationAmbienceRuntime | null = null;

  private outboundSource: MediaStreamAudioSourceNode | null = null;
  private outboundInputGain: GainNode | null = null;
  private outboundInputGainValue = 1;
  private outboundDestination: MediaStreamAudioDestinationNode | null = null;
  private outboundEffectRuntime: EffectRuntime | null = null;
  private loopbackEnabled = false;
  private loopbackRuntime: EffectRuntime | null = null;
  private outputMode: OutputMode = 'stereo';
  private masterVolume = 50;
  private voiceLayerEnabled = true;
  private actionSoundPreloadStarted = false;
  private effectIndex = EFFECT_SEQUENCE.findIndex((effect) => effect.id === 'off');
  private readonly effectValues: Record<EffectId, number> = {
    reverb: 50,
    echo: 50,
    flanger: 50,
    high_pass: 50,
    low_pass: 50,
    off: 0,
  };

  async ensureContext(): Promise<void> {
    if (!this.audioCtx) {
      const Ctor =
        window.AudioContext ||
        (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return;
      this.audioCtx = new Ctor();
      this.masterGainNode = this.audioCtx.createGain();
      this.masterGainNode.gain.value = this.masterVolume / 100;
      this.masterGainNode.connect(this.audioCtx.destination);
      this.sfxGainNode = this.audioCtx.createGain();
      this.sfxGainNode.connect(this.masterGainNode);
    }
    if (this.audioCtx.state === 'suspended') {
      await this.audioCtx.resume();
    }
    this.preloadActionSoundsOnce();
  }

  get context(): AudioContext | null {
    return this.audioCtx;
  }

  getOutputDestinationNode(): AudioNode | null {
    return this.masterGainNode ?? this.audioCtx?.destination ?? null;
  }

  preloadSamples(urls: Iterable<string | undefined | null>): void {
    void this.ensureContext().then(() => {
      const uniqueUrls = Array.from(
        new Set(
          Array.from(urls)
            .map((url) => String(url || '').trim())
            .filter((url) => url.length > 0),
        ),
      );
      for (const url of uniqueUrls) {
        void this.getSampleBuffer(url).catch(() => undefined);
      }
    });
  }

  supportsStereoPanner(): boolean {
    return !!this.audioCtx && typeof this.audioCtx.createStereoPanner === 'function';
  }

  supportsBinauralPanner(): boolean {
    return !!this.audioCtx && typeof this.audioCtx.createPanner === 'function';
  }

  supportsSinkId(element: HTMLMediaElement): boolean {
    return (
      typeof (element as HTMLMediaElement & { setSinkId?: (id: string) => Promise<void> }).setSinkId ===
      'function'
    );
  }

  async configureOutboundStream(inputStream: MediaStream): Promise<MediaStream> {
    await this.ensureContext();
    if (!this.audioCtx) {
      return inputStream;
    }

    if (this.outboundSource) {
      this.outboundSource.disconnect();
    }

    this.outboundSource = this.audioCtx.createMediaStreamSource(inputStream);
    if (!this.outboundInputGain) {
      this.outboundInputGain = this.audioCtx.createGain();
    }
    this.outboundInputGain.gain.value = this.outboundInputGainValue;
    if (!this.outboundDestination) {
      this.outboundDestination = this.audioCtx.createMediaStreamDestination();
    }

    this.outboundSource.connect(this.outboundInputGain);
    this.rebuildOutboundEffectGraph();

    return this.outboundDestination.stream;
  }

  cycleOutboundEffect(): { id: EffectId; label: string } {
    this.effectIndex = (this.effectIndex + 1) % EFFECT_SEQUENCE.length;
    this.rebuildOutboundEffectGraph();
    return EFFECT_SEQUENCE[this.effectIndex];
  }

  setOutboundEffect(effectId: EffectId): { id: EffectId; label: string } {
    const nextIndex = EFFECT_SEQUENCE.findIndex((effect) => effect.id === effectId);
    this.effectIndex = nextIndex >= 0 ? nextIndex : this.effectIndex;
    this.rebuildOutboundEffectGraph();
    return EFFECT_SEQUENCE[this.effectIndex];
  }

  getCurrentEffect(): { id: EffectId; label: string; value: number; defaultValue: number } {
    const effect = EFFECT_SEQUENCE[this.effectIndex];
    return {
      id: effect.id,
      label: effect.label,
      value: this.effectValues[effect.id],
      defaultValue: effect.defaultValue,
    };
  }

  adjustCurrentEffectLevel(step: number): { id: EffectId; label: string; value: number; defaultValue: number } | null {
    const effect = EFFECT_SEQUENCE[this.effectIndex];
    if (effect.id === 'off') {
      return null;
    }

    const next = this.clampLevel(this.effectValues[effect.id] + step);
    this.effectValues[effect.id] = next;
    this.rebuildOutboundEffectGraph();

    return {
      id: effect.id,
      label: effect.label,
      value: next,
      defaultValue: effect.defaultValue,
    };
  }

  setEffectLevels(levels: Partial<Record<EffectId, number>>): void {
    for (const effect of EFFECT_SEQUENCE) {
      if (effect.id === 'off') continue;
      const value = levels[effect.id];
      if (typeof value !== 'number') continue;
      this.effectValues[effect.id] = this.clampLevel(value);
    }
    this.rebuildOutboundEffectGraph();
  }

  getEffectLevels(): Record<EffectId, number> {
    return { ...this.effectValues };
  }

  setOutputMode(mode: OutputMode): void {
    this.outputMode = mode;
  }

  setMasterVolume(value: number): number {
    const next = Math.max(0, Math.min(100, Number.isFinite(value) ? Math.round(value) : 50));
    this.masterVolume = next;
    if (this.masterGainNode && this.audioCtx) {
      this.masterGainNode.gain.setValueAtTime(next / 100, this.audioCtx.currentTime);
    }
    return this.masterVolume;
  }

  adjustMasterVolume(step: number): number {
    return this.setMasterVolume(this.masterVolume + step);
  }

  getMasterVolume(): number {
    return this.masterVolume;
  }

  toggleOutputMode(): OutputMode {
    this.outputMode = this.outputMode === 'stereo' ? 'mono' : 'stereo';
    return this.outputMode;
  }

  getOutputMode(): OutputMode {
    return this.outputMode;
  }

  setVoiceLayerEnabled(enabled: boolean): void {
    this.voiceLayerEnabled = enabled;
  }

  isVoiceLayerEnabled(): boolean {
    return this.voiceLayerEnabled;
  }

  async setLocationAmbience(profile: LocationAmbienceProfile | null, enabled: boolean): Promise<void> {
    if (!enabled || !profile) {
      this.stopLocationAmbience();
      return;
    }
    await this.ensureContext();
    const { audioCtx, sfxGainNode } = this;
    if (!audioCtx || !sfxGainNode) return;
    if (this.locationAmbience?.key === profile.key) return;

    this.stopLocationAmbience();

    if (profile.loopUrl) {
      const masterGain = audioCtx.createGain();
      const targetGain = Math.max(0.0001, profile.loopGain ?? profile.gain);
      masterGain.gain.setValueAtTime(0.0001, audioCtx.currentTime);
      masterGain.gain.exponentialRampToValueAtTime(
        targetGain,
        audioCtx.currentTime + LOCATION_AMBIENCE_FADE_SECONDS,
      );
      masterGain.connect(sfxGainNode);

      try {
        const buffer = await this.getSampleBuffer(profile.loopUrl);
        if (this.locationAmbience?.key === profile.key) {
          masterGain.disconnect();
          return;
        }
        const source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.loop = true;
        source.connect(masterGain);
        source.start();
        this.locationAmbience = {
          key: profile.key,
          masterGain,
          nodes: [source],
        };
        return;
      } catch {
        try {
          masterGain.disconnect();
        } catch {
          // Ignore failed asset ambience graph cleanup.
        }
      }
    }

    const masterGain = audioCtx.createGain();
    masterGain.gain.setValueAtTime(0.0001, audioCtx.currentTime);
    masterGain.gain.exponentialRampToValueAtTime(
      Math.max(0.0001, profile.gain),
      audioCtx.currentTime + LOCATION_AMBIENCE_FADE_SECONDS,
    );
    masterGain.connect(sfxGainNode);

    const root = audioCtx.createOscillator();
    root.type = profile.wave;
    root.frequency.setValueAtTime(profile.rootHz, audioCtx.currentTime);
    const rootGain = audioCtx.createGain();
    rootGain.gain.setValueAtTime(profile.gain * 0.34, audioCtx.currentTime);
    root.connect(rootGain).connect(masterGain);

    const color = audioCtx.createOscillator();
    color.type = 'sine';
    color.frequency.setValueAtTime(profile.colorHz, audioCtx.currentTime);
    const colorGain = audioCtx.createGain();
    colorGain.gain.setValueAtTime(profile.gain * 0.2, audioCtx.currentTime);
    color.connect(colorGain).connect(masterGain);

    const air = audioCtx.createOscillator();
    air.type = 'triangle';
    air.frequency.setValueAtTime(profile.airHz, audioCtx.currentTime);
    const airGain = audioCtx.createGain();
    airGain.gain.setValueAtTime(profile.gain * 0.08, audioCtx.currentTime);
    air.connect(airGain).connect(masterGain);

    const noise = audioCtx.createBufferSource();
    noise.buffer = this.createNoiseBuffer(2);
    noise.loop = true;
    const filter = audioCtx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(profile.noiseHz, audioCtx.currentTime);
    filter.Q.setValueAtTime(profile.noiseQ, audioCtx.currentTime);
    const noiseGain = audioCtx.createGain();
    noiseGain.gain.setValueAtTime(profile.noiseGain, audioCtx.currentTime);
    noise.connect(filter).connect(noiseGain).connect(masterGain);

    root.start();
    color.start();
    air.start();
    noise.start();

    this.locationAmbience = {
      key: profile.key,
      masterGain,
      nodes: [root, color, air, noise, rootGain, colorGain, airGain, filter, noiseGain],
    };
  }

  stopLocationAmbience(): void {
    if (!this.audioCtx || !this.locationAmbience) {
      this.locationAmbience = null;
      return;
    }
    const runtime = this.locationAmbience;
    this.locationAmbience = null;
    runtime.masterGain.gain.cancelScheduledValues(this.audioCtx.currentTime);
    runtime.masterGain.gain.setTargetAtTime(0.0001, this.audioCtx.currentTime, LOCATION_AMBIENCE_FADE_SECONDS / 3);
    window.setTimeout(() => {
      for (const node of runtime.nodes) {
        if ('stop' in node && typeof node.stop === 'function') {
          try {
            node.stop();
          } catch {
            // Ignore already-stopped ambience sources.
          }
        }
        try {
          node.disconnect();
        } catch {
          // Ignore stale graph disconnects.
        }
      }
      try {
        runtime.masterGain.disconnect();
      } catch {
        // Ignore stale graph disconnects.
      }
    }, Math.ceil(LOCATION_AMBIENCE_FADE_SECONDS * 1000));
  }

  setOutboundInputGain(value: number): number {
    const next = Math.max(0.01, Number.isFinite(value) ? value : 1);
    this.outboundInputGainValue = next;
    if (this.outboundInputGain && this.audioCtx) {
      this.outboundInputGain.gain.setValueAtTime(next, this.audioCtx.currentTime);
    }
    return next;
  }

  getOutboundInputGain(): number {
    return this.outboundInputGainValue;
  }

  toggleLoopback(): boolean {
    this.loopbackEnabled = !this.loopbackEnabled;
    this.rebuildOutboundEffectGraph();
    return this.loopbackEnabled;
  }

  /** Returns current loopback monitor state. */
  isLoopbackEnabled(): boolean {
    return this.loopbackEnabled;
  }

  /** Sets loopback monitor state directly. */
  setLoopbackEnabled(enabled: boolean): boolean {
    this.loopbackEnabled = enabled;
    this.rebuildOutboundEffectGraph();
    return this.loopbackEnabled;
  }

  async attachRemoteStream(
    peer: SpatialPeerRuntime,
    stream: MediaStream,
    outputDeviceId: string,
  ): Promise<void> {
    await this.ensureContext();
    if (!this.audioCtx) return;
    this.cleanupPeerAudio(peer);

    const audioElement = new Audio();
    audioElement.srcObject = stream;
    audioElement.muted = true;

    if (outputDeviceId && this.supportsSinkId(audioElement)) {
      const sinkTarget = audioElement as HTMLMediaElement & { setSinkId?: (id: string) => Promise<void> };
      await sinkTarget.setSinkId?.(outputDeviceId);
    }

    await audioElement.play().catch(() => undefined);
    document.body.appendChild(audioElement);

    const sourceNode = this.audioCtx.createMediaStreamSource(stream);
    const gainNode = this.audioCtx.createGain();
    sourceNode.connect(gainNode);

    let pannerNode: StereoPannerNode | undefined;
    let binauralPannerNode: PannerNode | undefined;
    if (this.supportsBinauralPanner()) {
      binauralPannerNode = this.createBinauralPannerNode(HEARING_RADIUS);
      if (this.voiceLayerEnabled) {
        gainNode.connect(binauralPannerNode).connect(this.masterGainNode ?? this.audioCtx.destination);
      }
    } else if (this.supportsStereoPanner()) {
      pannerNode = this.audioCtx.createStereoPanner();
      if (this.voiceLayerEnabled) {
        gainNode.connect(pannerNode).connect(this.masterGainNode ?? this.audioCtx.destination);
      }
    } else {
      if (this.voiceLayerEnabled) {
        gainNode.connect(this.masterGainNode ?? this.audioCtx.destination);
      }
    }

    peer.audioElement = audioElement;
    peer.gain = gainNode;
    peer.panner = pannerNode;
    peer.binauralPanner = binauralPannerNode;
  }

  updateSpatialAudio(peers: Iterable<SpatialPeerRuntime>, playerPosition: { x: number; y: number }): void {
    if (!this.audioCtx) return;

    for (const peer of peers) {
      if (!peer.gain) continue;
      const mix = resolveSpatialMix({
        dx: peer.x - playerPosition.x,
        dy: peer.y - playerPosition.y,
        range: HEARING_RADIUS,
        nearFieldDistance: 1.5,
        nearFieldGain: 1,
      });
      const listenGain = Number.isFinite(peer.listenGain) ? Math.max(0, peer.listenGain as number) : 1;
      const scaledMix = mix ? { ...mix, gain: mix.gain * listenGain } : null;
      applySpatialMixToNodes({
        audioCtx: this.audioCtx,
        gainNode: peer.gain,
        pannerNode: peer.panner ?? null,
        mix: scaledMix,
        outputMode: this.outputMode,
        transition: 'target',
      });
      if (peer.binauralPanner) {
        const dx = this.outputMode === 'mono' ? 0 : peer.x - playerPosition.x;
        const dy = this.outputMode === 'mono' ? 0 : peer.y - playerPosition.y;
        this.setBinauralPannerPosition(peer.binauralPanner, dx, dy);
      }
    }
  }

  /** Updates active one-shot spatial sample gain/pan against current listener position. */
  updateSpatialSamples(playerPosition: { x: number; y: number }): void {
    if (!this.audioCtx) return;
    for (const sample of Array.from(this.activeSpatialSamples)) {
      this.applySpatialSampleRuntime(sample, playerPosition);
    }
  }

  sfxLocate(peer: { x: number; y: number }, range = HEARING_RADIUS): void {
    const safeRange = Math.max(1, range);
    const distanceRatio = Math.max(0, Math.min(1, Math.hypot(peer.x, peer.y) / safeRange));
    const freq = 1040 - distanceRatio * 360;
    this.playSound({ freq, duration: 0.2, type: 'sine', gain: 0.5, sourcePosition: peer, range: safeRange });
  }

  sfxUiConfirm(): void {
    this.playSampleOrFallback(ACTION_SOUND_URLS.uiConfirm, 0.78, { freq: 880, duration: 0.1, gain: 0.5 });
  }

  sfxUiCancel(): void {
    this.playSampleOrFallback(ACTION_SOUND_URLS.uiCancel, 0.72, {
      freq: 440,
      duration: 0.1,
      type: 'sawtooth',
      gain: 0.3,
    });
  }

  sfxUiBlip(): void {
    this.playSampleOrFallback(ACTION_SOUND_URLS.uiBlip, 0.58, {
      freq: 660,
      duration: 0.05,
      type: 'triangle',
      gain: 0.35,
    });
  }

  sfxEffectLevel(isDefault: boolean): void {
    this.playSound({ freq: isDefault ? 659.25 : 440, duration: 0.1, type: 'sine', gain: 0.35 });
  }

  sfxTileItemPing(): void {
    this.playSampleOrFallback(ACTION_SOUND_URLS.tileItemPing, 0.68, {
      freq: 1320,
      duration: 0.12,
      type: 'sine',
      gain: 0.45,
    });
  }

  sfxItemBeacon(sourcePosition: { x: number; y: number }, range: number): void {
    const safeRange = Math.max(1, range);
    const distanceRatio = Math.max(0, Math.min(1, Math.hypot(sourcePosition.x, sourcePosition.y) / safeRange));
    const playbackRate = 1.2 - distanceRatio * 0.45;
    const gain = 0.56 + (1 - distanceRatio) * 0.14;
    void this.playSpatialSample(
      ACTION_SOUND_URLS.tileItemPing,
      sourcePosition,
      { x: 0, y: 0 },
      gain,
      safeRange,
      playbackRate,
    ).then((played) => {
      if (played) return;
      this.playSound({
        freq: 1260 - distanceRatio * 420,
        duration: 0.14,
        type: 'sine',
        gain: 0.45,
        sourcePosition,
        range: safeRange,
      });
    });
  }

  sfxTileUserPing(): void {
    this.playSampleOrFallback(ACTION_SOUND_URLS.tileUserPing, 0.68, {
      freq: 880,
      duration: 0.12,
      type: 'sine',
      gain: 0.45,
    });
  }

  sfxDeviceHardwareToggle(): void {
    this.playSampleOrFallback(DEVICE_BUTTON_SOUND_URLS.hardwareToggle, 0.74, {
      freq: 360,
      duration: 0.08,
      type: 'square',
      gain: 0.28,
    });
  }

  sfxDeviceKeypad(): void {
    this.playSampleOrFallback(DEVICE_BUTTON_SOUND_URLS.keypadTactile, 0.64, {
      freq: 760,
      duration: 0.06,
      type: 'triangle',
      gain: 0.25,
    });
  }

  sfxDevicePresetButton(): void {
    this.playSampleOrFallback(DEVICE_BUTTON_SOUND_URLS.presetButton, 0.68, {
      freq: 840,
      duration: 0.07,
      type: 'sine',
      gain: 0.28,
    });
  }

  sfxRadioPower(): void {
    this.playSampleOrFallback(DEVICE_BUTTON_SOUND_URLS.radioPower, 0.76, {
      freq: 260,
      duration: 0.1,
      type: 'square',
      gain: 0.3,
    });
  }

  sfxRadioTunerStep(): void {
    this.playSampleOrFallback(DEVICE_BUTTON_SOUND_URLS.radioTunerStep, 0.66, {
      freq: 680,
      duration: 0.07,
      type: 'sawtooth',
      gain: 0.24,
    });
  }

  sfxSoftPlasticPress(): void {
    this.playSampleOrFallback(DEVICE_BUTTON_SOUND_URLS.softPlasticPress, 0.62, {
      freq: 520,
      duration: 0.06,
      type: 'triangle',
      gain: 0.22,
    });
  }

  async playSpatialSample(
    url: string,
    sourcePosition: { x: number; y: number },
    playerPosition: { x: number; y: number },
    gain = 1,
    range = HEARING_RADIUS,
    playbackRate = 1,
    useDistanceReflections = false,
  ): Promise<boolean> {
    await this.ensureContext();
    const { audioCtx, sfxGainNode } = this;
    if (!audioCtx || !sfxGainNode) return false;

    try {
      const buffer = await this.getSampleBuffer(url);
      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      const safePlaybackRate = this.normalizePlaybackRate(playbackRate);
      source.playbackRate.setValueAtTime(safePlaybackRate, audioCtx.currentTime);
      const isPortalSample = isPortalTravelSample(url);
      const startAt = audioCtx.currentTime + (isPortalSample ? PORTAL_ONE_SHOT_START_BUFFER_SECONDS : ONE_SHOT_START_BUFFER_SECONDS);
      const effectiveGain = isPortalSample ? Math.min(gain, PORTAL_ONE_SHOT_GAIN_CAP) : gain;
      const gainNode = audioCtx.createGain();
      gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
      source.connect(gainNode);
      let pannerNode: StereoPannerNode | null = null;
      let binauralPannerNode: PannerNode | null = null;
      if (this.supportsBinauralPanner() && this.outputMode === 'stereo') {
        binauralPannerNode = this.createBinauralPannerNode(Math.max(1, range));
        gainNode.connect(binauralPannerNode).connect(sfxGainNode);
      } else if (this.supportsStereoPanner() && this.outputMode === 'stereo') {
        pannerNode = audioCtx.createStereoPanner();
        gainNode.connect(pannerNode).connect(sfxGainNode);
      } else {
        gainNode.connect(sfxGainNode);
      }
      const distanceReflections = useDistanceReflections
        ? connectDistanceReflections(
            audioCtx,
            source,
            sfxGainNode,
            this.supportsStereoPanner() && this.outputMode === 'stereo',
          )
        : null;
      const runtime: ActiveSpatialSampleRuntime = {
        sourceX: sourcePosition.x,
        sourceY: sourcePosition.y,
        range: Math.max(1, range),
        baseGain: effectiveGain,
        gainNode,
        pannerNode,
        binauralPannerNode,
        sourceNode: source,
        startsAt: startAt,
        distanceReflections,
      };
      this.activeSpatialSamples.add(runtime);
      this.applySpatialSampleRuntime(runtime, playerPosition, true, startAt);
      source.onended = () => {
        this.activeSpatialSamples.delete(runtime);
        try {
          source.disconnect();
        } catch {
          // Ignore stale graph disconnects.
        }
        gainNode.disconnect();
        pannerNode?.disconnect();
        binauralPannerNode?.disconnect();
        disconnectDistanceReflections(distanceReflections);
      };
      source.start(startAt);
      return true;
    } catch {
      // Ignore sample decode/load errors.
      return false;
    }
  }

  playStepSignature(options: {
    identity: string;
    nickname: string;
    sourcePosition?: { x: number; y: number };
    playerPosition?: { x: number; y: number };
    range?: number;
  }): void {
    void this.ensureContext().then(() => {
      const { audioCtx, sfxGainNode } = this;
      if (!audioCtx || !sfxGainNode) return;

      const profile = this.stepSignatureProfile(options.identity, options.nickname);
      const now = audioCtx.currentTime;
      const range = Math.max(1, options.range ?? HEARING_RADIUS);
      const outputGain = audioCtx.createGain();
      outputGain.gain.setValueAtTime(profile.gain, now);
      outputGain.gain.setTargetAtTime(0.0001, now + profile.delaySeconds + profile.durationSeconds, 0.035);

      let pannerNode: StereoPannerNode | null = null;
      let binauralPannerNode: PannerNode | null = null;
      const sourcePosition = options.sourcePosition;
      const playerPosition = options.playerPosition;
      if (sourcePosition && playerPosition) {
        const mix = resolveSpatialMix({
          dx: sourcePosition.x - playerPosition.x,
          dy: sourcePosition.y - playerPosition.y,
          range,
          baseGain: profile.gain,
          nearFieldDistance: 1.2,
          nearFieldGain: profile.gain * 0.75,
          nearFieldCenterPan: true,
        });
        if (!mix || mix.gain <= 0) return;
        outputGain.gain.setValueAtTime(mix.gain, now);
        if (this.supportsBinauralPanner() && this.outputMode === 'stereo') {
          binauralPannerNode = this.createBinauralPannerNode(range);
          this.setBinauralPannerPosition(
            binauralPannerNode,
            sourcePosition.x - playerPosition.x,
            sourcePosition.y - playerPosition.y,
          );
          outputGain.connect(binauralPannerNode).connect(sfxGainNode);
        } else if (this.supportsStereoPanner() && this.outputMode === 'stereo') {
          pannerNode = audioCtx.createStereoPanner();
          pannerNode.pan.setValueAtTime(Math.max(-1, Math.min(1, mix.pan)), now);
          outputGain.connect(pannerNode).connect(sfxGainNode);
        } else {
          outputGain.connect(sfxGainNode);
        }
      } else {
        outputGain.connect(sfxGainNode);
      }

      const nodes: Array<AudioNode> = [outputGain];
      for (const [index, frequency] of profile.frequencies.entries()) {
        const startAt = now + index * profile.delaySeconds;
        const oscillator = audioCtx.createOscillator();
        oscillator.type = profile.oscillator;
        oscillator.frequency.setValueAtTime(frequency, startAt);
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.setValueAtTime(profile.filterHz, startAt);
        filter.Q.setValueAtTime(2.2, startAt);
        const envelope = audioCtx.createGain();
        envelope.gain.setValueAtTime(0.0001, startAt);
        envelope.gain.linearRampToValueAtTime(1, startAt + 0.008);
        envelope.gain.exponentialRampToValueAtTime(0.0001, startAt + profile.durationSeconds);
        oscillator.connect(filter).connect(envelope).connect(outputGain);
        oscillator.start(startAt);
        oscillator.stop(startAt + profile.durationSeconds + 0.02);
        nodes.push(oscillator, filter, envelope);
      }

      window.setTimeout(
        () => {
          for (const node of nodes) {
            try {
              node.disconnect();
            } catch {
              // Ignore already-stopped synthetic step nodes.
            }
          }
          pannerNode?.disconnect();
          binauralPannerNode?.disconnect();
        },
        Math.ceil((profile.delaySeconds + profile.durationSeconds + 0.08) * 1000),
      );
    });
  }

  /** Plays a short, descending, identity-stable spatial beacon for one user. */
  playUserBeacon(options: {
    identity: string;
    nickname: string;
    sourcePosition: { x: number; y: number };
    playerPosition: { x: number; y: number };
    range?: number;
  }): void {
    void this.ensureContext().then(() => {
      const { audioCtx, sfxGainNode } = this;
      if (!audioCtx || !sfxGainNode) return;

      const range = Math.max(1, options.range ?? HEARING_RADIUS);
      const mix = resolveSpatialMix({
        dx: options.sourcePosition.x - options.playerPosition.x,
        dy: options.sourcePosition.y - options.playerPosition.y,
        range,
        baseGain: 0.035,
        nearFieldDistance: 1.1,
        nearFieldGain: 0.026,
        nearFieldCenterPan: true,
      });
      if (!mix || mix.gain <= 0) return;

      const identityHash = this.hashText(`${options.identity} ${options.nickname}`.trim().toLowerCase());
      const baseFrequency = 720 + (identityHash % 13) * 38;
      const intervalRatio = 0.72 + ((identityHash >>> 8) % 5) * 0.025;
      const oscillatorTypes: OscillatorType[] = ['sine', 'triangle', 'sine', 'triangle'];
      const oscillatorType = oscillatorTypes[(identityHash >>> 16) % oscillatorTypes.length] ?? 'sine';
      const delaySeconds = 0.085 + ((identityHash >>> 20) % 4) * 0.012;
      const durationSeconds = 0.065;
      const now = audioCtx.currentTime;
      const outputGain = audioCtx.createGain();
      outputGain.gain.setValueAtTime(mix.gain, now);
      outputGain.gain.setTargetAtTime(0.0001, now + delaySeconds * 2 + durationSeconds, 0.03);

      let pannerNode: StereoPannerNode | null = null;
      let binauralPannerNode: PannerNode | null = null;
      if (this.supportsBinauralPanner() && this.outputMode === 'stereo') {
        binauralPannerNode = this.createBinauralPannerNode(range);
        this.setBinauralPannerPosition(
          binauralPannerNode,
          options.sourcePosition.x - options.playerPosition.x,
          options.sourcePosition.y - options.playerPosition.y,
        );
        outputGain.connect(binauralPannerNode).connect(sfxGainNode);
      } else if (this.supportsStereoPanner() && this.outputMode === 'stereo') {
        pannerNode = audioCtx.createStereoPanner();
        pannerNode.pan.setValueAtTime(Math.max(-1, Math.min(1, mix.pan)), now);
        outputGain.connect(pannerNode).connect(sfxGainNode);
      } else {
        outputGain.connect(sfxGainNode);
      }

      const nodes: AudioNode[] = [outputGain];
      for (let index = 0; index < 3; index += 1) {
        const startAt = now + index * delaySeconds;
        const oscillator = audioCtx.createOscillator();
        oscillator.type = oscillatorType;
        oscillator.frequency.setValueAtTime(baseFrequency * Math.pow(intervalRatio, index), startAt);
        const envelope = audioCtx.createGain();
        envelope.gain.setValueAtTime(0.0001, startAt);
        envelope.gain.linearRampToValueAtTime(1, startAt + 0.008);
        envelope.gain.exponentialRampToValueAtTime(0.0001, startAt + durationSeconds);
        oscillator.connect(envelope).connect(outputGain);
        oscillator.start(startAt);
        oscillator.stop(startAt + durationSeconds + 0.01);
        nodes.push(oscillator, envelope);
      }

      window.setTimeout(() => {
        for (const node of nodes) {
          try { node.disconnect(); } catch { /* Ignore already-cleaned beacon nodes. */ }
        }
        pannerNode?.disconnect();
        binauralPannerNode?.disconnect();
      }, Math.ceil((delaySeconds * 2 + durationSeconds + 0.08) * 1000));
    });
  }

  /** Plays one spatial sample and resolves when playback finishes. */
  async playSpatialSampleAndWait(
    url: string,
    sourcePosition: { x: number; y: number },
    playerPosition: { x: number; y: number },
    gain = 1,
    range = HEARING_RADIUS,
  ): Promise<boolean> {
    await this.ensureContext();
    const { audioCtx, sfxGainNode } = this;
    if (!audioCtx || !sfxGainNode) return false;

    try {
      const buffer = await this.getSampleBuffer(url);
      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      const isPortalSample = isPortalTravelSample(url);
      const startAt = audioCtx.currentTime + (isPortalSample ? PORTAL_ONE_SHOT_START_BUFFER_SECONDS : ONE_SHOT_START_BUFFER_SECONDS);
      const effectiveGain = isPortalSample ? Math.min(gain, PORTAL_ONE_SHOT_GAIN_CAP) : gain;
      const gainNode = audioCtx.createGain();
      gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
      source.connect(gainNode);
      let pannerNode: StereoPannerNode | null = null;
      let binauralPannerNode: PannerNode | null = null;
      if (this.supportsBinauralPanner() && this.outputMode === 'stereo') {
        binauralPannerNode = this.createBinauralPannerNode(Math.max(1, range));
        gainNode.connect(binauralPannerNode).connect(sfxGainNode);
      } else if (this.supportsStereoPanner() && this.outputMode === 'stereo') {
        pannerNode = audioCtx.createStereoPanner();
        gainNode.connect(pannerNode).connect(sfxGainNode);
      } else {
        gainNode.connect(sfxGainNode);
      }
      const runtime: ActiveSpatialSampleRuntime = {
        sourceX: sourcePosition.x,
        sourceY: sourcePosition.y,
        range: Math.max(1, range),
        baseGain: effectiveGain,
        gainNode,
        pannerNode,
        binauralPannerNode,
        sourceNode: source,
        startsAt: startAt,
        distanceReflections: null,
      };
      this.activeSpatialSamples.add(runtime);
      this.applySpatialSampleRuntime(runtime, playerPosition, true, startAt);
      await new Promise<void>((resolve) => {
        source.onended = () => {
          this.activeSpatialSamples.delete(runtime);
          try {
            source.disconnect();
          } catch {
            // Ignore stale graph disconnects.
          }
          gainNode.disconnect();
          pannerNode?.disconnect();
          binauralPannerNode?.disconnect();
          resolve();
        };
        source.start(startAt);
      });
      return true;
    } catch {
      // Ignore sample decode/load errors.
      return false;
    }
  }

  playSpatialWheelFlourish(
    sourcePosition: { x: number; y: number },
    playerPosition: { x: number; y: number },
    range = HEARING_RADIUS,
  ): void {
    void this.playSpatialSampleAndWait(
      ACTION_SOUND_URLS.wheelFlourish,
      sourcePosition,
      playerPosition,
      0.78,
      range,
    ).then((played) => {
      if (!played) {
        this.playSyntheticSpatialWheelFlourish(sourcePosition, playerPosition, range);
      }
    });
  }

  private playSyntheticSpatialWheelFlourish(
    sourcePosition: { x: number; y: number },
    playerPosition: { x: number; y: number },
    range = HEARING_RADIUS,
  ): void {
    void this.ensureContext().then(() => {
      const { audioCtx, sfxGainNode } = this;
      if (!audioCtx || !sfxGainNode) return;
      const mix = resolveSpatialMix({
        dx: sourcePosition.x - playerPosition.x,
        dy: sourcePosition.y - playerPosition.y,
        range: Math.max(1, range),
        baseGain: 0.62,
        nearFieldDistance: 1.4,
        nearFieldGain: 0.5,
        nearFieldCenterPan: true,
      });
      if (!mix || mix.gain <= 0) return;

      const now = audioCtx.currentTime;
      const duration = 2.9;
      const spatialGain = audioCtx.createGain();
      spatialGain.gain.setValueAtTime(mix.gain, now);
      spatialGain.gain.setTargetAtTime(0.0001, now + duration - 0.34, 0.16);

      let pannerNode: StereoPannerNode | null = null;
      let binauralPannerNode: PannerNode | null = null;
      if (this.supportsBinauralPanner() && this.outputMode === 'stereo') {
        binauralPannerNode = this.createBinauralPannerNode(Math.max(1, range));
        this.setBinauralPannerPosition(
          binauralPannerNode,
          sourcePosition.x - playerPosition.x,
          sourcePosition.y - playerPosition.y,
        );
        spatialGain.connect(binauralPannerNode).connect(sfxGainNode);
      } else if (this.supportsStereoPanner() && this.outputMode === 'stereo') {
        pannerNode = audioCtx.createStereoPanner();
        pannerNode.pan.setValueAtTime(Math.max(-1, Math.min(1, mix.pan)), now);
        spatialGain.connect(pannerNode).connect(sfxGainNode);
      } else {
        spatialGain.connect(sfxGainNode);
      }

      const motor = audioCtx.createOscillator();
      motor.type = 'sawtooth';
      motor.frequency.setValueAtTime(96, now);
      motor.frequency.exponentialRampToValueAtTime(48, now + duration);
      const motorFilter = audioCtx.createBiquadFilter();
      motorFilter.type = 'lowpass';
      motorFilter.frequency.setValueAtTime(920, now);
      motorFilter.frequency.exponentialRampToValueAtTime(260, now + duration);
      motorFilter.Q.setValueAtTime(1.1, now);
      const motorGain = audioCtx.createGain();
      motorGain.gain.setValueAtTime(0.001, now);
      motorGain.gain.linearRampToValueAtTime(0.09, now + 0.08);
      motorGain.gain.setTargetAtTime(0.0001, now + duration - 0.42, 0.18);
      motor.connect(motorFilter).connect(motorGain).connect(spatialGain);

      const shimmer = audioCtx.createOscillator();
      shimmer.type = 'triangle';
      shimmer.frequency.setValueAtTime(880, now);
      shimmer.frequency.exponentialRampToValueAtTime(1320, now + 0.7);
      const shimmerGain = audioCtx.createGain();
      shimmerGain.gain.setValueAtTime(0.0001, now);
      shimmerGain.gain.linearRampToValueAtTime(0.055, now + 0.04);
      shimmerGain.gain.setTargetAtTime(0.0001, now + 0.74, 0.12);
      shimmer.connect(shimmerGain).connect(spatialGain);

      const tickNodes: Array<OscillatorNode | GainNode | BiquadFilterNode> = [];
      let tickAt = now + 0.05;
      let interval = 0.055;
      for (let index = 0; index < 24 && tickAt < now + duration - 0.2; index += 1) {
        const tick = audioCtx.createOscillator();
        tick.type = index % 3 === 0 ? 'square' : 'triangle';
        tick.frequency.setValueAtTime(1420 - Math.min(520, index * 18), tickAt);
        const tickFilter = audioCtx.createBiquadFilter();
        tickFilter.type = 'bandpass';
        tickFilter.frequency.setValueAtTime(1500 - Math.min(620, index * 20), tickAt);
        tickFilter.Q.setValueAtTime(3.2, tickAt);
        const tickGain = audioCtx.createGain();
        const tickLevel = Math.max(0.018, 0.07 - index * 0.0016);
        tickGain.gain.setValueAtTime(0.0001, tickAt);
        tickGain.gain.linearRampToValueAtTime(tickLevel, tickAt + 0.006);
        tickGain.gain.exponentialRampToValueAtTime(0.0001, tickAt + 0.045);
        tick.connect(tickFilter).connect(tickGain).connect(spatialGain);
        tick.start(tickAt);
        tick.stop(tickAt + 0.055);
        tickNodes.push(tick, tickFilter, tickGain);
        tickAt += interval;
        interval *= 1.105;
      }

      const settle = audioCtx.createOscillator();
      settle.type = 'sine';
      settle.frequency.setValueAtTime(659.25, now + duration - 0.42);
      settle.frequency.exponentialRampToValueAtTime(329.63, now + duration - 0.05);
      const settleGain = audioCtx.createGain();
      settleGain.gain.setValueAtTime(0.0001, now + duration - 0.45);
      settleGain.gain.linearRampToValueAtTime(0.08, now + duration - 0.34);
      settleGain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
      settle.connect(settleGain).connect(spatialGain);

      motor.start(now);
      shimmer.start(now);
      settle.start(now + duration - 0.45);
      motor.stop(now + duration);
      shimmer.stop(now + 0.9);
      settle.stop(now + duration);

      window.setTimeout(() => {
        motor.disconnect();
        motorFilter.disconnect();
        motorGain.disconnect();
        shimmer.disconnect();
        shimmerGain.disconnect();
        settle.disconnect();
        settleGain.disconnect();
        spatialGain.disconnect();
        pannerNode?.disconnect();
        binauralPannerNode?.disconnect();
        for (const node of tickNodes) {
          try {
            node.disconnect();
          } catch {
            // Ignore already-cleaned tick nodes.
          }
        }
      }, Math.ceil((duration + 0.2) * 1000));
    });
  }

  private stepSignatureProfile(identity: string, nickname: string): StepSignatureProfile {
    const combined = `${identity} ${nickname}`.trim().toLowerCase();
    if (combined.includes('clawdia')) {
      return {
        label: 'moonlit heels',
        oscillator: 'sine',
        frequencies: [1320, 1760],
        delaySeconds: 0.038,
        durationSeconds: 0.072,
        gain: 0.042,
        filterHz: 1680,
      };
    }

    const profiles: StepSignatureProfile[] = [
      { label: 'soft boots', oscillator: 'triangle', frequencies: [164, 220], delaySeconds: 0.032, durationSeconds: 0.08, gain: 0.032, filterHz: 420 },
      { label: 'rubber crocs', oscillator: 'sine', frequencies: [310, 245], delaySeconds: 0.045, durationSeconds: 0.075, gain: 0.036, filterHz: 680 },
      { label: 'bright taps', oscillator: 'square', frequencies: [980, 740], delaySeconds: 0.03, durationSeconds: 0.052, gain: 0.025, filterHz: 1200 },
      { label: 'hill gravel', oscillator: 'sawtooth', frequencies: [190, 145], delaySeconds: 0.036, durationSeconds: 0.065, gain: 0.026, filterHz: 520 },
      { label: 'quiet slippers', oscillator: 'triangle', frequencies: [260, 330], delaySeconds: 0.04, durationSeconds: 0.07, gain: 0.022, filterHz: 760 },
    ];
    return profiles[this.hashText(combined || 'anonymous') % profiles.length];
  }

  private hashText(value: string): number {
    let hash = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  playSpatialBillboardAnnouncement(
    text: string,
    sourcePosition: { x: number; y: number },
    playerPosition: { x: number; y: number },
    range = HEARING_RADIUS,
  ): void {
    void this.ensureContext().then(() => {
      const { audioCtx, sfxGainNode } = this;
      if (!audioCtx || !sfxGainNode) return;
      const mix = resolveSpatialMix({
        dx: sourcePosition.x - playerPosition.x,
        dy: sourcePosition.y - playerPosition.y,
        range: Math.max(1, range),
        baseGain: 0.42,
        nearFieldDistance: 1.25,
        nearFieldGain: 0.34,
        nearFieldCenterPan: true,
      });
      if (!mix || mix.gain <= 0) return;

      const distanceRatio = Math.max(0, Math.min(1, mix.distance / Math.max(1, range)));
      const wordCount = Math.max(3, text.trim().split(/\s+/).filter(Boolean).length);
      const duration = Math.max(1.4, Math.min(5.2, wordCount * 0.22));
      const now = audioCtx.currentTime;
      const carrier = audioCtx.createOscillator();
      carrier.type = distanceRatio > 0.68 ? 'sawtooth' : 'square';
      carrier.frequency.setValueAtTime(180 + Math.max(0, 1 - distanceRatio) * 55, now);

      const lfo = audioCtx.createOscillator();
      lfo.type = 'sine';
      lfo.frequency.setValueAtTime(3.2 + distanceRatio * 2.8, now);
      const lfoGain = audioCtx.createGain();
      lfoGain.gain.setValueAtTime(8 + distanceRatio * 28, now);
      lfo.connect(lfoGain).connect(carrier.detune);

      const noise = audioCtx.createBufferSource();
      noise.buffer = this.createNoiseBuffer(duration);
      const noiseFilter = audioCtx.createBiquadFilter();
      noiseFilter.type = 'bandpass';
      noiseFilter.frequency.setValueAtTime(720 + distanceRatio * 320, now);
      noiseFilter.Q.setValueAtTime(0.7 + distanceRatio * 1.8, now);

      const toneGain = audioCtx.createGain();
      const noiseGain = audioCtx.createGain();
      const phraseGain = audioCtx.createGain();
      toneGain.gain.setValueAtTime(0.0001, now);
      noiseGain.gain.setValueAtTime(0.0001, now);
      phraseGain.gain.setValueAtTime(0, now);
      phraseGain.gain.linearRampToValueAtTime(mix.gain, now + 0.08);
      phraseGain.gain.setTargetAtTime(0.0001, now + duration - 0.22, 0.08);

      const syllableCount = Math.max(5, Math.min(28, Math.round(wordCount * 1.55)));
      for (let index = 0; index < syllableCount; index += 1) {
        const start = now + 0.08 + (index / syllableCount) * Math.max(0.2, duration - 0.24);
        const held = 0.055 + (index % 3) * 0.025;
        const toneLevel = 0.2 + (index % 4) * 0.035;
        const breathLevel = 0.04 + distanceRatio * 0.07;
        toneGain.gain.setValueAtTime(0.0001, start);
        toneGain.gain.linearRampToValueAtTime(toneLevel, start + 0.018);
        toneGain.gain.setTargetAtTime(0.0001, start + held, 0.025);
        noiseGain.gain.setValueAtTime(0.0001, start);
        noiseGain.gain.linearRampToValueAtTime(breathLevel, start + 0.012);
        noiseGain.gain.setTargetAtTime(0.0001, start + held * 0.8, 0.02);
        carrier.frequency.setValueAtTime(170 + ((index * 37) % 90) + (1 - distanceRatio) * 45, start);
      }

      const clarityFilter = audioCtx.createBiquadFilter();
      clarityFilter.type = 'lowpass';
      clarityFilter.frequency.setValueAtTime(4100 - distanceRatio * 2700, now);
      clarityFilter.Q.setValueAtTime(0.8 + distanceRatio * 1.3, now);

      const speakerCurve = audioCtx.createWaveShaper();
      speakerCurve.curve = this.createDistortionCurve(40 + distanceRatio * 220);
      speakerCurve.oversample = '2x';

      const dryGain = audioCtx.createGain();
      const wetGain = audioCtx.createGain();
      dryGain.gain.setValueAtTime(1 - distanceRatio * 0.42, now);
      wetGain.gain.setValueAtTime(0.04 + distanceRatio * 0.62, now);
      const delay = audioCtx.createDelay(0.7);
      delay.delayTime.setValueAtTime(0.08 + distanceRatio * 0.28, now);
      const feedback = audioCtx.createGain();
      feedback.gain.setValueAtTime(0.18 + distanceRatio * 0.44, now);

      const spatialGain = audioCtx.createGain();
      spatialGain.gain.setValueAtTime(1, now);
      let pannerNode: StereoPannerNode | null = null;
      let binauralPannerNode: PannerNode | null = null;
      if (this.supportsBinauralPanner() && this.outputMode === 'stereo') {
        binauralPannerNode = this.createBinauralPannerNode(Math.max(1, range));
        this.setBinauralPannerPosition(
          binauralPannerNode,
          sourcePosition.x - playerPosition.x,
          sourcePosition.y - playerPosition.y,
        );
        spatialGain.connect(binauralPannerNode).connect(sfxGainNode);
      } else if (this.supportsStereoPanner() && this.outputMode === 'stereo') {
        pannerNode = audioCtx.createStereoPanner();
        pannerNode.pan.setValueAtTime(Math.max(-1, Math.min(1, mix.pan)), now);
        spatialGain.connect(pannerNode).connect(sfxGainNode);
      } else {
        spatialGain.connect(sfxGainNode);
      }

      carrier.connect(toneGain).connect(phraseGain);
      noise.connect(noiseFilter).connect(noiseGain).connect(phraseGain);
      phraseGain.connect(clarityFilter).connect(speakerCurve);
      speakerCurve.connect(dryGain).connect(spatialGain);
      speakerCurve.connect(delay).connect(wetGain).connect(spatialGain);
      delay.connect(feedback).connect(delay);

      const stopAt = now + duration + 0.9;
      carrier.start(now);
      lfo.start(now);
      noise.start(now);
      carrier.stop(stopAt);
      lfo.stop(stopAt);
      noise.stop(now + duration);
      window.setTimeout(() => {
        carrier.disconnect();
        lfo.disconnect();
        lfoGain.disconnect();
        noise.disconnect();
        noiseFilter.disconnect();
        toneGain.disconnect();
        noiseGain.disconnect();
        phraseGain.disconnect();
        clarityFilter.disconnect();
        speakerCurve.disconnect();
        dryGain.disconnect();
        wetGain.disconnect();
        delay.disconnect();
        feedback.disconnect();
        spatialGain.disconnect();
        pannerNode?.disconnect();
        binauralPannerNode?.disconnect();
      }, Math.ceil((duration + 1.1) * 1000));
    });
  }

  async playSample(url: string, gain = 1, fadeInMs = 0, playbackRate = 1): Promise<boolean> {
    await this.ensureContext();
    const { audioCtx, sfxGainNode } = this;
    if (!audioCtx || !sfxGainNode) return false;
    if (gain <= 0) return false;

    try {
      const buffer = await this.getSampleBuffer(url);
      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      const safePlaybackRate = this.normalizePlaybackRate(playbackRate);
      source.playbackRate.setValueAtTime(safePlaybackRate, audioCtx.currentTime);
      const isPortalSample = isPortalTravelSample(url);
      const startAt = audioCtx.currentTime + (isPortalSample ? PORTAL_ONE_SHOT_START_BUFFER_SECONDS : 0);
      const effectiveGain = isPortalSample ? Math.min(gain, PORTAL_ONE_SHOT_GAIN_CAP) : gain;
      const gainNode = audioCtx.createGain();
      const safeFadeMs = Number.isFinite(fadeInMs) ? Math.max(0, fadeInMs) : 0;
      if (safeFadeMs > 0) {
        gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
        gainNode.gain.linearRampToValueAtTime(effectiveGain, startAt + safeFadeMs / 1000);
      } else {
        gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
        gainNode.gain.setTargetAtTime(effectiveGain, startAt, ONE_SHOT_ATTACK_SECONDS);
      }
      source.connect(gainNode).connect(sfxGainNode);
      source.start(startAt);
      return true;
    } catch {
      // Ignore sample decode/load errors.
      return false;
    }
  }

  private playSampleOrFallback(url: string, gain: number, fallback: SoundSpec): void {
    void this.playSample(url, gain).then((played) => {
      if (!played) this.playSound(fallback);
    });
  }

  private preloadActionSoundsOnce(): void {
    if (this.actionSoundPreloadStarted) return;
    this.actionSoundPreloadStarted = true;
    this.preloadSamples([...Object.values(ACTION_SOUND_URLS), ...Object.values(DEVICE_BUTTON_SOUND_URLS)]);
  }

  private normalizePlaybackRate(value: number): number {
    return Number.isFinite(value) ? Math.max(0.35, Math.min(2.5, value)) : 1;
  }

  /** Starts a looping sample and returns a stop callback for explicit teardown. */
  async startLoopingSample(
    url: string,
    gain = 1,
    options?: { fadeInSeconds?: number; fadeOutSeconds?: number; startDelaySeconds?: number },
  ): Promise<(() => void) | null> {
    await this.ensureContext();
    const { audioCtx, sfxGainNode } = this;
    if (!audioCtx || !sfxGainNode || gain <= 0) return null;
    try {
      const buffer = await this.getSampleBuffer(url);
      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      source.loop = true;
      const gainNode = audioCtx.createGain();
      const startAt = audioCtx.currentTime + Math.max(0, options?.startDelaySeconds ?? 0);
      const fadeInSeconds = Math.max(0, options?.fadeInSeconds ?? LOOP_SAMPLE_ATTACK_SECONDS);
      const fadeOutSeconds = Math.max(0, options?.fadeOutSeconds ?? LOOP_SAMPLE_RELEASE_SECONDS);
      gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
      if (fadeInSeconds > 0) {
        gainNode.gain.setValueAtTime(0, startAt);
        gainNode.gain.linearRampToValueAtTime(gain, startAt + fadeInSeconds);
      } else {
        gainNode.gain.setValueAtTime(gain, startAt);
      }
      source.connect(gainNode).connect(sfxGainNode);
      source.start(startAt);
      return () => {
        const stopAt = audioCtx.currentTime + fadeOutSeconds;
        try {
          gainNode.gain.cancelScheduledValues(audioCtx.currentTime);
          gainNode.gain.setTargetAtTime(0.0001, audioCtx.currentTime, Math.max(0.01, fadeOutSeconds / 3));
          source.stop(stopAt + 0.02);
        } catch {
          // Ignore already-stopped source.
        }
        window.setTimeout(
          () => {
            try {
              source.disconnect();
            } catch {
              // Ignore already-disconnected source.
            }
            try {
              gainNode.disconnect();
            } catch {
              // Ignore already-disconnected gain.
            }
          },
          Math.ceil((fadeOutSeconds + 0.05) * 1000),
        );
      };
    } catch {
      return null;
    }
  }

  cleanupPeerAudio(peer: SpatialPeerRuntime): void {
    if (peer.audioElement) {
      peer.audioElement.pause();
      peer.audioElement.srcObject = null;
      peer.audioElement.remove();
    }
    peer.gain?.disconnect();
    peer.panner?.disconnect();
    peer.binauralPanner?.disconnect();
    peer.audioElement = undefined;
    peer.gain = undefined;
    peer.panner = undefined;
    peer.binauralPanner = undefined;
  }

  private rebuildOutboundEffectGraph(): void {
    if (!this.audioCtx || !this.outboundInputGain || !this.outboundDestination) {
      return;
    }

    disconnectEffectRuntime(this.outboundEffectRuntime);
    this.outboundEffectRuntime = null;
    this.outboundInputGain.disconnect();

    const effect = EFFECT_SEQUENCE[this.effectIndex].id;
    this.outboundEffectRuntime = connectEffectChain(
      this.audioCtx,
      this.outboundInputGain,
      this.outboundDestination,
      effect,
      this.effectValues[effect],
    );
    this.rebuildLoopbackGraph(effect, this.effectValues[effect]);
  }

  private rebuildLoopbackGraph(effect: EffectId, effectValue: number): void {
    if (!this.audioCtx || !this.outboundInputGain) {
      return;
    }
    disconnectEffectRuntime(this.loopbackRuntime);
    this.loopbackRuntime = null;
    if (!this.loopbackEnabled) {
      return;
    }
    this.loopbackRuntime = connectEffectChain(
      this.audioCtx,
      this.outboundInputGain,
      this.masterGainNode ?? this.audioCtx.destination,
      effect,
      effectValue,
    );
  }

  private clampLevel(value: number): number {
    return clampEffectLevel(value);
  }

  private playSound(spec: SoundSpec): void {
    const { audioCtx, sfxGainNode } = this;
    if (!audioCtx || !sfxGainNode) return;

    const baseGain = spec.gain ?? 1;
    const resolved = spec.sourcePosition
      ? resolveSpatialMix({
          dx: spec.sourcePosition.x,
          dy: spec.sourcePosition.y,
          range: Math.max(1, spec.range ?? HEARING_RADIUS),
          baseGain,
        })
      : { gain: baseGain, pan: 0 };
    if (!resolved) return;
    const finalGain = resolved.gain;
    const panValue = spec.sourcePosition ? resolved.pan : undefined;

    if (finalGain <= 0) return;

    const startTime = audioCtx.currentTime + (spec.delay ?? 0);
    const oscillator = audioCtx.createOscillator();
    oscillator.type = spec.type ?? 'sine';
    oscillator.frequency.setValueAtTime(spec.freq, startTime);

    const gainNode = audioCtx.createGain();
    gainNode.gain.setValueAtTime(finalGain, startTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, startTime + spec.duration);

    oscillator.connect(gainNode);
    if (panValue !== undefined && this.supportsStereoPanner() && this.outputMode === 'stereo') {
      const panner = audioCtx.createStereoPanner();
      panner.pan.setValueAtTime(Math.max(-1, Math.min(1, panValue)), startTime);
      gainNode.connect(panner).connect(sfxGainNode);
    } else {
      gainNode.connect(sfxGainNode);
    }

    oscillator.start(startTime);
    oscillator.stop(startTime + spec.duration);
  }

  private createNoiseBuffer(durationSeconds: number): AudioBuffer {
    if (!this.audioCtx) {
      throw new Error('Audio context is required before creating noise.');
    }
    const frameCount = Math.max(1, Math.floor(this.audioCtx.sampleRate * durationSeconds));
    const buffer = this.audioCtx.createBuffer(1, frameCount, this.audioCtx.sampleRate);
    const data = buffer.getChannelData(0);
    let previous = 0;
    for (let i = 0; i < frameCount; i += 1) {
      const white = Math.random() * 2 - 1;
      previous = previous * 0.92 + white * 0.08;
      data[i] = previous;
    }
    return buffer;
  }

  private createDistortionCurve(amount: number): Float32Array {
    const samples = 256;
    const curve = new Float32Array(samples);
    const k = Math.max(0, amount);
    for (let i = 0; i < samples; i += 1) {
      const x = (i * 2) / samples - 1;
      curve[i] = ((3 + k) * x * 20 * (Math.PI / 180)) / (Math.PI + k * Math.abs(x));
    }
    return curve;
  }

  private applySpatialSampleRuntime(
    sample: ActiveSpatialSampleRuntime,
    playerPosition: { x: number; y: number },
    initial = false,
    startAt?: number,
  ): void {
    if (!this.audioCtx) return;
    const mix = resolveSpatialMix({
      dx: sample.sourceX - playerPosition.x,
      dy: sample.sourceY - playerPosition.y,
      range: sample.range,
      baseGain: sample.baseGain,
    });
    if (initial) {
      const gainValue = mix?.gain ?? 0;
      const targetTime = Math.max(this.audioCtx.currentTime, startAt ?? this.audioCtx.currentTime);
      sample.gainNode.gain.cancelScheduledValues(this.audioCtx.currentTime);
      sample.gainNode.gain.setValueAtTime(0, this.audioCtx.currentTime);
      sample.gainNode.gain.setTargetAtTime(gainValue, targetTime, ONE_SHOT_ATTACK_SECONDS);
      if (sample.pannerNode) {
        const panValue = mix?.pan ?? 0;
        const resolvedPan = this.outputMode === 'mono' ? 0 : Math.max(-1, Math.min(1, panValue));
        sample.pannerNode.pan.setValueAtTime(resolvedPan, this.audioCtx.currentTime);
      }
      if (sample.binauralPannerNode) {
        this.setBinauralPannerPosition(
          sample.binauralPannerNode,
          this.outputMode === 'mono' ? 0 : sample.sourceX - playerPosition.x,
          this.outputMode === 'mono' ? 0 : sample.sourceY - playerPosition.y,
        );
      }
      if (sample.distanceReflections) {
        updateDistanceReflections({
          audioCtx: this.audioCtx,
          runtime: sample.distanceReflections,
          mix,
          range: sample.range,
          outputMode: this.outputMode,
          maxWetGain: 0.28,
        });
      }
      return;
    }
    if (this.audioCtx.currentTime < sample.startsAt) {
      return;
    }
    applySpatialMixToNodes({
      audioCtx: this.audioCtx,
      gainNode: sample.gainNode,
      pannerNode: sample.pannerNode,
      mix,
      outputMode: this.outputMode,
      transition: 'target',
    });
    if (sample.binauralPannerNode) {
      this.setBinauralPannerPosition(
        sample.binauralPannerNode,
        this.outputMode === 'mono' ? 0 : sample.sourceX - playerPosition.x,
        this.outputMode === 'mono' ? 0 : sample.sourceY - playerPosition.y,
      );
    }
    if (sample.distanceReflections) {
      updateDistanceReflections({
        audioCtx: this.audioCtx,
        runtime: sample.distanceReflections,
        mix,
        range: sample.range,
        outputMode: this.outputMode,
        maxWetGain: 0.28,
      });
    }
  }

  private createBinauralPannerNode(range: number): PannerNode {
    if (!this.audioCtx) {
      throw new Error('Audio context not initialized');
    }
    const panner = this.audioCtx.createPanner();
    panner.panningModel = 'HRTF';
    panner.distanceModel = 'linear';
    panner.refDistance = 1;
    panner.maxDistance = Math.max(1, range);
    panner.rolloffFactor = 0;
    panner.coneInnerAngle = 360;
    panner.coneOuterAngle = 360;
    panner.coneOuterGain = 1;
    this.setBinauralPannerPosition(panner, 0, 0);
    return panner;
  }

  private setBinauralPannerPosition(panner: PannerNode, dx: number, dy: number): void {
    const x = Number.isFinite(dx) ? dx : 0;
    const z = Number.isFinite(dy) ? -dy : 0;
    if ('positionX' in panner) {
      panner.positionX.setTargetAtTime(x, this.audioCtx?.currentTime ?? 0, SPATIAL_TIME_CONSTANT_SECONDS);
      panner.positionY.setTargetAtTime(0, this.audioCtx?.currentTime ?? 0, SPATIAL_TIME_CONSTANT_SECONDS);
      panner.positionZ.setTargetAtTime(z, this.audioCtx?.currentTime ?? 0, SPATIAL_TIME_CONSTANT_SECONDS);
      return;
    }
    panner.setPosition(x, 0, z);
  }

  private async getSampleBuffer(url: string): Promise<AudioBuffer> {
    if (!this.audioCtx) {
      throw new Error('Audio context not initialized');
    }
    if (this.sampleCache.has(url)) {
      return this.sampleCache.get(url)!;
    }
    if (!this.sampleLoaders.has(url)) {
      this.sampleLoaders.set(
        url,
        fetch(url)
          .then((response) => {
            if (!response.ok) throw new Error(`Failed to fetch sample: ${url}`);
            return response.arrayBuffer();
          })
          .then((data) => this.audioCtx!.decodeAudioData(data))
          .then((buffer) => {
            this.sampleCache.set(url, buffer);
            this.sampleLoaders.delete(url);
            return buffer;
          })
          .catch((error) => {
            this.sampleLoaders.delete(url);
            throw error;
          }),
      );
    }
    return this.sampleLoaders.get(url)!;
  }
}
