import { describe, expect, it } from 'vitest';
import { createInitialState } from './gameState';

describe('initial world input state', () => {
  it('leaves arrow keys available for movement until a remote is explicitly focused', () => {
    expect(createInitialState().remoteControlsFocused).toBe(false);
  });
});
