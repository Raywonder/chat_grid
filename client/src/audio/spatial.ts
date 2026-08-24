export type SpatialMixOptions = {
  dx: number;
  dy: number;
  range: number;
  baseGain?: number;
  nearFieldDistance?: number;
  nearFieldGain?: number;
  nearFieldCenterPan?: boolean;
  farFieldRangeMultiplier?: number;
  farFieldFloorGain?: number;
  directional?: {
    enabled: boolean;
    facingDeg: number;
    coneDeg?: number;
    rearGain?: number;
  };
};

export type SpatialMixResult = {
  distance: number;
  gain: number;
  pan: number;
};

export const SPATIAL_RAMP_SECONDS = 0.2;
export const SPATIAL_TIME_CONSTANT_SECONDS = SPATIAL_RAMP_SECONDS / 3;

type SpatialOutputMode = 'stereo' | 'mono';

type ApplySpatialNodeOptions = {
  audioCtx: AudioContext;
  gainNode: GainNode;
  pannerNode: StereoPannerNode | null;
  binauralPannerNode?: PannerNode | null;
  binauralPosition?: { dx: number; dy: number };
  mix: SpatialMixResult | null;
  outputMode: SpatialOutputMode;
  transition: 'linear' | 'target';
  transitionSeconds?: number;
};

/**
 * Applies one resolved spatial mix to gain/pan nodes with a shared transition profile.
 */
export function applySpatialMixToNodes(options: ApplySpatialNodeOptions): void {
  const { audioCtx, gainNode, pannerNode, binauralPannerNode, binauralPosition, mix, outputMode, transition } = options;
  const transitionSeconds =
    typeof options.transitionSeconds === 'number' && Number.isFinite(options.transitionSeconds)
      ? Math.max(0.01, options.transitionSeconds)
      : SPATIAL_RAMP_SECONDS;
  const gainValue = mix?.gain ?? 0;
  const panValue = mix?.pan ?? 0;
  const resolvedPan = outputMode === 'mono' ? 0 : Math.max(-1, Math.min(1, panValue));
  if (binauralPannerNode && binauralPosition && outputMode === 'stereo') {
    const x = Number.isFinite(binauralPosition.dx) ? binauralPosition.dx : 0;
    const z = Number.isFinite(binauralPosition.dy) ? -binauralPosition.dy : 0;
    const now = audioCtx.currentTime;
    if ('positionX' in binauralPannerNode) {
      binauralPannerNode.positionX.setTargetAtTime(x, now, SPATIAL_TIME_CONSTANT_SECONDS);
      binauralPannerNode.positionY.setTargetAtTime(0, now, SPATIAL_TIME_CONSTANT_SECONDS);
      binauralPannerNode.positionZ.setTargetAtTime(z, now, SPATIAL_TIME_CONSTANT_SECONDS);
    } else {
      binauralPannerNode.setPosition(x, 0, z);
    }
  }

  if (transition === 'linear') {
    gainNode.gain.cancelScheduledValues(audioCtx.currentTime);
    gainNode.gain.linearRampToValueAtTime(gainValue, audioCtx.currentTime + transitionSeconds);
    if (pannerNode) {
      pannerNode.pan.cancelScheduledValues(audioCtx.currentTime);
      pannerNode.pan.linearRampToValueAtTime(resolvedPan, audioCtx.currentTime + transitionSeconds);
    }
    return;
  }

  gainNode.gain.setTargetAtTime(gainValue, audioCtx.currentTime, transitionSeconds / 3);
  if (pannerNode) {
    pannerNode.pan.setTargetAtTime(resolvedPan, audioCtx.currentTime, transitionSeconds / 3);
  }
}

type DirectionalProfile = {
  attenuationFactor: number;
  offAxisRatio: number;
};

