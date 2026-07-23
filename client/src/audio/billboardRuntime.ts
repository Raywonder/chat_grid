import { type WorldItem } from '../state/gameState';
import { AudioEngine } from './audioEngine';

type BillboardSpatialConfig = {
  range: number;
  directional: boolean;
  facingDeg: number;
};

const MIN_ROTATION_SECONDS = 60;
const DEFAULT_ROTATION_SECONDS = 60;
const APPROACH_COOLDOWN_MS = 4500;
const MIN_SPEECH_GAP_MS = 900;
const MIN_RECORDED_ANNOUNCEMENT_GAP_MS = 15_000;

type BillboardState = {
  lastText: string;
  lastPlayedAtMs: number;
  lastBannerIndex: number;
  wasInRange: boolean;
  playedIntro: boolean;
  rotationCount: number;
};

export class BillboardRuntime {
  private readonly stateByItemId = new Map<string, BillboardState>();
  private layerEnabled = true;
  private lastSpeechStartedAtMs = 0;
  private lastRecordedAnnouncementStartedAtMs = 0;

  constructor(
    private readonly audio: AudioEngine,
    private readonly getSpatialConfig: (item: WorldItem) => BillboardSpatialConfig,
    private readonly announceText: (message: string) => void,
    private readonly recordText: (message: string) => void = announceText,
    private readonly shouldSpeakAnnouncement: (item: WorldItem) => boolean = () => true,
  ) {}

  setLayerEnabled(enabled: boolean): void {
    this.layerEnabled = enabled;
    if (!enabled) {
      this.stateByItemId.clear();
    }
  }

  cleanup(itemId: string): void {
    this.stateByItemId.delete(itemId);
  }

  update(items: Map<string, WorldItem>, listenerPosition: { x: number; y: number }): void {
    if (!this.layerEnabled) return;
    const nowMs = Date.now();
    const seenIds = new Set<string>();
    for (const item of items.values()) {
      if (item.type !== 'billboard') continue;
      seenIds.add(item.id);
      const enabled = item.params.enabled !== false;
      const expiresAtMs = Number(item.params.expiresAtMs ?? 0);
      const maxRotations = Number(item.params.maxRotations ?? 0);
      if (!enabled || item.carrierId || (expiresAtMs > 0 && nowMs >= expiresAtMs)) {
        this.markOutOfRange(item.id);
        continue;
      }
      const range = Math.max(1, this.getSpatialConfig(item).range || 12);
      const distance = Math.hypot(item.x - listenerPosition.x, item.y - listenerPosition.y);
      if (distance > range) {
        this.markOutOfRange(item.id);
        continue;
      }
      const state = this.stateByItemId.get(item.id) ?? {
        lastText: '',
        lastPlayedAtMs: 0,
        lastBannerIndex: -1,
        wasInRange: false,
        playedIntro: false,
        rotationCount: 0,
      };
      if (maxRotations > 0 && state.rotationCount >= maxRotations) {
        state.wasInRange = true;
        this.stateByItemId.set(item.id, state);
        continue;
      }
      const rotationMs = resolveRotationMs(item);
      const shouldPlay =
        !state.wasInRange ||
        (nowMs - state.lastPlayedAtMs >= rotationMs && state.lastPlayedAtMs > 0) ||
        (state.lastPlayedAtMs === 0 && nowMs - state.lastPlayedAtMs >= APPROACH_COOLDOWN_MS);
      if (!shouldPlay) {
        state.wasInRange = true;
        this.stateByItemId.set(item.id, state);
        continue;
      }
      const next = resolveBillboardAnnouncement(item, state.lastBannerIndex, state.playedIntro);
      if (!next) {
        state.wasInRange = true;
        this.stateByItemId.set(item.id, state);
        continue;
      }
      const spoken = `${item.title}: ${next.text}`;
      const voiceAssetUrl = resolveVoiceAssetUrl(item);
      if (voiceAssetUrl) {
        if (nowMs - this.lastRecordedAnnouncementStartedAtMs < MIN_RECORDED_ANNOUNCEMENT_GAP_MS) {
          state.wasInRange = true;
          this.stateByItemId.set(item.id, state);
          continue;
        }
        this.lastRecordedAnnouncementStartedAtMs = nowMs;
        this.audio.preloadSamples([voiceAssetUrl]);
        void this.audio
          .playSpatialSample(voiceAssetUrl, { x: item.x, y: item.y }, listenerPosition, 0.96, range, 1, true)
          .then((played) => {
            if (played) {
              this.recordText(spoken);
              return;
            }
            this.announceText(spoken);
            this.playSyntheticBillboardVoice(spoken, item, listenerPosition, range);
          });
      } else {
        this.announceText(spoken);
        this.playSyntheticBillboardVoice(spoken, item, listenerPosition, range);
      }
      state.lastBannerIndex = next.bannerIndex;
      state.lastText = next.text;
      state.lastPlayedAtMs = nowMs;
      state.wasInRange = true;
      state.playedIntro = true;
      state.rotationCount += 1;
      this.stateByItemId.set(item.id, state);
    }

    for (const itemId of Array.from(this.stateByItemId.keys())) {
      if (!seenIds.has(itemId)) {
        this.stateByItemId.delete(itemId);
      }
    }
  }

