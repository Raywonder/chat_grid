import type { IncomingMessage, OutgoingMessage } from '../network/protocol';

export type AuthPolicy = {
  usernameMinLength: number;
  usernameMaxLength: number;
  passwordMinLength: number;
  passwordMaxLength: number;
};

type AuthDom = {
  loginView: HTMLElement;
  authSessionView: HTMLElement;
  authSessionText: HTMLParagraphElement;
  connectButton: HTMLButtonElement;
  logoutButton: HTMLButtonElement;
};

type AuthControllerDeps = {
  dom: AuthDom;
  authPolicyStorageKey: string;
  authSessionCookieSetUrl: string;
  authSessionCookieClearUrl: string;
  authSessionCookieClientHeader: string;
  initialAuthUsername: string;
  initialExternalAuthAssertion: string;
  isRunning: () => boolean;
  isMuted: () => boolean;
  isConnecting: () => boolean;
  setConnecting: (value: boolean) => void;
  applyMuteToTrack: (muted: boolean) => void;
  signalingSend: (message: OutgoingMessage) => void;
  disconnect: () => void;
  saveAuthUsername: (username: string) => void;
  setConnectionStatus: (message: string) => void;
  updateStatus: (message: string) => void;
  pushChatMessage: (message: string) => void;
  onServerAdminMenuActions: (actions: Array<{ id: string; label: string; tooltip?: string }> | null | undefined) => void;
};

type AuthUiDeps = {
  connect: () => Promise<void>;
};

type WelcomeAuth = Extract<IncomingMessage, { type: 'welcome' }>['auth'];

/**
 * Creates the auth/session controller used by the pre-connect UI and auth packet flow.
 */