export function resolveSpatialMix(options: SpatialMixOptions): SpatialMixResult | null {
  const {
    dx,
    dy,
    range,
    baseGain = 1,
    nearFieldDistance,
    nearFieldGain = 1,
    nearFieldCenterPan = false,
    farFieldRangeMultiplier = 1,
    farFieldFloorGain = 0,
  } = options;
  if (!(range > 0)) {
    return null;
  }

  const distance = Math.hypot(dx, dy);
  const audibleRange = range * Math.max(1, Math.min(3, farFieldRangeMultiplier));
  let effectiveRange = audibleRange;
  if (options.directional?.enabled) {
    const directionalProfile = resolveDirectionalProfile(dx, dy, options.directional);
    effectiveRange = Math.max(0.01, audibleRange * directionalProfile.attenuationFactor);
  }

  if (distance > effectiveRange) {
    return null;
  }

  const volumeRatio = Math.max(0, 1 - distance / effectiveRange);
  const slowRolloff = Math.pow(volumeRatio, 1.35);
  const floor = Math.max(0, Math.min(0.25, farFieldFloorGain));
  const shapedVolume = floor + (1 - floor) * slowRolloff;
  let gain = baseGain * shapedVolume;
  const clampedX = Math.max(-range, Math.min(range, dx));
  let pan = Math.sin((clampedX / range) * (Math.PI / 2));

  if (nearFieldDistance !== undefined && distance < nearFieldDistance) {
    gain = baseGain * nearFieldGain;
    if (nearFieldCenterPan) {
      pan = 0;
    }
  }

  return { distance, gain, pan };
}

/** Converts a world-relative source offset into listener-relative coordinates. */
export function rotateRelativePosition(
  dx: number,
  dy: number,
  headingDeg = 0,
): { dx: number; dy: number } {
  const heading = (normalizeDegrees(headingDeg) * Math.PI) / 180;
  // World x is east and world y is north. The listener's local x is right
  // and local y is forward, so clockwise heading rotates the sound field.
  return {
    dx: dx * Math.cos(heading) - dy * Math.sin(heading),
    dy: dx * Math.sin(heading) + dy * Math.cos(heading),
  };
}

/** Stereo fallback pan for a listener-relative source position. */
export function resolveSpatialPan(dx: number, range: number): number {
  if (!(range > 0)) return 0;
  const clampedX = Math.max(-range, Math.min(range, dx));
  return Math.sin((clampedX / range) * (Math.PI / 2));
}

export function resolveDirectionalMuffleRatio(
  dx: number,
  dy: number,
  directional: SpatialMixOptions['directional'],
): number {
  if (!directional?.enabled) return 0;
  return resolveDirectionalProfile(dx, dy, directional).offAxisRatio;
}

export function normalizeDegrees(value: number): number {
  if (!Number.isFinite(value)) return 0;
  const wrapped = value % 360;
  return wrapped < 0 ? wrapped + 360 : wrapped;
}

/** Computes compass bearing from source to listener where 0 is north and 90 is east. */
function bearingFromSourceToListener(dx: number, dy: number): number {
  // 0 degrees is north (+y), 90 is east (+x), matching screen-reader compass wording.
  const degrees = Math.atan2(dx, dy) * (180 / Math.PI);
  return normalizeDegrees(degrees);
}

/** Returns shortest absolute angular difference in degrees on a circle. */
function angularDifferenceDeg(a: number, b: number): number {
  const raw = Math.abs(normalizeDegrees(a) - normalizeDegrees(b));
  return raw > 180 ? 360 - raw : raw;
}

/** Computes directional attenuation profile based on listener angle vs source facing. */
function resolveDirectionalProfile(
  dx: number,
  dy: number,
  directional: NonNullable<SpatialMixOptions['directional']>,
): DirectionalProfile {
  const coneDeg = Math.max(1, Math.min(359, directional.coneDeg ?? 120));
  const rearGain = Math.max(0, Math.min(1, directional.rearGain ?? 0.5));
  const facingDeg = normalizeDegrees(directional.facingDeg);
  // `dx/dy` are listener-relative source coords in current callers, so invert to get source->listener bearing.
  const bearingDeg = bearingFromSourceToListener(-dx, -dy);
  const diff = angularDifferenceDeg(facingDeg, bearingDeg);
  const halfCone = coneDeg / 2;
  if (diff <= halfCone) {
    return { attenuationFactor: 1, offAxisRatio: 0 };
  }
  const span = Math.max(1, 180 - halfCone);
  const linearRatio = Math.max(0, Math.min(1, (diff - halfCone) / span));
  const offAxisRatio = linearRatio * linearRatio * (3 - 2 * linearRatio);
  return {
    attenuationFactor: 1 - offAxisRatio * (1 - rearGain),
    offAxisRatio,
  };
}