  private markOutOfRange(itemId: string): void {
    const state = this.stateByItemId.get(itemId);
    if (!state) return;
    state.wasInRange = false;
    this.stateByItemId.set(itemId, state);
  }

  private playSyntheticBillboardVoice(
    spoken: string,
    item: WorldItem,
    listenerPosition: { x: number; y: number },
    range: number,
  ): void {
    this.audio.playSpatialBillboardAnnouncement(spoken, { x: item.x, y: item.y }, listenerPosition, range);
    if (this.shouldSpeakAnnouncement(item)) {
      this.speakBillboardVoice(spoken, item);
    }
  }

  private speakBillboardVoice(text: string, item: WorldItem): void {
    if (!this.layerEnabled) return;
    if (String(item.params.voiceName ?? '').trim().toLowerCase() === 'clawdia') return;
    const synth = window.speechSynthesis;
    if (!synth || typeof SpeechSynthesisUtterance === 'undefined') return;
    const nowMs = Date.now();
    if (synth.speaking || synth.pending || nowMs - this.lastSpeechStartedAtMs < MIN_SPEECH_GAP_MS) {
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    const voiceName = String(item.params.voiceName ?? '').trim();
    utterance.voice = chooseAnnouncementVoice(synth.getVoices(), voiceName);
    utterance.rate = voiceName.toLowerCase() === 'clawdia' ? 0.94 : 0.98;
    utterance.pitch = voiceName.toLowerCase() === 'clawdia' ? 1.08 : 1;
    utterance.volume = 0.92;
    utterance.lang = utterance.voice?.lang || 'en-US';
    this.lastSpeechStartedAtMs = nowMs;
    synth.speak(utterance);
  }
}

function resolveVoiceAssetUrl(item: WorldItem): string {
  const explicit = String(item.params.voiceAssetUrl ?? item.params.voiceAudioUrl ?? '').trim();
  if (explicit) return explicit;
  return String(item.params.voiceName ?? '').trim().toLowerCase() === 'clawdia'
    ? 'sounds/billboards/clawdia-town.mp3'
    : '';
}

function chooseAnnouncementVoice(
  voices: SpeechSynthesisVoice[],
  voiceName: string,
): SpeechSynthesisVoice | null {
  if (voices.length === 0) return null;
  const wanted = voiceName.trim().toLowerCase();
  if (wanted) {
    const exact = voices.find((voice) => voice.name.toLowerCase() === wanted);
    if (exact) return exact;
    const contains = voices.find((voice) => voice.name.toLowerCase().includes(wanted));
    if (contains) return contains;
  }
  if (wanted === 'clawdia') {
    const clawdiaLike = ['claudia', 'sylvie', 'samantha', 'ava', 'zira', 'amelie', 'french'];
    const match = voices.find((voice) => {
      const name = voice.name.toLowerCase();
      const lang = voice.lang.toLowerCase();
      return clawdiaLike.some((needle) => name.includes(needle)) || lang.startsWith('fr');
    });
    if (match) return match;
  }
  return (
    voices.find((voice) => voice.default && voice.lang.toLowerCase().startsWith('en')) ??
    voices.find((voice) => voice.lang.toLowerCase().startsWith('en')) ??
    voices[0] ??
    null
  );
}

function resolveRotationMs(item: WorldItem): number {
  const raw = Number(item.params.rotationSeconds);
  const seconds = Number.isFinite(raw) ? Math.max(MIN_ROTATION_SECONDS, raw) : DEFAULT_ROTATION_SECONDS;
  return seconds * 1000;
}

function resolveBillboardAnnouncement(
  item: WorldItem,
  previousBannerIndex: number,
  playedIntro: boolean,
): { text: string; bannerIndex: number } | null {
  const mode = String(item.params.billboardMode ?? 'interactive').trim().toLowerCase();
  const voiceName = String(item.params.voiceName ?? '').trim();
  const announcement = String(item.params.announcementText ?? '').trim();
  const banners = String(item.params.bannerText ?? '')
    .split('|')
    .map((part) => part.trim())
    .filter(Boolean);
  if (announcement && (banners.length === 0 || !playedIntro)) {
    const prefix = voiceName ? `${voiceName} says: ` : '';
    return { text: `${prefix}${announcement}`, bannerIndex: previousBannerIndex };
  }
  if (banners.length > 0) {
    const nextIndex = (previousBannerIndex + 1) % banners.length;
    return { text: banners[nextIndex], bannerIndex: nextIndex };
  }
  if (mode === 'audio_only') {
    return null;
  }
  const headline = String(item.params.headline ?? '').trim();
  const body = String(item.params.body ?? '').trim();
  const fallback = [headline || item.title, body].filter(Boolean).join('. ');
  return fallback ? { text: fallback, bannerIndex: previousBannerIndex } : null;
}
