export const PLAYER_TURN_STEP_DEG = 15;

export type TurnDirection = 'left' | 'right';

export function normalizeHeading(value: number): number {
  const normalized = value % 360;
  return normalized < 0 ? normalized + 360 : normalized;
}

export function turnHeading(headingDeg: number, direction: TurnDirection): number {
  const delta = direction === 'left' ? -PLAYER_TURN_STEP_DEG : PLAYER_TURN_STEP_DEG;
  return normalizeHeading(headingDeg + delta);
}
