import { describe, expect, it } from 'vitest';
import { resolveMainModeCommand } from './mainCommandRouter';

describe('conversation shortcuts', () => {
  it('keeps Control M assigned to the focused direct conversation', () => {
    expect(resolveMainModeCommand('KeyM', false, true)).toBe('openDirectMessage');
  });

  it('reserves Control comma and period for conversation history', () => {
    expect(resolveMainModeCommand('Comma', false, true)).toBeNull();
    expect(resolveMainModeCommand('Period', false, true)).toBeNull();
    expect(resolveMainModeCommand('Comma', true, true)).toBeNull();
    expect(resolveMainModeCommand('Period', true, true)).toBeNull();
  });

  it('keeps Control arrows available to a carried media remote', () => {
    expect(resolveMainModeCommand('ArrowLeft', false, true)).toBe('radioRemoteStationPrevious');
    expect(resolveMainModeCommand('ArrowRight', false, true)).toBe('radioRemoteStationNext');
  });

  it('separates taking an item from describing its surface', () => {
    expect(resolveMainModeCommand('KeyJ', false, false)).toBe('pickupSurfaceItem');
    expect(resolveMainModeCommand('KeyJ', true, false)).toBe('describeSurface');
  });

  it('assigns shifted Enter to object interaction and shifted R to user actions', () => {
    expect(resolveMainModeCommand('Enter', true, false)).toBe('interactItem');
    expect(resolveMainModeCommand('KeyR', true, false)).toBe('openUserActionMenu');
  });
});
