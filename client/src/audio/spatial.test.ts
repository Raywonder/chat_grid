import { describe, expect, it } from 'vitest';
import { resolveSpatialPan, rotateRelativePosition } from './spatial';

describe('listener-relative spatial rotation', () => {
  it('keeps north ahead at zero heading', () => {
    expect(rotateRelativePosition(0, 4, 0)).toEqual({ dx: 0, dy: 4 });
  });

  it('moves world north to the listener left after turning east', () => {
    const relative = rotateRelativePosition(0, 4, 90);
    expect(relative.dx).toBeCloseTo(-4);
    expect(relative.dy).toBeCloseTo(0);
    expect(resolveSpatialPan(relative.dx, 4)).toBeCloseTo(-1);
  });

  it('rotates a full circle back to the original sound field', () => {
    const relative = rotateRelativePosition(3, -2, 360);
    expect(relative.dx).toBeCloseTo(3);
    expect(relative.dy).toBeCloseTo(-2);
  });
});
