import { describe, expect, it } from 'vitest';
import { PLAYER_TURN_STEP_DEG, turnHeading } from './orientation';

describe('listener turning', () => {
  it('turns in 15 degree increments and wraps around north', () => {
    expect(PLAYER_TURN_STEP_DEG).toBe(15);
    expect(turnHeading(0, 'left')).toBe(345);
    expect(turnHeading(345, 'right')).toBe(0);
    expect(turnHeading(350, 'right')).toBe(5);
  });
});