export function createAuthController(deps: AuthControllerDeps): {
  initializeUi: () => void;
  setupUiHandlers: (uiDeps: AuthUiDeps) => void;
  updateConnectAvailability: () => void;
  hasPermission: (key: string) => boolean;
  getVoiceSendAllowed: () => boolean;
  reapplyVoiceSendPermission: () => void;
  getAuthUserId: () => string;
  sendAuthRequest: () => void;
  handleAuthRequired: (message: Extract<IncomingMessage, { type: 'auth_required' }>) => void;
  handleAuthResult: (message: Extract<IncomingMessage, { type: 'auth_result' }>) => Promise<void>;
  handleAuthPermissions: (message: Extract<IncomingMessage, { type: 'auth_permissions' }>) => void;
  setSavedSessionCookieAvailable: (available: boolean) => void;
  applyWelcomeAuth: (
    auth: WelcomeAuth,
    adminMenuActions: Array<{ id: string; label: string; tooltip?: string }> | null | undefined,
  ) => void;
  logOutAccount: () => void;
} {
  let authUsername = deps.initialAuthUsername;
  let authUserId = '';
  let authPolicy: AuthPolicy | null = null;
  let authPermissions = new Set<string>();
  let voiceSendAllowed = true;
  let pendingAuthRequest = false;
  let externalAuthAssertion = deps.initialExternalAuthAssertion.trim();
  let savedSessionCookieAvailable = false;

  function sanitizeAuthUsername(value: string): string {
    const maxLength = authPolicy?.usernameMaxLength ?? 128;
    return value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, '')
      .slice(0, Math.max(1, maxLength));
  }

  function applyVoiceSendPermission(): void {
    voiceSendAllowed = authPermissions.has('voice.send');
    if (voiceSendAllowed) {
      deps.applyMuteToTrack(deps.isMuted());
      return;
    }
    deps.applyMuteToTrack(true);
  }

  function applyAuthPermissions(role: string | null | undefined, permissions: string[] | null | undefined): void {
    void role;
    authPermissions = new Set((permissions || []).map((value) => String(value).trim()).filter((value) => value.length > 0));
    applyVoiceSendPermission();
  }

  function applyAuthPolicy(policy: unknown): void {
    if (!policy || typeof policy !== 'object') return;
    const raw = policy as Partial<AuthPolicy>;
    const usernameMin = Number(raw.usernameMinLength);
    const usernameMax = Number(raw.usernameMaxLength);
    const passwordMin = Number(raw.passwordMinLength);
    const passwordMax = Number(raw.passwordMaxLength);
    if (
      !Number.isInteger(usernameMin) ||
      !Number.isInteger(usernameMax) ||
      !Number.isInteger(passwordMin) ||
      !Number.isInteger(passwordMax)
    ) {
      return;
    }
    if (usernameMin < 1 || usernameMax < usernameMin || passwordMin < 1 || passwordMax < passwordMin) {
      return;
    }
    authPolicy = {
      usernameMinLength: usernameMin,
      usernameMaxLength: usernameMax,
      passwordMinLength: passwordMin,
      passwordMaxLength: passwordMax,
    };
    localStorage.setItem(deps.authPolicyStorageKey, JSON.stringify(authPolicy));
    updateConnectAvailability();
  }

  function loadPersistedAuthPolicy(): void {
    const raw = localStorage.getItem(deps.authPolicyStorageKey);
    if (!raw) return;
    try {
      applyAuthPolicy(JSON.parse(raw));
    } catch {
      // Ignore malformed persisted policy and keep live server policy source of truth.
    }
  }

  function resetSavedSessionHint(): void {
    authUserId = '';
    authUsername = '';
    savedSessionCookieAvailable = false;
    deps.saveAuthUsername('');
  }

  function updateConnectAvailability(): void {
    const hasSavedUsernameHint = sanitizeAuthUsername(authUsername).length > 0;
    const hasSavedSessionHint = hasSavedUsernameHint || savedSessionCookieAvailable;
    const hasExternalAuth = externalAuthAssertion.length > 0;
    const showLogout = deps.isRunning() || hasSavedSessionHint;
    deps.dom.logoutButton.classList.toggle('hidden', !showLogout);
    deps.dom.logoutButton.disabled = !showLogout;
    if (deps.isRunning()) {
      deps.dom.connectButton.textContent = 'Connect';
      deps.dom.connectButton.disabled = true;
      deps.dom.loginView.classList.add('hidden');
      deps.dom.authSessionView.classList.add('hidden');
      return;
    }
    if (hasSavedSessionHint) {
      deps.dom.authSessionText.textContent = hasSavedUsernameHint
        ? `Logged in as ${sanitizeAuthUsername(authUsername)}.`
        : 'Logged in with your saved blind.software session.';
      deps.dom.loginView.classList.add('hidden');
      deps.dom.authSessionView.classList.remove('hidden');
    } else {
      deps.dom.loginView.classList.remove('hidden');
      deps.dom.authSessionView.classList.add('hidden');
    }
    const authReady = hasExternalAuth || hasSavedSessionHint;
    deps.dom.connectButton.textContent = deps.isConnecting()
      ? 'Connecting...'
      : hasSavedSessionHint
      ? 'Connect'
      : hasExternalAuth
        ? 'Continue with blind.software'
        : 'Connect';
    deps.dom.connectButton.disabled = deps.isConnecting() || !authReady;
  }

  function buildAuthRequestPacket(): OutgoingMessage | null {
    if (externalAuthAssertion) {
      return { type: 'auth_external', assertion: externalAuthAssertion };
    }
    return null;
  }

  function sendAuthRequest(): void {
    const packet = buildAuthRequestPacket();
    if (!packet) {
      pendingAuthRequest = false;
      if (sanitizeAuthUsername(authUsername).length > 0 || savedSessionCookieAvailable) {
        deps.setConnectionStatus('Restoring saved session...');
      } else {
        deps.setConnectionStatus('Sign in with blind.software to join the grid.');
        deps.setConnecting(false);
      }
      updateConnectAvailability();
      return;
    }
    pendingAuthRequest = true;
    deps.setConnectionStatus('Authenticating...');
    deps.signalingSend(packet);
  }

  function handleAuthRequired(message: Extract<IncomingMessage, { type: 'auth_required' }>): void {
    const hadPendingRequest = pendingAuthRequest;
    pendingAuthRequest = false;
    authUserId = '';
    applyAuthPolicy(message.authPolicy);
    applyAuthPermissions('user', []);
    deps.onServerAdminMenuActions([]);
    deps.setConnectionStatus('Authentication required.');
    deps.updateStatus(message.message);
    if (!hadPendingRequest) {
      const packet = buildAuthRequestPacket();
      if (packet) {
        pendingAuthRequest = true;
        deps.setConnectionStatus('Authenticating...');
        deps.signalingSend(packet);
        return;
      }
      if (sanitizeAuthUsername(authUsername).length > 0 || savedSessionCookieAvailable) {
        resetSavedSessionHint();
      }
      deps.setConnecting(false);
      updateConnectAvailability();
    }
  }

  async function persistHttpOnlySessionCookie(sessionToken: string): Promise<void> {
    const token = sessionToken.trim();
    if (!token) return;
    try {
      const response = await fetch(deps.authSessionCookieSetUrl, {
        method: 'GET',
        credentials: 'include',
        headers: {
          Authorization: `Bearer ${token}`,
          [deps.authSessionCookieClientHeader]: '1',
        },
        cache: 'no-store',
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      console.warn('Unable to persist auth cookie.', error);
      deps.pushChatMessage('Session save failed. You may need to log in again after refresh.');
    }
  }

  async function clearHttpOnlySessionCookie(): Promise<void> {
    try {
      const response = await fetch(deps.authSessionCookieClearUrl, {
        method: 'GET',
        credentials: 'include',
        headers: {
          [deps.authSessionCookieClientHeader]: '1',
        },
        cache: 'no-store',
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      console.warn('Unable to clear auth cookie.', error);
      deps.pushChatMessage('Session clear failed. Your browser may retain an old login cookie.');
    }
  }

  async function handleAuthResult(message: Extract<IncomingMessage, { type: 'auth_result' }>): Promise<void> {
    pendingAuthRequest = false;
    applyAuthPolicy(message.authPolicy);
    if (!message.ok) {
      externalAuthAssertion = '';
      authUserId = '';
      if (message.message.toLowerCase().includes('session')) {
        resetSavedSessionHint();
        void clearHttpOnlySessionCookie();
      }
      applyAuthPermissions('user', []);
      deps.onServerAdminMenuActions([]);
      deps.setConnectionStatus(message.message);
      deps.setConnecting(false);
      updateConnectAvailability();
      deps.disconnect();
      return;
    }

    externalAuthAssertion = '';
    if (message.sessionToken) {
      void persistHttpOnlySessionCookie(message.sessionToken);
    }
    if (message.username) {
      authUsername = message.username;
      deps.saveAuthUsername(message.username);
    }
    applyAuthPermissions(message.role, message.permissions);
    deps.onServerAdminMenuActions(message.adminMenuActions);
    // The persistent connection status is already an ARIA live region, so this
    // is announced before the world view takes focus in browsers and shells.
    deps.setConnectionStatus('Sign in successful. Joining Chat Grid...');
  }

  function handleAuthPermissions(message: Extract<IncomingMessage, { type: 'auth_permissions' }>): void {
    const hadVoiceSend = voiceSendAllowed;
    applyAuthPermissions(message.role, message.permissions);
    deps.onServerAdminMenuActions(message.adminMenuActions);
    if (hadVoiceSend && !voiceSendAllowed) {
      deps.updateStatus('Voice send permission revoked.');
    }
    if (!hadVoiceSend && voiceSendAllowed) {
      deps.updateStatus('Voice send permission granted.');
    }
  }

  function applyWelcomeAuth(
    auth: WelcomeAuth,
    adminMenuActions: Array<{ id: string; label: string; tooltip?: string }> | null | undefined,
  ): void {
    authUserId = String(auth?.userId || '').trim();
    applyAuthPolicy(auth?.policy);
    applyAuthPermissions(auth?.role, auth?.permissions);
    deps.onServerAdminMenuActions(adminMenuActions);
  }

  function logOutAccount(): void {
    authUserId = '';
    authUsername = '';
    void clearHttpOnlySessionCookie();
    deps.saveAuthUsername('');
    applyAuthPermissions('user', []);
    deps.onServerAdminMenuActions([]);
    if (deps.isRunning()) {
      deps.signalingSend({ type: 'auth_logout' });
      deps.disconnect();
    }
    deps.updateStatus('Logged out.');
    updateConnectAvailability();
  }

  function setSavedSessionCookieAvailable(available: boolean): void {
    savedSessionCookieAvailable = available;
    updateConnectAvailability();
  }

  function setupUiHandlers(uiDeps: AuthUiDeps): void {
    deps.dom.logoutButton.addEventListener('click', () => {
      logOutAccount();
    });
    void uiDeps;
  }

  function initializeUi(): void {
    loadPersistedAuthPolicy();
    updateConnectAvailability();
  }

  return {
    initializeUi,
    setupUiHandlers,
    updateConnectAvailability,
    hasPermission: (key: string) => authPermissions.has(key),
    getVoiceSendAllowed: () => voiceSendAllowed,
    reapplyVoiceSendPermission: applyVoiceSendPermission,
    getAuthUserId: () => authUserId,
    sendAuthRequest,
    handleAuthRequired,
    handleAuthResult,
    handleAuthPermissions,
    setSavedSessionCookieAvailable,
    applyWelcomeAuth,
    logOutAccount,
  };
}
