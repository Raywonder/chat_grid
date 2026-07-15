import { SPATIAL_TIME_CONSTANT_SECONDS, type SpatialMixResult } from './spatial';

type OutputMode = 'stereo' | 'mono';

export type DistanceReflectionRuntime = {
  input: GainNode;
  earlyDelay: DelayNode;
  lateDelay: DelayNode;
  feedback: GainNode;
  tone: BiquadFilterNode;
  wetGain: GainNode;
  panner: StereoPannerNode | null;
  nodes: AudioNode[];
};

type ReflectionUpdateOptions = {
  audioCtx: AudioContext;
  runtime: DistanceReflectionRuntime;
  mix: SpatialMixResult | null;
  range: number;
  outputMode: OutputMode;
  maxWetGain?: number;
  proximityEffect?: boolean;
};

/**
 * Adds a quiet parallel room-reflection path for spatial continuous sources.
 * Direct audio stays clear; distance only brings in a soft delayed layer behind it.
 */
export function connectDistanceReflections(
  audioCtx: AudioContext,
  source: AudioNode,
  destination: AudioNode,
  canStereoPan: boolean,
): DistanceReflectionRuntime {
  const input = audioCtx.createGain();
  input.gain.value = 1;

  const earlyDelay = audioCtx.createDelay(0.45);
  earlyDelay.delayTime.value = 0.035;
  const lateDelay = audioCtx.createDelay(0.85);
  lateDelay.delayTime.value = 0.12;
  const feedback = audioCtx.createGain();
  feedback.gain.value = 0.05;

  const tone = audioCtx.createBiquadFilter();
  tone.type = 'lowpass';
  tone.frequency.value = 4200;
  tone.Q.value = 0.7;

  const wetGain = audioCtx.createGain();
  wetGain.gain.value = 0;

  let panner: StereoPannerNode | null = null;
  if (canStereoPan) {
    panner = audioCtx.createStereoPanner();
    wetGain.connect(panner).connect(destination);
  } else {
    wetGain.connect(destination);
  }

  source.connect(input);
  input.connect(earlyDelay).connect(tone);
  input.connect(lateDelay);
  lateDelay.connect(feedback).connect(lateDelay);
  lateDelay.connect(tone);
  tone.connect(wetGain);

  return {
    input,
    earlyDelay,
    lateDelay,
    feedback,
    tone,
    wetGain,
    panner,
    nodes: [input, earlyDelay, lateDelay, feedback, tone, wetGain, ...(panner ? [panner] : [])],
  };
}

export function updateDistanceReflections(options: ReflectionUpdateOptions): void {
  const { audioCtx, runtime, mix, range, outputMode } = options;
  const now = audioCtx.currentTime;
  const maxWetGain = Math.max(0, Math.min(0.35, options.maxWetGain ?? 0.16));
  const distanceRatio = mix ? Math.max(0, Math.min(1, mix.distance / Math.max(1, range))) : 0;
  const audibleGain = mix ? Math.max(0, Math.min(1, mix.gain)) : 0;
  const farShape = distanceRatio * distanceRatio * (3 - 2 * distanceRatio);
  const nearShape = (1 - distanceRatio) * (1 - distanceRatio);
  const reflectionShape = options.proximityEffect ? nearShape : farShape;
  const nearSuppression = options.proximityEffect || distanceRatio >= 0.18 ? 1 : distanceRatio / 0.18;
  const wetGain = mix ? maxWetGain * reflectionShape * nearSuppression * Math.min(1, 0.35 + audibleGain) : 0;
  const earlyDelaySeconds = 0.018 + reflectionShape * 0.105;
  const lateDelaySeconds = 0.07 + reflectionShape * 0.31;
  const feedbackGain = 0.035 + reflectionShape * 0.19;
  const toneHz = 5200 - reflectionShape * 3300;
  const reflectionPan = outputMode === 'mono' || !mix ? 0 : Math.max(-1, Math.min(1, mix.pan * 0.42));

  runtime.wetGain.gain.setTargetAtTime(wetGain, now, SPATIAL_TIME_CONSTANT_SECONDS);
  runtime.earlyDelay.delayTime.setTargetAtTime(earlyDelaySeconds, now, SPATIAL_TIME_CONSTANT_SECONDS);
  runtime.lateDelay.delayTime.setTargetAtTime(lateDelaySeconds, now, SPATIAL_TIME_CONSTANT_SECONDS);
  runtime.feedback.gain.setTargetAtTime(feedbackGain, now, SPATIAL_TIME_CONSTANT_SECONDS);
  runtime.tone.frequency.setTargetAtTime(toneHz, now, SPATIAL_TIME_CONSTANT_SECONDS);
  runtime.panner?.pan.setTargetAtTime(reflectionPan, now, SPATIAL_TIME_CONSTANT_SECONDS);
}

export function disconnectDistanceReflections(runtime: DistanceReflectionRuntime | null): void {
  if (!runtime) return;
  for (const node of runtime.nodes) {
    node.disconnect();
  }
}
