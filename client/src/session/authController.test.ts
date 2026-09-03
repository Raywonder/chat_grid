import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createAuthController } from './authController';

class FakeClassList {
  private readonly values = new Set<string>();

  add(value: string): void {
    this.values.add(value);
  }

  remove(value: string): void {
    this.values.delete(value);
  }

  toggle(value: string, force?: boolean): boolean {
    const enabled = force ?? !this.values.has(value);
    if (enabled) this.values.add(value);
    else this.values.delete(value);
    return enabled;
  }

  contains(value: string): boolean {
    return this.values.has(value);
  }
}

function fakeElement() {
  return {
    classList: new FakeClassList(),
    hidden: false,
    disabled: false,
    textContent: '',
    addEventListener: vi.fn(),
    focus: vi.fn(),
  };
}

describe('authController browser sign-in state', () => {
  const localValues = new Map<string, string>();
  const sessionValues = new Map<string, string>();
  let bodyClassList: FakeClassList;

  beforeEach(() => {
    localValues.clear();
    sessionValues.clear();
    bodyClassList = new FakeClassList();
    vi.stubGlobal('document', { body: { classList: bodyClassList } });
    vi.stubGlobal('window', { setTimeout: (callback: () => void) => callback() });
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => localValues.get(key) ?? null,
      setItem: (key: string, value: string) => localValues.set(key, value),
    });
    vi.stubGlobal('sessionStorage', {
      removeItem: (key: string) => sessionValues.delete(key),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('keeps the authenticated interface unlocked after consuming the one-time assertion', async () => {
    const authSessionView = fakeElement();
    const controller = createAuthController({
      dom: {
        loginView: fakeElement(),
        authSessionView,
        authSessionText: fakeElement(),
        signInButton: fakeElement(),
        connectButton: fakeElement(),
        guestButton: fakeElement(),
        logoutButton: fakeElement(),
      } as never,
      authPolicyStorageKey: 'test-auth-policy',
      authSessionCookieSetUrl: '/session/set',
      authSessionCookieClearUrl: '/session/clear',
      authSessionCookieClientHeader: 'X-Test-Client',
      initialAuthUsername: '',
      initialExternalAuthAssertion: 'one-time-assertion',
      isRunning: () => false,
      isMuted: () => false,
      isConnecting: () => false,
      setConnecting: vi.fn(),
      applyMuteToTrack: vi.fn(),
      signalingSend: vi.fn(),
      disconnect: vi.fn(),
      saveAuthUsername: vi.fn(),
      setConnectionStatus: vi.fn(),
      updateStatus: vi.fn(),
      pushChatMessage: vi.fn(),
      onServerAdminMenuActions: vi.fn(),
    });

    await controller.handleAuthResult({
      type: 'auth_result',
      ok: true,
      message: 'Signed in.',
      username: 'dom',
      role: 'user',
      permissions: [],
    });

    expect(bodyClassList.contains('auth-locked')).toBe(false);
    expect(authSessionView.classList.contains('hidden')).toBe(false);
  });
});
