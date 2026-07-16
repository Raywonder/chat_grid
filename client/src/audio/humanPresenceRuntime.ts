import { HEARING_RADIUS, type PeerState, type Player } from '../state/gameState';
import { AudioEngine } from './audioEngine';

type PresenceAudio = Pick<AudioEngine, 'playSpatialSample'>;

type PresencePerson = Pick<Player, 'id' | 'nickname' | 'x' | 'y' | 'posture' | 'mood'> & {
  locationId?: string;
};

type PresenceSchedule = {
  posture: PresencePerson['posture'];
  nextBreathAtMs: number;
  breathCount: number;
};

const HUMAN_SOUND_RANGE = Math.min(8, HEARING_RADIUS);
const GENTLE_BREATH_URL = 'sounds/human/gentle-rest-breath.mp3?v=20260716-human-presence';
const SLEEPY_BREATH_URL = 'sounds/human/sleepy-breath.mp3?v=20260716-human-presence';
const BEDDING_SETTLE_URL = 'sounds/human/bedding-settle.mp3?v=20260716-human-presence';
const CONTENTED_SIGH_URL = 'sounds/human/soft-contented-sigh.mp3?v=20260716-human-presence';
const SLEEPY_MOODS = new Set(['dreamy', 'resting', 'sleepy', 'tired']);

/** Renders quiet, spatial human-presence cues from authoritative person state. */
export class HumanPresenceRuntime {
  private readonly schedules = new Map<string, PresenceSchedule>();
  private enabled = true;

  constructor(
    private readonly audio: PresenceAudio,
    private readonly resolveSoundUrl: (soundPath: string) => string,
  ) {}

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  reset(): void {
    this.schedules.clear();
  }

  update(options: {
    player: Player;
    peers: Iterable<PeerState>;
    currentLocationId: string;
    listenerPosition: { x: number; y: number };
    nowMs?: number;
  }): void {
    const nowMs = options.nowMs ?? Date.now();
    const presentIds = new Set<string>();
    const localId = options.player.id || 'local-player';
    this.updatePerson(
      { ...options.player, id: localId, locationId: options.currentLocationId },
      options.currentLocationId,
      options.listenerPosition,
      nowMs,
    );
    presentIds.add(localId);

    for (const peer of options.peers) {
      const peerLocationId = peer.locationId || options.currentLocationId;
      if (peerLocationId !== options.currentLocationId) continue;
      this.updatePerson(
        {
          id: peer.id,
          nickname: peer.nickname,
          x: peer.x,
          y: peer.y,
          posture: peer.posture ?? 'standing',
          mood: peer.mood ?? 'settled',
          locationId: peerLocationId,
        },
        options.currentLocationId,
        options.listenerPosition,
        nowMs,
      );
      presentIds.add(peer.id);
    }

    for (const id of this.schedules.keys()) {
      if (!presentIds.has(id)) this.schedules.delete(id);
    }
  }

  private updatePerson(
    person: PresencePerson,
    currentLocationId: string,
    listenerPosition: { x: number; y: number },
    nowMs: number,
  ): void {
    const id = person.id || person.nickname;
    const previous = this.schedules.get(id);
    if (!previous) {
      this.schedules.set(id, {
        posture: person.posture,
        nextBreathAtMs: nowMs + this.randomInterval(7_000, 14_000),
        breathCount: 0,
      });
      return;
    }

    if (previous.posture !== person.posture) {
      const enteredRest = person.posture === 'lying' || person.posture === 'sitting';
      previous.posture = person.posture;
      previous.nextBreathAtMs = nowMs + this.randomInterval(6_000, 12_000);
      previous.breathCount = 0;
      if (enteredRest && this.enabled && person.locationId === currentLocationId) {
        void this.audio.playSpatialSample(
          this.resolveSoundUrl(BEDDING_SETTLE_URL),
          person,
          listenerPosition,
          person.posture === 'lying' ? 0.24 : 0.15,
          HUMAN_SOUND_RANGE,
        );
      }
      return;
    }

    if (!this.enabled || person.posture === 'standing' || person.locationId !== currentLocationId) return;
    if (nowMs < previous.nextBreathAtMs) return;

    const sleepy = person.posture === 'lying' && SLEEPY_MOODS.has(String(person.mood).toLowerCase());
    previous.breathCount += 1;
    const useSigh = person.posture === 'lying' && previous.breathCount % 7 === 0;
    const soundUrl = useSigh ? CONTENTED_SIGH_URL : sleepy ? SLEEPY_BREATH_URL : GENTLE_BREATH_URL;
    const gain = useSigh ? 0.16 : sleepy ? 0.18 : person.posture === 'lying' ? 0.15 : 0.11;
    void this.audio.playSpatialSample(
      this.resolveSoundUrl(soundUrl),
      person,
      listenerPosition,
      gain,
      HUMAN_SOUND_RANGE,
      this.randomInterval(97, 103) / 100,
    );

    const interval = person.posture === 'lying'
      ? sleepy ? this.randomInterval(13_000, 21_000) : this.randomInterval(18_000, 30_000)
      : this.randomInterval(32_000, 52_000);
    previous.nextBreathAtMs = nowMs + interval;
  }

  private randomInterval(minimum: number, maximum: number): number {
    return Math.round(minimum + Math.random() * Math.max(0, maximum - minimum));
  }
}
