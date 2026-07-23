import './styles.css';
import { AudioEngine, type LocationAmbienceProfile } from './audio/audioEngine';
import {
  EFFECT_SEQUENCE,
} from './audio/effects';
import { RadioStationRuntime } from './audio/radioStationRuntime';
import { getProxyUrlForMedia, shouldProxyExternalMediaUrl } from './audio/mediaUrl';
import { ItemEmitRuntime } from './audio/itemEmitRuntime';
import { BillboardRuntime } from './audio/billboardRuntime';
import { ClockAnnouncer } from './audio/clockAnnouncer';
import { TvScreenRuntime } from './media/tvScreenRuntime';
import { normalizeDegrees } from './audio/spatial';
import {
  applyPastedText,
  applyTextInput,
  describeBackspaceDeletedCharacter,
  describeDeleteDeletedCharacter,
  describeCursorCharacter,
  describeCursorWordOrCharacter,
  mapTextInputKey,
  moveCursorWordLeft,
  moveCursorWordRight,
  shouldReplaceCurrentText,
} from './input/textInput';
import { formatCommandMenuLabel, type CommandDescriptor, type ModeInput } from './input/commandTypes';
import { getAvailableMainModeCommands } from './input/mainModeCommands';
import { resolveMainModeCommand, type MainModeCommand } from './input/mainCommandRouter';
import { dispatchModeInput } from './input/modeDispatcher';
import { handleListControlKey } from './input/listController';
import { createAdminController, type AdminMenuAction } from './input/adminController';
import { setupKeyboardInputHandlers } from './input/keyboardController';
import { setupMidiInputHandlers, type MidiControllerHandle } from './input/midiController';
import { getEditSessionAction } from './input/editSession';
import { formatSteppedNumber, snapNumberToStep } from './input/numeric';
import { type IncomingMessage, type OutgoingMessage } from './network/protocol';
import { createOnMessageHandler } from './network/messageHandlers';
import { SignalingClient } from './network/signalingClient';
import { CanvasRenderer } from './render/canvasRenderer';
import {
  GRID_SIZE,
  HEARING_RADIUS,
  MOVE_COOLDOWN_MS,
  createInitialState,
  getDirection,
  getNearestItem,
  getNearestPeer,
  isItemQuiet,
  type GameMode,
  type PeerState,
  type WorldItem,
} from './state/gameState';
import {
  applyServerItemUiDefinitions,
  getItemManagementActionMetadata,
  getServerMainModeCommandMetadata,
  getItemTypeGlobalProperties,
  getItemTypeSequence,
  getEditableItemPropertyKeys,
  getInspectItemPropertyKeys,
  getItemPropertyOptionValues,
  getItemPropertyMetadata,
  itemPropertyLabel,
  getItemTypeTooltip,
  itemTypeLabel,
} from './items/itemRegistry';
import { formatItemInteractionHint, formatItemNarrationSummary } from './items/itemNarration';
import { createItemInteractionController } from './items/itemInteractionController';
import { createItemPropertyEditor } from './items/itemPropertyEditor';
import { createItemPropertyPresentation } from './items/itemPropertyPresentation';
import { ItemBehaviorRegistry } from './items/types/behaviorRegistry';
import { SettingsStore, type FlexPbxDialingPreferences } from './settings/settingsStore';
import { createAuthController } from './session/authController';
import { startClientUpdateWatcher, type ClientVersionMetadata } from './session/clientUpdateWatcher';
import { runConnectFlow, runDisconnectFlow, type ConnectFlowDeps } from './session/connectionFlow';
import { MediaSession } from './session/mediaSession';
import { type AnnouncementMode, type AudioAnnouncementSettings, type AudioLayerState, type RadioAnnouncementMode } from './types/audio';
import { setupUiHandlers as setupDomUiHandlers } from './ui/domBindings';
import { PeerManager } from './webrtc/peerManager';

const NICKNAME_MAX_LENGTH = 32;
const MIC_CALIBRATION_DURATION_MS = 5000;
const MIC_CALIBRATION_SAMPLE_INTERVAL_MS = 50;
const MIC_CALIBRATION_MIN_GAIN = 0.5;
const MIC_CALIBRATION_MAX_GAIN = 4;
const MIC_CALIBRATION_TARGET_RMS = 0.12;
const MIC_CALIBRATION_ACTIVE_RMS_THRESHOLD = 0.003;
const MIC_INPUT_GAIN_SCALE_MULTIPLIER = 2;
const MIC_INPUT_GAIN_STEP = 0.05;

const PENDING_EXTERNAL_AUTH_STORAGE_KEY = 'endiginousPendingExternalAuth';

/** Reads a one-time external auth assertion and keeps it across a forced reload. */
function consumeExternalAuthAssertion(): string {
  const url = new URL(window.location.href);
  const assertion = String(url.searchParams.get('external_auth') || '').trim()
    || String(sessionStorage.getItem(PENDING_EXTERNAL_AUTH_STORAGE_KEY) || '').trim();
  if (assertion) {
    sessionStorage.setItem(PENDING_EXTERNAL_AUTH_STORAGE_KEY, assertion);
    url.searchParams.delete('external_auth');
    window.history.replaceState({}, document.title, url.toString());
  }
  return assertion;
}
const HEARTBEAT_INTERVAL_MS = 10_000;
const RECONNECT_DELAY_MS = 5_000;
const RECONNECT_MAX_ATTEMPTS = 6;
const RECONNECT_PAGE_REFRESH_KEY = 'chatGridReconnectPageRefresh';
const RECONNECT_PAGE_REFRESH_MAX_AGE_MS = 5 * 60_000;
const CLIENT_UPDATE_POLL_MS = 30_000;
const AUDIO_SUBSCRIPTION_REFRESH_MS = 500;
const TELEPORT_SQUARES_PER_SECOND = 20;
const AUTH_POLICY_STORAGE_KEY = 'chgridAuthPolicy';
const MESSAGE_OUTBOX_STORAGE_KEY = 'chatGridPendingMessages';
const MESSAGE_OUTBOX_MAX_ITEMS = 25;

declare global {
  interface Window {
    CHGRID_RELEASE_VERSION?: string;
    CHGRID_CLIENT_REVISION?: string;
  }
}

type Dom = {
  gridTitle: HTMLElement;
  connectionStatus: HTMLElement;
  appVersion: HTMLElement;
  loginView: HTMLElement;
  authSessionView: HTMLElement;
  authSessionText: HTMLParagraphElement;
  helpSection: HTMLElement;
  helpToggle: HTMLButtonElement;
  updatesSection: HTMLElement;
  updatesToggle: HTMLButtonElement;
  updatesPanel: HTMLDivElement;
  connectButton: HTMLButtonElement;
  logoutButton: HTMLButtonElement;
  disconnectButton: HTMLButtonElement;
  focusGridButton: HTMLButtonElement;
  openSettingsButton: HTMLButtonElement;
  midiButton: HTMLButtonElement;
  closeSettingsButton: HTMLButtonElement;
  readGuideButton: HTMLButtonElement;
  settingsModal: HTMLDivElement;
  audioInputSelect: HTMLSelectElement;
  audioOutputSelect: HTMLSelectElement;
  announcementModeSelect: HTMLSelectElement;
  radioAnnouncementModeSelect: HTMLSelectElement;
  itemBeaconsToggle: HTMLInputElement;
  movementDirectionsToggle: HTMLInputElement;
  flexPbxOutboundDialingToggle: HTMLInputElement;
  flexPbxDialingPrefixesInput: HTMLInputElement;
  flexPbxDialingStatus: HTMLParagraphElement;
  castLocalOnlyToggle: HTMLInputElement;
  ntfyNotificationsToggle: HTMLInputElement;
  ntfyNotificationsStatus: HTMLParagraphElement;
  ntfySubscriptionLink: HTMLAnchorElement;
  rotateNtfyTopicButton: HTMLButtonElement;
  audioInputCurrent: HTMLParagraphElement;
  audioOutputCurrent: HTMLParagraphElement;
  joinGuide: HTMLElement;
  gridDashboard: HTMLElement;
  gridPosition: HTMLSpanElement;
  gridPeople: HTMLSpanElement;
  gridItems: HTMLSpanElement;
  gridHere: HTMLSpanElement;
  worldSummary: HTMLParagraphElement;
  canvas: HTMLCanvasElement;
  interactiveItemPanel: HTMLElement;
  interactiveItemTitle: HTMLHeadingElement;
  interactiveItemCloseButton: HTMLButtonElement;
  interactiveItemFrame: HTMLIFrameElement;
  status: HTMLDivElement;
  instructions: HTMLDivElement;
};

const dom: Dom = {
  gridTitle: requiredById('gridTitle'),
  connectionStatus: requiredById('connectionStatus'),
  appVersion: requiredById('appVersion'),
  loginView: requiredById('loginView'),
  authSessionView: requiredById('authSessionView'),
  authSessionText: requiredById('authSessionText'),
  helpSection: requiredById('helpSection'),
  helpToggle: requiredById('helpToggle'),
  updatesSection: requiredById('updatesSection'),
  updatesToggle: requiredById('updatesToggle'),
  updatesPanel: requiredById('updatesPanel'),
  connectButton: requiredById('connectButton'),
  logoutButton: requiredById('logoutButton'),
  disconnectButton: requiredById('disconnectButton'),
  focusGridButton: requiredById('focusGridButton'),
  openSettingsButton: requiredById('openSettingsButton'),
  midiButton: requiredById('midiButton'),
  closeSettingsButton: requiredById('closeSettingsButton'),
  readGuideButton: requiredById('readGuideButton'),
  settingsModal: requiredById('settingsModal'),
  audioInputSelect: requiredById('audioInputSelect'),
  audioOutputSelect: requiredById('audioOutputSelect'),
  announcementModeSelect: requiredById('announcementModeSelect'),
  radioAnnouncementModeSelect: requiredById('radioAnnouncementModeSelect'),
  itemBeaconsToggle: requiredById('itemBeaconsToggle'),
  movementDirectionsToggle: requiredById('movementDirectionsToggle'),
  flexPbxOutboundDialingToggle: requiredById('flexPbxOutboundDialingToggle'),
  flexPbxDialingPrefixesInput: requiredById('flexPbxDialingPrefixesInput'),
  flexPbxDialingStatus: requiredById('flexPbxDialingStatus'),
  castLocalOnlyToggle: requiredById('castLocalOnlyToggle'),
  ntfyNotificationsToggle: requiredById('ntfyNotificationsToggle'),
  ntfyNotificationsStatus: requiredById('ntfyNotificationsStatus'),
  ntfySubscriptionLink: requiredById('ntfySubscriptionLink'),
  rotateNtfyTopicButton: requiredById('rotateNtfyTopicButton'),
  audioInputCurrent: requiredById('audioInputCurrent'),
  audioOutputCurrent: requiredById('audioOutputCurrent'),
  joinGuide: requiredById('joinGuide'),
  gridDashboard: requiredById('gridDashboard'),
  gridPosition: requiredById('gridPosition'),
  gridPeople: requiredById('gridPeople'),
  gridItems: requiredById('gridItems'),
  gridHere: requiredById('gridHere'),
  worldSummary: requiredById('worldSummary'),
  canvas: requiredById('gameCanvas'),
  interactiveItemPanel: requiredById('interactiveItemPanel'),
  interactiveItemTitle: requiredById('interactiveItemTitle'),
  interactiveItemCloseButton: requiredById('interactiveItemCloseButton'),
  interactiveItemFrame: requiredById('interactiveItemFrame'),
  status: requiredById('status'),
  instructions: requiredById('instructions'),
};

type ChangelogSection = {
  date: string;
  items: string[];
};

type ChangelogData = {
  sections: ChangelogSection[];
};

type HelpItem = {
  keys: string;
  description: string;
};

type HelpSection = {
  title: string;
  items: HelpItem[];
};

type HelpData = {
  sections: HelpSection[];
};

type WorldLocationOption = {
  id: string;
  name: string;
  kind: string;
  description: string;
  spawnX: number;
  spawnY: number;
  ambienceKey?: string;
  ambienceName?: string;
};

type FootstepCue = {
  url: string;
  gain: number;
  fadeInMs: number;
  playbackRate: number;
  identity: string;
  nickname: string;
  surface: string;
};

type QueuedChatMessage = {
  id: string;
  kind: 'room' | 'direct';
  message: string;
  targetId?: string;
  targetName?: string;
  createdAt: number;
};

type FootstepSurfaceProfile = {
  label: string;
  sampleIndexes: number[];
  gain: number;
  pitchMin: number;
  pitchMax: number;
  fadeInMs?: number;
};

/** Builds linearized help-view lines from sectioned help content. */
function buildHelpLines(help: HelpData): string[] {
  const lines: string[] = [];
  for (const section of help.sections) {
    lines.push(section.title);
    for (const item of section.items) {
      lines.push(`${item.keys}: ${item.description}`);
    }
  }
  return lines;
}

/** Builds linear startup-guide lines from the visible join guide content. */
function buildJoinGuideLines(): string[] {
  const title = dom.joinGuide.querySelector('h2')?.textContent?.trim();
  const lines = Array.from(dom.joinGuide.querySelectorAll('p'))
    .map((line) => line.textContent?.replace(/\s+/g, ' ').trim() ?? '')
    .filter((line) => line.length > 0);
  return [title, ...lines].filter((line): line is string => Boolean(line && line.length > 0));
}

/** Announces the current startup-guide line through the app reader. */
function announceJoinGuideLine(): void {
  const lines = buildJoinGuideLines();
  if (lines.length === 0) {
    updateStatus('Guide unavailable.');
    audio.sfxUiCancel();
    return;
  }
  joinGuideReaderIndex = Math.max(0, Math.min(joinGuideReaderIndex, lines.length - 1));
  updateStatus(lines[joinGuideReaderIndex]);
  audio.sfxUiBlip();
}

/** Opens a focus-mode reader for startup instructions before joining the grid. */
function openJoinGuideReader(): void {
  joinGuideReaderActive = true;
  joinGuideReaderIndex = 0;
  dom.readGuideButton.textContent = 'Reading guide';
  dom.readGuideButton.setAttribute('aria-pressed', 'true');
  dom.readGuideButton.focus();
  announceJoinGuideLine();
}

/** Closes the startup guide reader and returns focus to the guide button. */
function closeJoinGuideReader(): void {
  if (!joinGuideReaderActive) return;
  dom.readGuideButton.textContent = 'Read guide';
  dom.readGuideButton.setAttribute('aria-pressed', 'false');
  dom.readGuideButton.focus();
  updateStatus('Closed guide.');
  audio.sfxUiCancel();
  joinGuideReaderActive = false;
}

/** Handles arrow-key reading for the startup guide without requiring screen-reader browse mode. */
function handleJoinGuideReaderKey(event: KeyboardEvent): void {
  if (!joinGuideReaderActive) return;
  const lines = buildJoinGuideLines();
  if (lines.length === 0) {
    closeJoinGuideReader();
    return;
  }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Escape', 'Enter', ' '].includes(event.key)) return;
  event.preventDefault();
  if (event.key === 'ArrowDown') {
    joinGuideReaderIndex = Math.min(lines.length - 1, joinGuideReaderIndex + 1);
    announceJoinGuideLine();
    return;
  }
  if (event.key === 'ArrowUp') {
    joinGuideReaderIndex = Math.max(0, joinGuideReaderIndex - 1);
    announceJoinGuideLine();
    return;
  }
  if (event.key === 'Home') {
    joinGuideReaderIndex = 0;
    announceJoinGuideLine();
    return;
  }
  if (event.key === 'End') {
    joinGuideReaderIndex = lines.length - 1;
    announceJoinGuideLine();
    return;
  }
  if (event.key === 'Enter' || event.key === ' ') {
    announceJoinGuideLine();
    return;
  }
  closeJoinGuideReader();
}

/** Announces standardized menu entry as `Title. First option.` */
function announceMenuEntry(title: string, firstOption: string): void {
  const trimmedTitle = title.trim();
  const trimmedOption = firstOption.trim();
  const titleSuffix = /[.!?]$/.test(trimmedTitle) ? '' : '.';
  const optionSuffix = /[.!?]$/.test(trimmedOption) ? '' : '.';
  updateStatus(`${trimmedTitle}${titleSuffix} ${trimmedOption}${optionSuffix}`);
  audio.sfxUiBlip();
}

const APP_RELEASE_VERSION = String(window.CHGRID_RELEASE_VERSION ?? '').trim();
const APP_CLIENT_REVISION = String(window.CHGRID_CLIENT_REVISION ?? '').trim();
const APP_DISPLAY_VERSION = [APP_RELEASE_VERSION, APP_CLIENT_REVISION].filter((value) => value.length > 0).join(' ').trim();
const STARTED_FROM_VERSION_RELOAD = isVersionReloadedSession();
const IS_NATIVE_CLIENT = new URLSearchParams(window.location.search).has('native_client');
document.documentElement.classList.toggle('chatgrid-native', IS_NATIVE_CLIENT);
dom.appVersion.textContent = APP_DISPLAY_VERSION
  ? `${IS_NATIVE_CLIENT ? 'Endiginous desktop client' : 'Another AI experiment with Jage'}. Version ${APP_DISPLAY_VERSION}`
  : `${IS_NATIVE_CLIENT ? 'Endiginous desktop client' : 'Another AI experiment with Jage'}. Version unknown`;
const DEFAULT_GRID_NAME = 'Endiginous';
const DEFAULT_WELCOME_MESSAGE =
  IS_NATIVE_CLIENT
    ? 'Welcome to Endiginous, your immersive audio playground. Use the File menu for sign-in, settings, updates, and desktop settings.'
    : 'Welcome to Endiginous, your immersive audio playground. Configure your audio, then sign in with blind.software to join the grid.';
const APP_BASE_URL = import.meta.env.BASE_URL || '/';
/** Resolves an app-relative path against the configured Vite base path. */
function withBase(path: string): string {
  const normalizedBase = APP_BASE_URL.endsWith('/') ? APP_BASE_URL : `${APP_BASE_URL}/`;
  return `${normalizedBase}${path.replace(/^\/+/, '')}`;
}
/** Announces a newer client bundle and navigates through a cache-busted URL. */
function scheduleClientUpdateReload(metadata: ClientVersionMetadata): void {
  if (reloadScheduledForVersionMismatch) return;
  // An external-auth assertion is valid only for this sign-in attempt. Keep
  // the current session alive long enough for auth_result to clear it instead
  // of reloading halfway through the callback flow.
  if (initialExternalAuthAssertion || sessionStorage.getItem(PENDING_EXTERNAL_AUTH_STORAGE_KEY)) {
    setConnectionStatus('Sign-in is still completing. Update will wait.');
    return;
  }
  reloadScheduledForVersionMismatch = true;
  const label = [metadata.releaseVersion, metadata.clientRevision].filter((value) => value.length > 0).join(' ');
  const message = label
    ? `New Endiginous ${IS_NATIVE_CLIENT ? 'world runtime' : 'update'} ${label} found. Reloading...`
    : `New Endiginous ${IS_NATIVE_CLIENT ? 'world runtime update' : 'update'} found. Reloading...`;
  setConnectionStatus(message);
  pushChatMessage(message);
  window.setTimeout(
    () => {
      reloadClientForVersion(metadata.clientRevision || 'latest');
    },
    document.visibilityState === 'visible' ? 1_500 : 50,
  );
}
const SYSTEM_SOUND_URLS = {
  logon: withBase('sounds/logon.ogg'),
  logout: withBase('sounds/logout.ogg'),
  notify: withBase('sounds/notify.ogg'),
} as const;
const AUTH_SESSION_COOKIE_SET_URL = withBase('auth/session/set');
const AUTH_SESSION_COOKIE_CLEAR_URL = withBase('auth/session/clear');
const AUTH_SESSION_COOKIE_CHECK_URL = withBase('auth/session/check');
const AUTH_SESSION_COOKIE_CLIENT_HEADER = 'X-Chgrid-Auth-Client';
const ACTION_SOUND_URL = withBase('sounds/action.ogg');
const FOOTSTEP_SOUND_URLS = Array.from({ length: 11 }, (_, index) => withBase(`sounds/step-${index + 1}.ogg`));
const FOOTSTEP_GAIN = 0.7;
const LOCATION_AMBIENCE_PROFILES: Record<string, Omit<LocationAmbienceProfile, 'key' | 'name'>> = {
  city_plaza: { loopUrl: withBase('sounds/ambience/city_plaza.ogg'), loopGain: 0.5, rootHz: 110, colorHz: 165, airHz: 330, noiseHz: 950, noiseQ: 0.8, gain: 0.06, noiseGain: 0.018, wave: 'sine' },
  forest_canopy: { loopUrl: withBase('sounds/ambience/forest_canopy.ogg'), loopGain: 0.45, rootHz: 82, colorHz: 123, airHz: 246, noiseHz: 1450, noiseQ: 1.2, gain: 0.055, noiseGain: 0.032, wave: 'triangle' },
  town_square: { loopUrl: withBase('sounds/ambience/town_square.ogg'), loopGain: 0.48, rootHz: 98, colorHz: 147, airHz: 294, noiseHz: 720, noiseQ: 0.7, gain: 0.052, noiseGain: 0.018, wave: 'sine' },
  town_cafe: { loopUrl: withBase('sounds/ambience/town_cafe.ogg?v=20260715-world-cup-cafe'), loopGain: 0.38, rootHz: 92, colorHz: 184, airHz: 368, noiseHz: 1050, noiseQ: 1.1, gain: 0.044, noiseGain: 0.022, wave: 'triangle' },
  arcade_glow: { loopUrl: withBase('sounds/ambience/arcade_glow.ogg?v=20260714-arcade-loop'), loopGain: 0.5, rootHz: 130.81, colorHz: 196, airHz: 392, noiseHz: 1800, noiseQ: 2.4, gain: 0.052, noiseGain: 0.012, wave: 'square' },
  office_focus: { loopUrl: withBase('sounds/ambience/office_focus.ogg'), loopGain: 0.42, rootHz: 73.42, colorHz: 146.83, airHz: 293.66, noiseHz: 560, noiseQ: 0.9, gain: 0.047, noiseGain: 0.014, wave: 'sine' },
  neighborhood_evening: { loopUrl: withBase('sounds/ambience/neighborhood_evening.ogg'), loopGain: 0.48, rootHz: 87.31, colorHz: 130.81, airHz: 261.63, noiseHz: 820, noiseQ: 0.9, gain: 0.049, noiseGain: 0.02, wave: 'triangle' },
  front_entry: { loopUrl: withBase('sounds/ambience/front_entry.ogg'), loopGain: 0.42, rootHz: 92.5, colorHz: 185, airHz: 277.18, noiseHz: 650, noiseQ: 1, gain: 0.045, noiseGain: 0.014, wave: 'sine' },
  living_room_warmth: { loopUrl: withBase('sounds/ambience/living_room_warmth.ogg'), loopGain: 0.5, rootHz: 65.41, colorHz: 130.81, airHz: 196, noiseHz: 500, noiseQ: 0.8, gain: 0.05, noiseGain: 0.012, wave: 'triangle' },
  studio_current: { loopUrl: withBase('sounds/ambience/studio_current.ogg'), loopGain: 0.42, rootHz: 55, colorHz: 110, airHz: 220, noiseHz: 1250, noiseQ: 1.6, gain: 0.052, noiseGain: 0.018, wave: 'sawtooth' },
  kitchen_soft_clatter: { loopUrl: withBase('sounds/ambience/kitchen_soft_clatter.ogg'), loopGain: 0.35, rootHz: 104, colorHz: 156, airHz: 312, noiseHz: 980, noiseQ: 1.3, gain: 0.048, noiseGain: 0.019, wave: 'triangle' },
  bedroom_quiet: { loopUrl: withBase('sounds/ambience/bedroom_quiet.ogg'), loopGain: 0.55, rootHz: 61.74, colorHz: 123.47, airHz: 185, noiseHz: 420, noiseQ: 0.7, gain: 0.038, noiseGain: 0.01, wave: 'sine' },
  relaxation_ocean: { loopUrl: withBase('sounds/ambience/relaxation_bowls.ogg?v=20260714-singing-bowls'), loopGain: 0.52, rootHz: 74, colorHz: 148, airHz: 222, noiseHz: 360, noiseQ: 0.65, gain: 0.042, noiseGain: 0.026, wave: 'sine' },
};
const STREAM_LOCATION_AMBIENCE_BASE: Omit<LocationAmbienceProfile, 'key' | 'name' | 'loopUrl' | 'loopGain'> = {
  rootHz: 96,
  colorHz: 144,
  airHz: 288,
  noiseHz: 820,
  noiseQ: 0.9,
  gain: 0.048,
  noiseGain: 0.018,
  wave: 'sine',
};
const DEFAULT_FOOTSTEP_PROFILE: FootstepSurfaceProfile = {
  label: 'pavement',
  sampleIndexes: [1, 2, 3, 4, 6],
  gain: FOOTSTEP_GAIN,
  pitchMin: 0.95,
  pitchMax: 1.06,
};
const TELEPORT_START_SOUND_URL = withBase('sounds/teleport_start.ogg');
const TELEPORT_START_GAIN = 0.1;
const TELEPORT_SOUND_URL = withBase('sounds/teleport.ogg');
const DOOR_CLOSE_SOUND_URL = withBase('sounds/doors/door-close.mp3?v=20260714-real-door');
const WALL_SOUND_URL = withBase('sounds/wall.ogg');
const MOVEMENT_NARRATION_INTERVAL_MS = 650;
const RUN_MOVEMENT_TICK_MULTIPLIER = 0.55;
const CAREFUL_MOVEMENT_TICK_MULTIPLIER = 1.25;
const ITEM_BEACON_RADIUS = 3.5;
const ITEM_BEACON_INTERVAL_MS = 3200;
const RUNTIME_RECOVERY_STATUS_INTERVAL_MS = 5_000;
const SEAT_INTERACTION_RADIUS = 1.5;

const state = createInitialState();
const renderer = new CanvasRenderer(dom.canvas);
const audio = new AudioEngine();
const settings = new SettingsStore();
const initialAuthUsername = settings.loadAuthUsername();
let worldGridSize = GRID_SIZE;
let worldGridWidth = GRID_SIZE;
let worldGridHeight = GRID_SIZE;
let movementTickMs = MOVE_COOLDOWN_MS;
let lastWallCollisionDirection: string | null = null;
let statusTimeout: number | null = null;
let pendingDoorCloseCue: { x: number; y: number; expiresAt: number } | null = null;
let lastFocusedElement: Element | null = null;
let lastAnnouncementText = '';
let lastAnnouncementAt = 0;
let lastRuntimeRecoveryStatusAt = 0;
let lastMovementNarrationAt = 0;
let lastMovementNarrationDirection = '';
let outputMode = settings.loadOutputMode();
let activeGridName = DEFAULT_GRID_NAME;
let activeWelcomeMessage = DEFAULT_WELCOME_MESSAGE;
let currentLocationId = '';
let currentLocationName = '';
let worldLocationOptions: WorldLocationOption[] = [];
const messageBuffer: string[] = [];
let messageCursor = -1;
type ConversationBuffer = { peerId: string; peerName: string; messages: string[]; cursor: number };
const publicMessageBuffer: string[] = [];
const systemMessageBuffer: string[] = [];
const directConversationBuffers = new Map<string, ConversationBuffer>();
let publicMessageCursor = -1;
let systemMessageCursor = -1;
let focusedConversationPeerId: string | null = null;
let focusedConversationPeerName: string | null = null;

function conversationKey(peerName: string): string {
  return peerName.trim().toLocaleLowerCase();
}

/** Appends a bounded message without pulling an active history reader away. */
function appendMessageKeepingCursor(buffer: string[], cursor: number, message: string): number {
  const wasAtLatest = cursor < 0 || cursor >= buffer.length - 1;
  buffer.push(message);
  const removedOldest = buffer.length > 300;
  if (removedOldest) buffer.shift();
  if (wasAtLatest) return buffer.length - 1;
  return removedOldest ? Math.max(0, cursor - 1) : cursor;
}

const radioRuntime = new RadioStationRuntime(audio, getItemSpatialConfig, {
  onStationFailure: (itemId) => {
    updateStatus('Scanning stations.');
    signaling.send({ type: 'item_secondary_use', itemId });
  },
});
const tvScreenRuntime = new TvScreenRuntime();
const itemEmitRuntime = new ItemEmitRuntime(audio, resolveIncomingSoundUrl, getItemSpatialConfig);
const billboardRuntime = new BillboardRuntime(audio, getItemSpatialConfig, (message) => {
  pushChatMessage(message);
}, (message) => {
  pushChatMessage(message, false);
}, shouldSpeakItemAnnouncement);
const clockAnnouncer = new ClockAnnouncer(audio, () => getListenerPosition());
const initialExternalAuthAssertion = consumeExternalAuthAssertion();
let replaceTextOnNextType = false;
let pendingAlarmItemId: string | null = null;
let pendingEscapeDisconnect = false;
let micGainLoopbackRestoreState: boolean | null = null;
let mainHelpViewerLines: string[] = [];
let helpViewerLines: string[] = [];
let helpViewerIndex = 0;
let helpViewerReturnMode: GameMode = 'normal';
let joinGuideReaderActive = false;
let joinGuideReaderIndex = 0;
const commandPaletteCommands: Array<CommandDescriptor & { run: () => void | Promise<void> }> = [];
let commandPaletteIndex = 0;
let commandPaletteReturnMode: GameMode = 'normal';
type UserActionId =
  | 'hug'
  | 'cuddle'
  | 'kiss'
  | 'announce_focus'
  | 'tap_shoulder'
  | 'wave'
  | 'high_five'
  | 'fist_bump'
  | 'handshake'
  | 'hold_hands'
  | 'cheer'
  | 'clap'
  | 'laugh'
  | 'smile'
  | 'wink'
  | 'nod'
  | 'shake_head'
  | 'bow'
  | 'dance'
  | 'spin'
  | 'jump'
  | 'shrug'
  | 'facepalm'
  | 'gasp'
  | 'sigh'
  | 'blush'
  | 'cry'
  | 'yawn'
  | 'apologize'
  | 'forgive'
  | 'comfort'
  | 'pat_back'
  | 'poke'
  | 'boop'
  | 'salute'
  | 'point'
  | 'thumbs_up'
  | 'heart'
  | 'sparkle'
  | 'celebrate'
  | 'tease'
  | 'playful_smack'
  | 'whisper'
  | 'listen'
  | 'sit_with'
  | 'step_back'
  | 'take_left_hand'
  | 'take_right_hand'
  | 'release_hand'
  | 'walk_to'
  | 'teleport_to'
  | 'direct_message';
type UserActionOption = {
  id: UserActionId;
  label: string;
  tooltip: string;
};
const USER_ACTION_OPTIONS: UserActionOption[] = [
  {
    id: 'hug',
    label: 'Hug',
    tooltip: 'Give this user a spatial hug reaction.',
  },
  { id: 'cuddle', label: 'Cuddle', tooltip: 'Cuddle close with this user.' },
  { id: 'kiss', label: 'Kiss', tooltip: 'Give this user an affectionate kiss.' },
  {
    id: 'announce_focus',
    label: 'Announce focus',
    tooltip: 'Tell the room who you are focusing without touching or moving anyone.',
  },
  {
    id: 'tap_shoulder',
    label: 'Tap shoulder',
    tooltip: 'Gently get this user attention with a spatial tap cue.',
  },
  { id: 'wave', label: 'Wave', tooltip: 'Wave hello to this user.' },
  { id: 'high_five', label: 'High-five', tooltip: 'Give this user a quick high-five.' },
  { id: 'fist_bump', label: 'Fist bump', tooltip: 'Give this user a small fist bump.' },
  { id: 'handshake', label: 'Handshake', tooltip: 'Offer this user a friendly handshake.' },
  { id: 'hold_hands', label: 'Hold hands', tooltip: 'Offer to hold this user’s hand.' },
  { id: 'cheer', label: 'Cheer', tooltip: 'Cheer this user on.' },
  { id: 'clap', label: 'Clap', tooltip: 'Applaud this user.' },
  { id: 'laugh', label: 'Laugh', tooltip: 'Laugh with this user.' },
  { id: 'smile', label: 'Smile', tooltip: 'Smile at this user.' },
  { id: 'wink', label: 'Wink', tooltip: 'Give this user a playful wink.' },
  { id: 'nod', label: 'Nod', tooltip: 'Nod to this user.' },
  { id: 'shake_head', label: 'Shake head', tooltip: 'React with a head shake.' },
  { id: 'bow', label: 'Bow', tooltip: 'Bow politely to this user.' },
  { id: 'dance', label: 'Dance', tooltip: 'Dance near this user.' },
  { id: 'spin', label: 'Spin', tooltip: 'Spin around near this user.' },
  { id: 'jump', label: 'Jump', tooltip: 'Jump excitedly near this user.' },
  { id: 'shrug', label: 'Shrug', tooltip: 'Shrug near this user.' },
  { id: 'facepalm', label: 'Facepalm', tooltip: 'React with a facepalm.' },
  { id: 'gasp', label: 'Gasp', tooltip: 'React with surprise.' },
  { id: 'sigh', label: 'Sigh', tooltip: 'Let out a small sigh.' },
  { id: 'blush', label: 'Blush', tooltip: 'React with a shy blush.' },
  { id: 'cry', label: 'Cry', tooltip: 'React with tears or let someone comfort you.' },
  { id: 'yawn', label: 'Yawn', tooltip: 'React with a sleepy yawn.' },
  { id: 'apologize', label: 'Apologize', tooltip: 'Offer this user a sincere apology.' },
  { id: 'forgive', label: 'Forgive', tooltip: 'Offer this user forgiveness.' },
  { id: 'comfort', label: 'Comfort', tooltip: 'Offer quiet comfort.' },
  { id: 'pat_back', label: 'Pat back', tooltip: 'Pat this user on the back.' },
  { id: 'poke', label: 'Poke', tooltip: 'Poke this user playfully.' },
  { id: 'boop', label: 'Boop', tooltip: 'Boop this user playfully.' },
  { id: 'salute', label: 'Salute', tooltip: 'Salute this user.' },
  { id: 'point', label: 'Point', tooltip: 'Point toward this user.' },
  { id: 'thumbs_up', label: 'Thumbs-up', tooltip: 'Give this user a thumbs-up.' },
  { id: 'heart', label: 'Heart', tooltip: 'Send this user a heart.' },
  { id: 'sparkle', label: 'Sparkle', tooltip: 'Sparkle at this user.' },
  { id: 'celebrate', label: 'Celebrate', tooltip: 'Celebrate with this user.' },
  { id: 'tease', label: 'Tease', tooltip: 'Tease this user playfully.' },
  { id: 'playful_smack', label: 'Playful smack', tooltip: 'A light physical-comedy reaction.' },
  { id: 'whisper', label: 'Whisper', tooltip: 'Lean in like you are whispering.' },
  { id: 'listen', label: 'Listen', tooltip: 'Show that you are listening closely.' },
  { id: 'sit_with', label: 'Sit with', tooltip: 'Sit with this user.' },
  { id: 'step_back', label: 'Step back', tooltip: 'Give this user some space.' },
  {
    id: 'take_left_hand',
    label: 'Offer left hand',
    tooltip: 'Offer your left hand. The other user keeps choice and may release or follow.',
  },
  {
    id: 'take_right_hand',
    label: 'Offer right hand',
    tooltip: 'Offer your right hand. The other user keeps choice and may release or follow.',
  },
  {
    id: 'release_hand',
    label: 'Release hand',
    tooltip: 'Release the hand connection or decline being led.',
  },
  {
    id: 'walk_to',
    label: 'Walk to user',
    tooltip: 'Move to a nearby square beside this user.',
  },
  {
    id: 'teleport_to',
    label: 'Teleport to user',
    tooltip: 'Move directly onto this user square.',
  },
  {
    id: 'direct_message',
    label: 'Direct message',
    tooltip: 'Start a private message to this user.',
  },
];
const DYNAMIC_USER_ACTION_IDS: UserActionId[] = [
  'cuddle',
  'kiss',
  'announce_focus',
  'tap_shoulder',
  'wave',
  'high_five',
  'fist_bump',
  'handshake',
  'hold_hands',
  'cheer',
  'clap',
  'laugh',
  'smile',
  'wink',
  'nod',
  'bow',
  'dance',
  'shrug',
  'gasp',
  'blush',
  'cry',
  'yawn',
  'apologize',
  'forgive',
  'comfort',
  'pat_back',
  'poke',
  'boop',
  'salute',
  'thumbs_up',
  'heart',
  'sparkle',
  'celebrate',
  'tease',
  'playful_smack',
  'listen',
  'sit_with',
  'step_back',
];
let userActionMenuIndex = 0;
let userActionTargetId: string | null = null;
let heartbeatTimerId: number | null = null;
let heartbeatNextPingId = -1;
let heartbeatAwaitingPong = false;
let reconnectInFlight = false;
let autoReconnectEnabled = false;
let activeServerInstanceId: string | null = null;
let reloadScheduledForVersionMismatch = false;
let peerNegotiationReady = false;
let pendingSignalMessages: Array<Extract<IncomingMessage, { type: 'signal' }>> = [];
let peerListenGainByNickname = settings.loadPeerListenGains();
let audioLayers: AudioLayerState = {
  voice: true,
  item: true,
  media: true,
  world: true,
};
let audioAnnouncementSettings: AudioAnnouncementSettings = settings.loadAudioAnnouncementSettings();
let flexPbxDialingPreferences: FlexPbxDialingPreferences = settings.loadFlexPbxDialingPreferences();
let flexPbxServerState: {
  verified: boolean;
  outboundAllowed: boolean;
  message: string;
} | null = null;
let lastItemBeaconTile = '';
let lastItemBeaconItemId = '';
let lastItemBeaconAtMs = 0;
let lastAutoSeatItemId = '';
let lastSubscriptionRefreshAt = 0;
let lastSubscriptionRefreshTileX = Math.round(state.player.x);
let lastSubscriptionRefreshTileY = Math.round(state.player.y);
let subscriptionRefreshInFlight = false;
let subscriptionRefreshPending = false;
let suppressItemPropertyEchoUntilMs = 0;
let activeTeleportLoopStop: (() => void) | null = null;
let activeTeleportLoopToken = 0;
let activeTeleport:
  | {
      startX: number;
      startY: number;
      targetX: number;
      targetY: number;
      startedAtMs: number;
      durationMs: number;
      lastSyncAtMs: number;
      lastSentX: number;
      lastSentY: number;
      completionStatus: string;
    }
  | null = null;

const signalingProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const signalingUrl = `${signalingProtocol}://${window.location.host}${withBase('ws')}`;
const signaling = new SignalingClient(signalingUrl, handleSignalingStatus);

const peerManager = new PeerManager(
  audio,
  (targetId, payload) => {
    signaling.send({ type: 'signal', targetId, ...payload });
  },
  () => mediaSession.getOutboundStream(),
  updateStatus,
  () => activeCastStream,
  handleRemoteCastStream,
);
const mediaSession = new MediaSession({
  state,
  audio,
  peerManager,
  settings,
  dom,
  updateStatus,
  micCalibrationDurationMs: MIC_CALIBRATION_DURATION_MS,
  micCalibrationSampleIntervalMs: MIC_CALIBRATION_SAMPLE_INTERVAL_MS,
  micCalibrationMinGain: MIC_CALIBRATION_MIN_GAIN,
  micCalibrationMaxGain: MIC_CALIBRATION_MAX_GAIN,
  micCalibrationTargetRms: MIC_CALIBRATION_TARGET_RMS,
  micCalibrationActiveRmsThreshold: MIC_CALIBRATION_ACTIVE_RMS_THRESHOLD,
  micInputGainScaleMultiplier: MIC_INPUT_GAIN_SCALE_MULTIPLIER,
  micInputGainStep: MIC_INPUT_GAIN_STEP,
  hostLabel: IS_NATIVE_CLIENT ? 'desktop client' : 'browser',
});

let midiControllerHandle: MidiControllerHandle = {
  requestEnable: async () => false,
  setControlVisible: () => undefined,
};

const itemBehaviorRegistry = new ItemBehaviorRegistry({
  state,
  audio,
  signalingSend: (message) => signaling.send(message),
  updateStatus,
  openHelpViewer: (lines, returnMode) => openHelpViewer(lines, returnMode),
  requestMidiAccess: (reason) => midiControllerHandle.requestEnable(reason),
  setMidiControlVisible: (visible) => midiControllerHandle.setControlVisible(visible),
  withBase,
});

audio.setOutputMode(outputMode);

loadEffectLevels();
loadAudioLayerState();
loadMicInputGain();
loadMasterVolume();
void loadHelp();
void itemBehaviorRegistry.initialize();
void loadChangelog();
void loadClientBranding();
startClientUpdateWatcher({
  currentRevision: APP_CLIENT_REVISION,
  currentEntrypointUrl: import.meta.url,
  versionUrl: withBase('version.js'),
  indexUrl: withBase(''),
  pollMs: CLIENT_UPDATE_POLL_MS,
  onUpdateAvailable: scheduleClientUpdateReload,
});

function applyGridBranding(gridName: string | null | undefined, welcomeMessage: string | null | undefined): void {
  const nextGridName = String(gridName ?? '').trim() || DEFAULT_GRID_NAME;
  const nextWelcomeMessage = String(welcomeMessage ?? '').trim() || DEFAULT_WELCOME_MESSAGE;
  activeGridName = nextGridName;
  activeWelcomeMessage = nextWelcomeMessage;
  document.title = nextGridName;
  dom.gridTitle.textContent = nextGridName;
  dom.focusGridButton.textContent = nextGridName;
  dom.canvas.setAttribute('aria-label', `${nextGridName}, press question mark for help.`);
}

/** Stores server-advertised world locations for keyboard navigation. */
function setWorldLocations(locations: WorldLocationOption[], selectedLocationId?: string): void {
  worldLocationOptions = locations.filter((location) => location.id.trim().length > 0 && location.name.trim().length > 0);
  if (selectedLocationId) {
    const current = worldLocationOptions.find((location) => location.id === selectedLocationId);
    currentLocationId = selectedLocationId;
    currentLocationName = current?.name ?? selectedLocationId;
  }
  preloadLocationAmbienceSounds();
  void syncLocationAmbience();
}

/** Stores the current server location label for local travel menus. */
function setCurrentLocation(locationId: string, locationName: string): void {
  currentLocationId = locationId;
  currentLocationName = locationName;
  void syncLocationAmbience();
}

function profileForLocationAmbience(location: WorldLocationOption | undefined): LocationAmbienceProfile | null {
  if (!location) return null;
  const locationAmbienceItem = Array.from(state.items.values())
    .filter((item) => {
      if (item.type !== 'widget') return false;
      if (item.locationId !== location.id) return false;
      if (item.carrierId) return false;
      if (item.params.enabled === false) return false;
      if (String(item.params.ambienceScope ?? '').trim().toLowerCase() !== 'location') return false;
      const emitSound = String(item.params.emitSound ?? item.emitSound ?? '').trim();
      return resolveIncomingSoundUrl(emitSound).length > 0;
    })
    .sort((a, b) => {
      const priorityA = Number(a.params.ambiencePriority ?? 50);
      const priorityB = Number(b.params.ambiencePriority ?? 50);
      const normalizedA = Number.isFinite(priorityA) ? priorityA : 50;
      const normalizedB = Number.isFinite(priorityB) ? priorityB : 50;
      return normalizedB - normalizedA || a.title.localeCompare(b.title) || a.id.localeCompare(b.id);
    })[0];
  if (locationAmbienceItem) {
    const emitSound = String(locationAmbienceItem.params.emitSound ?? locationAmbienceItem.emitSound ?? '').trim();
    const ambienceName = String(locationAmbienceItem.params.ambienceName ?? '').trim() || locationAmbienceItem.title;
    const volumeRaw = Number(locationAmbienceItem.params.emitVolume ?? 100);
    const volume = Number.isFinite(volumeRaw) ? Math.max(0, Math.min(100, volumeRaw)) : 100;
    return {
      ...STREAM_LOCATION_AMBIENCE_BASE,
      key: `item:${locationAmbienceItem.id}:${emitSound}:${volume}`,
      name: ambienceName,
      loopUrl: resolveIncomingSoundUrl(emitSound),
      // Location ambience should remain a real room bed, not disappear when a
      // nearby radio is turned down.  The listener's master volume still
      // controls the final level; this is only the per-layer mix.
      loopGain: 0.42 * (volume / 100),
      loopStartSeconds: Number(locationAmbienceItem.params.ambienceLoopStartSeconds ?? 0),
      loopEndSeconds: Number(locationAmbienceItem.params.ambienceLoopEndSeconds ?? 0) || undefined,
    };
  }
  const ambienceKey = location.ambienceKey || location.kind || location.id;
  const profileKey = ambienceKey.trim() || location.id;
  const name = location.ambienceName?.trim() || location.name;
  const profile = LOCATION_AMBIENCE_PROFILES[profileKey] ?? LOCATION_AMBIENCE_PROFILES[location.kind] ?? LOCATION_AMBIENCE_PROFILES.city_plaza;
  return { key: profileKey, name, ...profile };
}

function preloadLocationAmbienceSounds(): void {
  audio.preloadSamples(Object.values(LOCATION_AMBIENCE_PROFILES).map((profile) => profile.loopUrl));
  audio.preloadSamples([
    TELEPORT_START_SOUND_URL,
    TELEPORT_SOUND_URL,
    withBase('sounds/teleport_departure_whoosh.ogg'),
    withBase('sounds/teleport_arrival_chime.ogg'),
    withBase('sounds/teleport_pad_loop.ogg'),
    withBase('sounds/portal_spatial_loop.ogg'),
  ]);
}

function locationOptionForId(locationId?: string | null): WorldLocationOption | undefined {
  const normalized = String(locationId || '').trim();
  if (!normalized) return undefined;
  return worldLocationOptions.find((entry) => entry.id === normalized);
}

function currentLocationOption(): WorldLocationOption | undefined {
  return locationOptionForId(currentLocationId);
}

/** Resolves a location name from a peer or item location id. */
function locationNameForId(locationId?: string | null): string {
  const normalized = String(locationId || '').trim();
  if (!normalized) return currentLocationName || currentLocationOption()?.name || 'the grid';
  return worldLocationOptions.find((entry) => entry.id === normalized)?.name || normalized;
}

function profileForLocationFootsteps(location: WorldLocationOption | undefined): FootstepSurfaceProfile {
  const surfaceKey = (location?.ambienceKey || location?.kind || location?.id || '').trim();
  const profiles: Record<string, FootstepSurfaceProfile> = {
    city_plaza: { label: 'pavement', sampleIndexes: [1, 2, 3, 4, 6], gain: 0.72, pitchMin: 0.96, pitchMax: 1.06 },
    forest_canopy: { label: 'gravel and leaves', sampleIndexes: [7, 8, 9, 10, 11], gain: 0.84, pitchMin: 1.02, pitchMax: 1.18 },
    town_square: { label: 'gravel path', sampleIndexes: [4, 6, 7, 8, 10], gain: 0.8, pitchMin: 0.98, pitchMax: 1.12 },
    arcade_glow: { label: 'rubber arcade floor', sampleIndexes: [3, 5, 6, 9], gain: 0.66, pitchMin: 0.88, pitchMax: 1 },
    office_focus: { label: 'office carpet', sampleIndexes: [1, 2, 5], gain: 0.5, pitchMin: 0.8, pitchMax: 0.92, fadeInMs: 18 },
    neighborhood_evening: { label: 'sidewalk and porch gravel', sampleIndexes: [2, 4, 7, 8], gain: 0.75, pitchMin: 0.94, pitchMax: 1.08 },
    front_entry: { label: 'wood entry', sampleIndexes: [3, 4, 6], gain: 0.64, pitchMin: 0.94, pitchMax: 1.04 },
    living_room_warmth: { label: 'living room rug', sampleIndexes: [1, 2, 3], gain: 0.52, pitchMin: 0.8, pitchMax: 0.93, fadeInMs: 18 },
    studio_current: { label: 'studio floor', sampleIndexes: [5, 6, 9, 11], gain: 0.62, pitchMin: 0.9, pitchMax: 1.05 },
    kitchen_soft_clatter: { label: 'kitchen tile', sampleIndexes: [4, 5, 6, 9], gain: 0.74, pitchMin: 1.04, pitchMax: 1.18 },
    bedroom_quiet: { label: 'bedroom carpet', sampleIndexes: [1, 2], gain: 0.42, pitchMin: 0.76, pitchMax: 0.86, fadeInMs: 24 },
    relaxation_ocean: { label: 'soft relaxation room carpet', sampleIndexes: [1, 2], gain: 0.38, pitchMin: 0.72, pitchMax: 0.84, fadeInMs: 26 },
  };
  return profiles[surfaceKey] ?? profiles[location?.kind ?? ''] ?? DEFAULT_FOOTSTEP_PROFILE;
}

async function syncLocationAmbience(forceRestart = false): Promise<void> {
  const location = currentLocationOption();
  await audio.setLocationAmbience(profileForLocationAmbience(location), audioLayers.world, forceRestart);
}

/** Re-primes world audio when a browser/tab/audio-context pause has recovered. */
function resumeWorldAudioAfterFocus(forceRestart = true): void {
  if (!state.running) return;
  void audio.ensureContext().then(async () => {
    // Reattach remote voice after browser sleep, tab restore, or a delayed
    // microphone permission grant. Room ambience alone is not proof that the
    // live voice graph has resumed.
    await peerManager.resumeRemoteAudio();
    await syncLocationAmbience(forceRestart);
  }).catch(() => undefined);
}

window.addEventListener('focus', resumeWorldAudioAfterFocus);
window.addEventListener('pageshow', resumeWorldAudioAfterFocus);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') resumeWorldAudioAfterFocus();
});
document.addEventListener('pointerdown', () => resumeWorldAudioAfterFocus(false), { passive: true });

async function loadClientBranding(): Promise<void> {
  try {
    const response = await fetch(withBase('client_branding.json'), { cache: 'no-store' });
    if (!response.ok) {
      return;
    }
    const data = (await response.json()) as { gridName?: unknown; welcomeMessage?: unknown };
    applyGridBranding(
      typeof data.gridName === 'string' ? data.gridName : null,
      typeof data.welcomeMessage === 'string' ? data.welcomeMessage : null,
    );
    if (!state.running && !STARTED_FROM_VERSION_RELOAD) {
      setConnectionStatus(activeWelcomeMessage);
    }
  } catch {
    // Branding falls back to built-in defaults when deploy-time branding is unavailable.
  }
}

/** Fetches a required DOM element and casts it to the requested element type. */
function requiredById<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) {
    throw new Error(`Missing element: ${id}`);
  }
  return found as T;
}

const itemPropertyPresentation = createItemPropertyPresentation();
const getItemPropertyValue = itemPropertyPresentation.getItemPropertyValue;
const isItemPropertyEditable = itemPropertyPresentation.isItemPropertyEditable;
const describeItemPropertyHelp = itemPropertyPresentation.describeItemPropertyHelp;
const validateNumericItemPropertyInput = itemPropertyPresentation.validateNumericItemPropertyInput;

type ItemPropertyOptionSet = {
  values: string[];
  labels: string[];
};

function radioSpeakerRoleLabel(value: unknown): string {
  const role = String(value ?? 'primary').trim().toLowerCase();
  if (role === 'sub') return 'sub';
  if (role === 'low') return 'low';
  if (role === 'mid') return 'mid';
  if (role === 'high') return 'high';
  if (role === 'high_low_bass') return 'high/low';
  return 'primary';
}

function radioPlaybackLabel(item: WorldItem): string {
  const station = String(item.params.stationName ?? '').trim();
  const nowPlaying = String(item.params.nowPlaying ?? '').trim();
  if (nowPlaying && station) return `${station}, ${nowPlaying}`;
  if (station) return station;
  if (nowPlaying) return nowPlaying;
  return item.params.enabled === false ? 'off' : 'playing nearby';
}

function radioLinkedMediaGroupOptions(item: WorldItem): ItemPropertyOptionSet {
  const currentGroup = String(item.params.linkedMediaGroup ?? '').trim();
  const entries = Array.from(state.items.values())
    .filter((candidate) => {
      if (candidate.id === item.id) return false;
      if (candidate.type !== 'radio_station') return false;
      if (candidate.locationId !== item.locationId) return false;
      if (candidate.carrierId) return false;
      return String(candidate.params.linkedMediaGroup ?? '').trim().length > 0;
    })
    .map((candidate) => {
      const group = String(candidate.params.linkedMediaGroup ?? '').trim();
      const distance = Math.hypot(candidate.x - item.x, candidate.y - item.y);
      const enabled = candidate.params.enabled !== false;
      const hasMedia = String(candidate.params.playbackUrl ?? candidate.params.streamUrl ?? '').trim().length > 0;
      const role = radioSpeakerRoleLabel(candidate.params.speakerRole);
      return {
        group,
        label: `${candidate.title}, ${role}, ${enabled && hasMedia ? radioPlaybackLabel(candidate) : 'available'} (${Math.round(distance)} away)`,
        distance,
        enabled,
        hasMedia,
        isPrimary: role === 'primary',
      };
    })
    .sort((a, b) => {
      if (a.group === currentGroup && b.group !== currentGroup) return -1;
      if (b.group === currentGroup && a.group !== currentGroup) return 1;
      if (a.enabled !== b.enabled) return a.enabled ? -1 : 1;
      if (a.hasMedia !== b.hasMedia) return a.hasMedia ? -1 : 1;
      if (a.isPrimary !== b.isPrimary) return a.isPrimary ? -1 : 1;
      return a.distance - b.distance || a.label.localeCompare(b.label);
    });
  const values: string[] = [];
  const labels: string[] = [];
  if (currentGroup) {
    values.push(currentGroup);
    labels.push(`Current link: ${currentGroup}`);
  }
  for (const entry of entries) {
    if (values.includes(entry.group)) continue;
    values.push(entry.group);
    labels.push(`Link to ${entry.label}`);
  }
  return { values, labels };
}

function getItemPropertyOptionsForItem(item: WorldItem, key: string): string[] | undefined {
  if (item.type === 'radio_station' && key === 'linkedMediaGroup') {
    const options = radioLinkedMediaGroupOptions(item).values;
    return options.length > 0 ? options : undefined;
  }
  return getItemPropertyOptionValues(item.type, key);
}
const authController = createAuthController({
  dom,
  authPolicyStorageKey: AUTH_POLICY_STORAGE_KEY,
  authSessionCookieSetUrl: AUTH_SESSION_COOKIE_SET_URL,
  authSessionCookieClearUrl: AUTH_SESSION_COOKIE_CLEAR_URL,
  authSessionCookieClientHeader: AUTH_SESSION_COOKIE_CLIENT_HEADER,
  initialAuthUsername,
  initialExternalAuthAssertion,
  isRunning: () => state.running,
  isMuted: () => state.isMuted,
  isConnecting: () => mediaSession.isConnecting(),
  setConnecting: (value) => mediaSession.setConnecting(value),
  applyMuteToTrack: (muted) => {
    mediaSession.applyMuteToTrack(muted);
  },
  signalingSend: (message) => signaling.send(message),
  disconnect,
  saveAuthUsername: (username) => {
    settings.saveAuthUsername(username);
  },
  setConnectionStatus,
  updateStatus,
  pushChatMessage,
  shouldAnnounceRadioAction: () => shouldAnnounceRadioStatus(),
  onServerAdminMenuActions: (actions) => {
    adminController.setServerAdminMenuActions(actions);
  },
});
const adminController = createAdminController({
  state,
  signalingSend: (message) => signaling.send(message),
  announceMenuEntry,
  updateStatus,
  getGridName: () => activeGridName,
  sfxUiBlip: () => audio.sfxUiBlip(),
  sfxUiCancel: () => audio.sfxUiCancel(),
  applyTextInputEdit,
  setReplaceTextOnNextType: (value) => {
    replaceTextOnNextType = value;
  },
});
const itemInteractionController = createItemInteractionController({
  state,
  signalingSend: (message) => signaling.send(message),
  announceMenuEntry,
  updateStatus,
  sfxUiBlip: () => audio.sfxUiBlip(),
  sfxUiCancel: () => audio.sfxUiCancel(),
  hasPermission: (key) => authController.hasPermission(key),
  getAuthUserId: () => authController.getAuthUserId(),
  getItemManagementActionMetadata,
  itemLabel: itemLabelWithInteractionHint,
  getEditableItemPropertyKeys,
  getInspectItemPropertyKeys,
  getItemPropertyValue,
  itemPropertyLabel,
  useItem: (item) => useItem(item),
  secondaryUseItem: (item) => secondaryUseItem(item),
});

/** Toggles updates panel visibility and syncs associated ARIA state. */
function setUpdatesExpanded(expanded: boolean): void {
  dom.updatesToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  dom.updatesToggle.textContent = expanded ? 'Close world updates' : 'Read world updates';
  dom.updatesPanel.hidden = !expanded;
  dom.updatesPanel.classList.toggle('hidden', !expanded);
}

/** Toggles help panel visibility and syncs associated ARIA state. */
function setHelpExpanded(expanded: boolean): void {
  dom.helpToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  dom.helpToggle.textContent = expanded ? 'Hide help' : 'Show help';
  dom.instructions.hidden = !expanded;
  dom.instructions.classList.toggle('hidden', !expanded);
}

/** Renders help sections into the footer help container and builds linearized viewer lines. */
function renderHelp(help: HelpData): void {
  const lines = buildHelpLines(help);
  dom.instructions.innerHTML = '';
  for (const section of help.sections) {
    const sectionHeading = document.createElement('h3');
    sectionHeading.textContent = section.title;
    dom.instructions.appendChild(sectionHeading);
    for (const item of section.items) {
      const line = document.createElement('p');
      const keys = document.createElement('b');
      keys.textContent = `${item.keys}:`;
      line.appendChild(keys);
      line.append(` ${item.description}`);
      dom.instructions.appendChild(line);
    }
  }
  mainHelpViewerLines = lines;
  helpViewerLines = lines;
  helpViewerIndex = 0;
  dom.helpSection.classList.remove('hidden');
  setHelpExpanded(false);
}

/** Loads runtime help content from `help.json` and applies it when available. */
async function loadHelp(): Promise<void> {
  try {
    const response = await fetch(withBase('help.json'), { cache: 'no-store' });
    if (!response.ok) {
      dom.helpSection.classList.add('hidden');
      return;
    }
    const help = (await response.json()) as HelpData;
    if (!Array.isArray(help.sections) || help.sections.length === 0) {
      dom.helpSection.classList.add('hidden');
      return;
    }
    renderHelp(help);
    dom.helpToggle.addEventListener('click', () => {
      const expanded = dom.helpToggle.getAttribute('aria-expanded') === 'true';
      setHelpExpanded(!expanded);
    });
  } catch {
    dom.helpSection.classList.add('hidden');
  }
}

/** Renders changelog sections into the collapsible updates panel. */
function renderChangelog(changelog: ChangelogData): void {
  dom.updatesPanel.innerHTML = '';
  for (const section of changelog.sections) {
    const heading = document.createElement('h3');
    heading.textContent = section.date;
    dom.updatesPanel.appendChild(heading);

    const list = document.createElement('ul');
    for (const item of section.items) {
      const li = document.createElement('li');
      li.textContent = item;
      list.appendChild(li);
    }
    dom.updatesPanel.appendChild(list);
  }
}

/** Loads changelog entries from `changelog.json` and wires the panel toggle button. */
async function loadChangelog(): Promise<void> {
  try {
    const response = await fetch(withBase('changelog.json'), { cache: 'no-store' });
    if (!response.ok) {
      dom.updatesSection.classList.add('hidden');
      return;
    }
    const changelog = (await response.json()) as ChangelogData;
    if (!Array.isArray(changelog.sections) || changelog.sections.length === 0) {
      dom.updatesSection.classList.add('hidden');
      return;
    }
    renderChangelog(changelog);
    setUpdatesExpanded(false);
    dom.updatesToggle.addEventListener('click', () => {
      const expanded = dom.updatesToggle.getAttribute('aria-expanded') === 'true';
      setUpdatesExpanded(!expanded);
    });
  } catch {
    dom.updatesSection.classList.add('hidden');
  }
}

function setStatusText(message: string, announceViaLiveRegion: boolean): void {
  if (statusTimeout !== null) {
    window.clearTimeout(statusTimeout);
  }
  dom.status.setAttribute('aria-live', announceViaLiveRegion ? 'polite' : 'off');
  dom.status.textContent = '';
  requestAnimationFrame(() => {
    dom.status.textContent = message;
  });
  // Keep the last status available for users who need time to review it with
  // a screen reader. A new status replaces it; it is never cleared silently.
}

/** Announces status text with brief de-duplication and auto-clear timing. */
function updateStatus(message: string): void {
  if (!state.running && !joinGuideReaderActive) {
    return;
  }
  const normalized = String(message)
    .replace(/\s*\n+\s*/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
  const now = performance.now();
  if (normalized && normalized === lastAnnouncementText && now - lastAnnouncementAt < 300) {
    return;
  }
  lastAnnouncementText = normalized;
  lastAnnouncementAt = now;

  // Native desktop clients route world narration directly to the active
  // screen reader. The ARIA live region remains the browser fallback.
  const nativeSpeak = (
    window as Window & {
      chatGridNativeSpeak?: (text: string, options?: { interrupt?: boolean }) => void;
    }
  ).chatGridNativeSpeak;
  if (normalized && typeof nativeSpeak === 'function') {
    nativeSpeak(normalized, { interrupt: true });
    setStatusText(normalized, false);
    return;
  }

  setStatusText(normalized, true);
}

/** Updates persistent connection/update status shown under the page heading. */
function setConnectionStatus(message: string): void {
  dom.connectionStatus.textContent = String(message).trim();
}

/** Sanitizes user nicknames to printable/safe characters and enforces max length. */
function sanitizeName(value: string): string {
  return value.replace(/[\u0000-\u001F\u007F<>]/g, '').trim().slice(0, NICKNAME_MAX_LENGTH);
}

/** Enables/disables the connect button based on state and nickname validity. */
function updateConnectAvailability(): void {
  authController.updateConnectAvailability();
}

/** Restores persisted outbound effect levels from local storage. */
function loadEffectLevels(): void {
  const parsed = settings.loadEffectLevels();
  if (!parsed) return;
  audio.setEffectLevels(parsed);
}

/** Persists current outbound effect levels to local storage. */
function persistEffectLevels(): void {
  settings.saveEffectLevels(audio.getEffectLevels());
}

/** Restores local audio-layer toggles and applies initial voice-layer state. */
function loadAudioLayerState(): void {
  audioLayers = settings.loadAudioLayers();
  audio.setVoiceLayerEnabled(audioLayers.voice);
}

/** Persists current audio-layer toggles to local storage. */
function persistAudioLayerState(): void {
  settings.saveAudioLayers(audioLayers);
}

/** Normalizes a user-selected announcement mode into the supported setting values. */
function normalizeAnnouncementMode(value: string): AnnouncementMode {
  return value === 'sounds_only' || value === 'required_only' || value === 'full' ? value : 'full';
}

/** Persists current TTS/beacon preferences to local storage. */
function persistAudioAnnouncementSettings(): void {
  settings.saveAudioAnnouncementSettings(audioAnnouncementSettings);
}

/** Syncs settings controls from persisted TTS/beacon preferences. */
function syncAnnouncementSettingsControls(): void {
  dom.announcementModeSelect.value = audioAnnouncementSettings.mode;
  dom.radioAnnouncementModeSelect.value = audioAnnouncementSettings.radioAnnouncementMode;
  dom.itemBeaconsToggle.checked = audioAnnouncementSettings.itemBeacons;
  dom.movementDirectionsToggle.checked = audioAnnouncementSettings.movementDirections;
}

function syncFlexPbxDialingControls(): void {
  dom.flexPbxOutboundDialingToggle.checked = flexPbxDialingPreferences.enabled;
  dom.flexPbxDialingPrefixesInput.value = flexPbxDialingPreferences.prefixes.join(', ');
  const serverState = flexPbxServerState;
  const unavailable = !state.running || (serverState !== null && (!serverState.verified || !serverState.outboundAllowed));
  dom.flexPbxOutboundDialingToggle.disabled = unavailable;
  dom.flexPbxDialingPrefixesInput.disabled = !state.running;
  if (!state.running) {
    dom.flexPbxDialingStatus.textContent = 'Connect to the server to check FlexPBX verification.';
  } else if (!serverState) {
    dom.flexPbxDialingStatus.textContent = 'Checking server verification… these settings do not grant outbound authorization.';
  } else if (!serverState.verified) {
    dom.flexPbxDialingStatus.textContent = 'The server has not verified FlexPBX outbound dialing for this account. Settings do not grant authorization.';
  } else if (!serverState.outboundAllowed) {
    dom.flexPbxDialingStatus.textContent = serverState.message || 'The server has not enabled FlexPBX outbound dialing for this account.';
  } else {
    dom.flexPbxDialingStatus.textContent = serverState.message || 'Server verification allows convenience outbound dialing. In-world extensions remain the primary path.';
  }
}

function parseFlexPbxPrefixes(value: string): string[] {
  const prefixes = value
    .split(/[\s,]+/)
    .map((prefix) => prefix.trim())
    .filter((prefix) => /^\d+$/.test(prefix))
    .filter((prefix, index, all) => all.indexOf(prefix) === index)
    .slice(0, 8);
  return prefixes.length > 0 ? prefixes : ['9'];
}

function setFlexPbxDialingPreferences(enabled: boolean, prefixesText: string): void {
  flexPbxDialingPreferences = { enabled, prefixes: parseFlexPbxPrefixes(prefixesText) };
  settings.saveFlexPbxDialingPreferences(flexPbxDialingPreferences);
  syncFlexPbxDialingControls();
  if (state.running) {
    signaling.send({
      type: 'flexpbx_dialing_preferences_update',
      enabled: flexPbxDialingPreferences.enabled,
      prefixes: flexPbxDialingPreferences.prefixes,
    });
    dom.flexPbxDialingStatus.textContent = 'Saving convenience dialing preferences; server verification is still required.';
  }
}

function shouldAnnounceRadioStatus(): boolean {
  return audioAnnouncementSettings.radioAnnouncementMode === 'full';
}

function setRadioAnnouncementMode(value: string): void {
  const mode: RadioAnnouncementMode = value === 'sounds_only' || value === 'off' ? value : 'full';
  audioAnnouncementSettings = { ...audioAnnouncementSettings, radioAnnouncementMode: mode };
  persistAudioAnnouncementSettings();
  syncAnnouncementSettingsControls();
  const labels: Record<RadioAnnouncementMode, string> = {
    full: 'radio station readouts on',
    sounds_only: 'radio station sounds only',
    off: 'radio station readouts off',
  };
  updateStatus(`Radio announcements ${labels[mode]}.`);
  audio.sfxUiConfirm();
}

/** Returns whether a bool-like item param is explicitly enabled. */
function itemParamEnabled(item: WorldItem, key: string): boolean {
  const raw = item.params[key];
  if (raw === true) return true;
  if (typeof raw === 'number') return raw !== 0;
  if (typeof raw === 'string') {
    const token = raw.trim().toLowerCase();
    return token === 'true' || token === 'on' || token === 'yes' || token === '1' || token === 'required';
  }
  return false;
}

/** Returns whether the item should still produce a minimal required alert. */
function isItemAnnouncementRequired(item: WorldItem): boolean {
  return itemParamEnabled(item, 'announcementRequired') || itemParamEnabled(item, 'beaconRequired');
}

/** Returns whether optional browser TTS is enabled for this item announcement. */
function shouldSpeakItemAnnouncement(item: WorldItem): boolean {
  if (audioAnnouncementSettings.mode === 'sounds_only') return false;
  if (audioAnnouncementSettings.mode === 'required_only') return isItemAnnouncementRequired(item);
  return true;
}

/** Returns whether an item can produce proximity beacons under the current preference. */
function shouldBeaconItem(item: WorldItem): boolean {
  if (item.carrierId || isItemQuiet(item)) return false;
  if (isItemAnnouncementRequired(item)) return true;
  return audioAnnouncementSettings.itemBeacons;
}

/** Applies a user-selected announcement mode and announces the result. */
function setAnnouncementMode(value: string): void {
  audioAnnouncementSettings = {
    ...audioAnnouncementSettings,
    mode: normalizeAnnouncementMode(value),
  };
  persistAudioAnnouncementSettings();
  syncAnnouncementSettingsControls();
  const labels: Record<AnnouncementMode, string> = {
    full: 'TTS announcements and alert sounds',
    sounds_only: 'alert sounds only',
    required_only: 'required announcements only',
  };
  updateStatus(`Announcements: ${labels[audioAnnouncementSettings.mode]}.`);
  audio.sfxUiConfirm();
}

/** Applies the optional item-beacon preference while preserving required item beacons. */
function setItemBeacons(enabled: boolean): void {
  audioAnnouncementSettings = {
    ...audioAnnouncementSettings,
    itemBeacons: enabled,
  };
  persistAudioAnnouncementSettings();
  syncAnnouncementSettingsControls();
  updateStatus(enabled ? 'Optional item beacons on.' : 'Optional item beacons off. Required item alerts remain on.');
  audio.sfxUiConfirm();
}

/** Enables or disables verbose spoken movement directions for this device. */
function setMovementDirections(enabled: boolean): void {
  audioAnnouncementSettings = {
    ...audioAnnouncementSettings,
    movementDirections: enabled,
  };
  persistAudioAnnouncementSettings();
  syncAnnouncementSettingsControls();
  updateStatus(`Movement direction announcements ${enabled ? 'on' : 'off'}.`);
  audio.sfxUiConfirm();
}

/** Cycles through user-facing TTS announcement modes from the command palette. */
function cycleAnnouncementModeCommand(): void {
  const sequence: AnnouncementMode[] = ['full', 'sounds_only', 'required_only'];
  const currentIndex = sequence.indexOf(audioAnnouncementSettings.mode);
  setAnnouncementMode(sequence[(currentIndex + 1) % sequence.length] ?? 'full');
}

/** Toggles optional item beacons from the command palette. */
function toggleItemBeaconsCommand(): void {
  setItemBeacons(!audioAnnouncementSettings.itemBeacons);
}

/** Clamps microphone input gain to the supported calibration bounds. */
function clampMicInputGain(value: number): number {
  if (!Number.isFinite(value)) return 1;
  return Math.max(MIC_CALIBRATION_MIN_GAIN, Math.min(MIC_CALIBRATION_MAX_GAIN, value));
}

/** Loads persisted microphone input gain and applies default when missing. */
function loadMicInputGain(): void {
  const parsed = settings.loadMicInputGain();
  if (parsed === null) {
    audio.setOutboundInputGain(2);
    return;
  }
  audio.setOutboundInputGain(clampMicInputGain(parsed));
}

/** Persists microphone input gain to local storage. */
function persistMicInputGain(value: number): void {
  settings.saveMicInputGain(value);
}

/** Loads persisted master output volume and applies default when missing. */
function loadMasterVolume(): void {
  const parsed = settings.loadMasterVolume();
  if (parsed === null) {
    audio.setMasterVolume(50);
    return;
  }
  audio.setMasterVolume(parsed);
}

/** Persists master output volume to local storage. */
function persistMasterVolume(value: number): void {
  settings.saveMasterVolume(value);
}

/** Normalizes nickname for local per-user listen-gain preference keys. */
function peerListenGainKey(nickname: string): string {
  return nickname.trim().toLowerCase();
}

/** Returns configured listen gain for a nickname (default 1.0). */
function getPeerListenGainForNickname(nickname: string): number {
  const key = peerListenGainKey(nickname);
  const raw = peerListenGainByNickname[key];
  if (!Number.isFinite(raw)) return 1;
  return clampMicInputGain(raw);
}

/** Persists local listen gain preference for a nickname. */
function setPeerListenGainForNickname(nickname: string, gain: number): void {
  const key = peerListenGainKey(nickname);
  peerListenGainByNickname = { ...peerListenGainByNickname, [key]: clampMicInputGain(gain) };
  settings.savePeerListenGains(peerListenGainByNickname);
}

/** Applies stored listen-gain preferences to currently known peer runtimes. */
function applyConfiguredPeerListenGains(): void {
  for (const [peerId, peerState] of state.peers.entries()) {
    peerManager.setPeerListenGain(peerId, getPeerListenGainForNickname(peerState.nickname));
  }
}

/** Applies current layer toggles to peer voice, media streams, and item emitters. */
async function applyAudioLayerState(): Promise<void> {
  audio.setVoiceLayerEnabled(audioLayers.voice);
  if (audioLayers.voice) {
    await peerManager.resumeRemoteAudio();
  } else {
    peerManager.suspendRemoteAudio();
  }
  const listenerPosition = getListenerPosition();
  await radioRuntime.setLayerEnabled(audioLayers.media, state.items.values(), listenerPosition);
  await itemEmitRuntime.setLayerEnabled(audioLayers.item, state.items.values(), listenerPosition);
  billboardRuntime.setLayerEnabled(audioLayers.item);
  await syncLocationAmbience();
}

/** Refreshes distance-gated radio/item stream subscriptions for a listener position. */
async function refreshAudioSubscriptionsAt(listenerPosition: { x: number; y: number }, force = false): Promise<void> {
  await refreshAudioSubscriptionsForListeners([listenerPosition], force);
}

/** Refreshes distance-gated radio/item stream subscriptions for one or more listener positions. */
async function refreshAudioSubscriptionsForListeners(
  listenerPositions: Array<{ x: number; y: number }>,
  force = false,
): Promise<void> {
  if (!state.running) return;
  if (listenerPositions.length === 0) return;
  const now = Date.now();
  const anchorListener = listenerPositions[listenerPositions.length - 1];
  const tileX = Math.round(anchorListener.x);
  const tileY = Math.round(anchorListener.y);
  const moved = tileX !== lastSubscriptionRefreshTileX || tileY !== lastSubscriptionRefreshTileY;
  if (!force && !moved && now - lastSubscriptionRefreshAt < AUDIO_SUBSCRIPTION_REFRESH_MS) {
    return;
  }
  if (subscriptionRefreshInFlight) {
    subscriptionRefreshPending = true;
    return;
  }
  subscriptionRefreshInFlight = true;
  lastSubscriptionRefreshAt = now;
  lastSubscriptionRefreshTileX = tileX;
  lastSubscriptionRefreshTileY = tileY;
  try {
    if (force) {
      radioRuntime.recoverActivePlayback();
      itemEmitRuntime.recoverActivePlayback();
    }
    await radioRuntime.sync(state.items.values(), listenerPositions);
    tvScreenRuntime.sync(state.items.values(), anchorListener);
    await itemEmitRuntime.sync(state.items.values(), listenerPositions);
  } finally {
    subscriptionRefreshInFlight = false;
    if (subscriptionRefreshPending) {
      subscriptionRefreshPending = false;
      void refreshAudioSubscriptions(true);
    }
  }
}

/** Refreshes distance-gated radio/item stream subscriptions on movement or timer cadence. */
async function refreshAudioSubscriptions(force = false): Promise<void> {
  if (activeTeleport) {
    await refreshAudioSubscriptionsForListeners(
      [
        { x: activeTeleport.startX, y: activeTeleport.startY },
        { x: activeTeleport.targetX, y: activeTeleport.targetY },
      ],
      force,
    );
    return;
  }
  await refreshAudioSubscriptionsAt(getListenerPosition(), force);
}

/** Toggles a single audio layer and applies the change immediately. */
function toggleAudioLayer(layer: keyof AudioLayerState): void {
  audioLayers = { ...audioLayers, [layer]: !audioLayers[layer] };
  persistAudioLayerState();
  void applyAudioLayerState();
  updateStatus(`${layer} layer ${audioLayers[layer] ? 'on' : 'off'}.`);
  audio.sfxUiBlip();
}

/** Routes signaling transport status messages through chat buffer + status output. */
function handleSignalingStatus(message: string): void {
  if (message === 'Connected.') {
    return;
  }
  if (message === 'Disconnected.' && mediaSession.isConnecting() && !state.running) {
    stopLocalMedia();
    mediaSession.setConnecting(false);
    updateConnectAvailability();
    setConnectionStatus('Connect failed. Server disconnected before joining the grid.');
    pushChatMessage('Connect failed. Server disconnected before joining the grid.');
    if (autoReconnectEnabled && !reconnectInFlight) {
      void reconnectAfterSocketClose();
    }
    return;
  }
  if (message === 'Disconnected.' && state.running && !reconnectInFlight) {
    setConnectionStatus('Disconnected from server. Reconnecting...');
    pushChatMessage('Disconnected from server. Reconnecting...');
    void reconnectAfterSocketClose();
    return;
  }
  if (message === 'Disconnected.') {
    setConnectionStatus('Disconnected from server.');
    pushChatMessage('Disconnected from server.');
    return;
  }
  pushChatMessage(message);
}

/** Performs cache-busted navigation so the host loads the newest client bundle. */
function reloadClientForVersion(versionToken: string): void {
  const nextUrl = new URL(window.location.href);
  nextUrl.searchParams.set('v', versionToken || 'unknown');
  nextUrl.searchParams.set('t', String(Date.now()));
  window.location.replace(nextUrl.toString());
}

/** Returns true when this page load came from the version-mismatch reload flow. */
function isVersionReloadedSession(): boolean {
  const params = new URLSearchParams(window.location.search);
  return params.has('v') && params.has('t');
}

/** Removes one-shot version reload markers after startup has consumed them. */
function clearVersionReloadMarker(): void {
  const nextUrl = new URL(window.location.href);
  if (!nextUrl.searchParams.has('v') && !nextUrl.searchParams.has('t')) return;
  nextUrl.searchParams.delete('v');
  nextUrl.searchParams.delete('t');
  window.history.replaceState(window.history.state, '', nextUrl.toString());
}

/** Returns true when a cache-busted page load is recovering a dropped session. */
function isConnectionRecoveryReload(): boolean {
  return new URLSearchParams(window.location.search).has('reconnect');
}

/** Clears the one-shot recovery query marker after the world has admitted us. */
function clearConnectionRecoveryMarker(): void {
  const nextUrl = new URL(window.location.href);
  if (nextUrl.searchParams.has('reconnect')) {
    nextUrl.searchParams.delete('reconnect');
    window.history.replaceState(window.history.state, '', nextUrl.toString());
  }
  sessionStorage.removeItem(RECONNECT_PAGE_REFRESH_KEY);
}

/** Reloads the full client once when transport retries cannot recover a session. */
function refreshClientForConnectionRecovery(): boolean {
  const now = Date.now();
  const previous = Number(sessionStorage.getItem(RECONNECT_PAGE_REFRESH_KEY) || 0);
  if (Number.isFinite(previous) && previous > 0 && now - previous < RECONNECT_PAGE_REFRESH_MAX_AGE_MS) {
    return false;
  }
  sessionStorage.setItem(RECONNECT_PAGE_REFRESH_KEY, String(now));
  const nextUrl = new URL(window.location.href);
  nextUrl.searchParams.delete('v');
  nextUrl.searchParams.delete('t');
  nextUrl.searchParams.set('reconnect', String(now));
  window.location.replace(nextUrl.toString());
  return true;
}

/** Appends a chat/system line to the bounded status history buffer. */
function pushChatMessage(message: string, announce = true): void {
  messageCursor = appendMessageKeepingCursor(messageBuffer, messageCursor, message);
  const normalized = message.trim().toLowerCase();
  if (state.running && normalized.endsWith(' has logged in.')) {
    setConnectionStatus(`${message} Press Shift+L to find them or / to say hello.`);
  }
  if (announce) {
    updateStatus(message);
  }
  systemMessageCursor = appendMessageKeepingCursor(systemMessageBuffer, systemMessageCursor, message);
}

/** Stores one public-room message separately from system and direct traffic. */
function pushPublicChatMessage(message: string): void {
  messageCursor = appendMessageKeepingCursor(messageBuffer, messageCursor, message);
  publicMessageCursor = appendMessageKeepingCursor(publicMessageBuffer, publicMessageCursor, message);
  updateStatus(message);
}

/** Stores one direct message in the two-person conversation for its peer. */
function pushDirectChatMessage(message: string, peerId: string, peerName: string): void {
  messageCursor = appendMessageKeepingCursor(messageBuffer, messageCursor, message);
  const key = conversationKey(peerName);
  const existing = directConversationBuffers.get(key) ?? { peerId, peerName, messages: [], cursor: -1 };
  existing.peerId = peerId;
  existing.peerName = peerName;
  existing.cursor = appendMessageKeepingCursor(existing.messages, existing.cursor, message);
  directConversationBuffers.set(key, existing);
  if (!focusedConversationPeerId) {
    focusedConversationPeerId = peerId;
    focusedConversationPeerName = peerName;
  }
  updateStatus(message);
}

function resetChatHistoryForReplay(): void {
  messageBuffer.length = 0;
  publicMessageBuffer.length = 0;
  directConversationBuffers.clear();
  messageCursor = -1;
  publicMessageCursor = -1;
  focusedConversationPeerId = null;
  focusedConversationPeerName = null;
}

function loadQueuedChatMessages(): QueuedChatMessage[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(MESSAGE_OUTBOX_STORAGE_KEY) || '[]') as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is QueuedChatMessage => {
        if (!item || typeof item !== 'object') return false;
        const row = item as Partial<QueuedChatMessage>;
        return (
          (row.kind === 'room' || row.kind === 'direct') &&
          typeof row.message === 'string' &&
          row.message.trim().length > 0 &&
          typeof row.createdAt === 'number'
        );
      })
      .slice(-MESSAGE_OUTBOX_MAX_ITEMS);
  } catch {
    return [];
  }
}

function saveQueuedChatMessages(messages: QueuedChatMessage[]): void {
  try {
    window.localStorage.setItem(
      MESSAGE_OUTBOX_STORAGE_KEY,
      JSON.stringify(messages.slice(-MESSAGE_OUTBOX_MAX_ITEMS)),
    );
  } catch {
    // If storage is unavailable, the live socket path still handles normal sends.
  }
}

function queueChatMessage(message: QueuedChatMessage): void {
  const queued = loadQueuedChatMessages();
  queued.push(message);
  saveQueuedChatMessages(queued);
  const label = message.kind === 'direct' && message.targetName ? `direct message to ${message.targetName}` : 'room message';
  pushChatMessage(`Queued ${label}. It will send after reconnect.`);
}

function currentPeerIdForQueuedMessage(message: QueuedChatMessage): string | null {
  if (message.kind !== 'direct') return null;
  if (message.targetId && state.peers.has(message.targetId)) {
    return message.targetId;
  }
  const targetName = String(message.targetName || '').trim().toLowerCase();
  if (!targetName) return null;
  for (const peer of state.peers.values()) {
    if (peer.nickname.trim().toLowerCase() === targetName) {
      return peer.id;
    }
  }
  return null;
}

function sendQueuedMessageNow(message: QueuedChatMessage): boolean {
  if (!state.running || !signaling.isOpen()) return false;
  if (message.kind === 'room') {
    return signaling.send({ type: 'chat_message', message: message.message });
  }
  const targetId = currentPeerIdForQueuedMessage(message);
  if (!targetId) return false;
  return signaling.send({ type: 'direct_message', targetId, message: message.message });
}

function flushQueuedChatMessages(): void {
  if (!signaling.isOpen()) return;
  const queued = loadQueuedChatMessages();
  if (queued.length === 0) return;
  const remaining: QueuedChatMessage[] = [];
  let sentCount = 0;
  for (const message of queued) {
    if (sendQueuedMessageNow(message)) {
      sentCount += 1;
    } else {
      remaining.push(message);
    }
  }
  saveQueuedChatMessages(remaining);
  if (sentCount > 0) {
    pushChatMessage(`Sent ${sentCount} queued ${sentCount === 1 ? 'message' : 'messages'}.`);
  }
  if (remaining.length > 0) {
    pushChatMessage(`${remaining.length} queued ${remaining.length === 1 ? 'message is' : 'messages are'} still waiting for the target.`);
  }
}

function sendOrQueueChatMessage(rawMessage: string): void {
  const directTargetId = state.directMessageTargetId;
  const directTargetName = state.directMessageTargetName || undefined;
  const queued: QueuedChatMessage = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    kind: directTargetId ? 'direct' : 'room',
    message: rawMessage,
    targetId: directTargetId || undefined,
    targetName: directTargetName,
    createdAt: Date.now(),
  };
  // Resolve direct targets by the current peer id before sending. A stale id
  // can otherwise be accepted by WebSocket.send() and then discarded by the
  // server after a reconnect or location change.
  if (sendQueuedMessageNow(queued)) {
    return;
  }
  queueChatMessage(queued);
}

/** Refreshes the compact visible dashboard for sighted and low-vision grid users. */
function updateGridDashboard(): void {
  if (!state.running) return;
  const peerCount = state.peers.size;
  const itemCount = Array.from(state.items.values()).filter((item) => !item.carrierId && !isItemQuiet(item)).length;
  const namesHere = getPeerNamesAtPosition(state.player.x, state.player.y);
  const itemsHere = getItemsAtPosition(state.player.x, state.player.y);
  const itemSummary = itemsHere.length > 0 ? formatItemNarrationSummary(itemsHere) : '';
  const hereSummary = [...namesHere, itemSummary].filter(Boolean).join(', ') || 'just you';

  dom.gridPosition.textContent = `${state.player.x}, ${state.player.y}`;
  dom.gridPeople.textContent = peerCount === 1 ? '1 other user' : `${peerCount} other users`;
  dom.gridItems.textContent = itemCount === 1 ? '1 item' : `${itemCount} items`;
  dom.gridHere.textContent = hereSummary;
  dom.worldSummary.textContent = `You are at ${state.player.x}, ${state.player.y}. ${hereSummary}. ${dom.gridPeople.textContent}; ${dom.gridItems.textContent}.`;
}

/** Classifies a system chat line into a corresponding notification sound, when applicable. */
function classifySystemMessageSound(message: string): keyof typeof SYSTEM_SOUND_URLS | null {
  const normalized = message.trim().toLowerCase();
  if (!normalized) return null;
  if (normalized.startsWith('welcome. logged in as ') || normalized.endsWith(' has logged in.')) {
    return 'logon';
  }
  if (normalized.endsWith(' has logged out.')) {
    return 'logout';
  }
  if (normalized.includes(' is now known as ') || normalized.startsWith('you are now known as ')) {
    return 'notify';
  }
  if (normalized.startsWith('server rebooting in ')) {
    return 'notify';
  }
  return null;
}

/** Resolves incoming sound references to playable URLs, including proxy routing when needed. */
function resolveIncomingSoundUrl(url: string): string {
  const raw = String(url || '').trim();
  if (!raw) return '';
  const lowered = raw.toLowerCase();
  if (lowered === 'none' || lowered === 'off') return '';
  if (/^https?:/i.test(raw)) {
    return shouldProxyExternalMediaUrl(raw) ? getProxyUrlForMedia(raw) : raw;
  }
  if (/^(data:|blob:)/i.test(raw)) return raw;
  if (raw.startsWith('/sounds/')) {
    return withBase(raw.slice(1));
  }
  if (raw.startsWith('/voice/')) {
    return withBase(raw.slice(1));
  }
  if (raw.startsWith('sounds/')) {
    return withBase(raw);
  }
  return raw;
}

function stringParam(item: WorldItem, key: string): string {
  const value = item.params[key];
  return typeof value === 'string' ? value.trim() : '';
}

function resolveInteractiveItemUrl(rawUrl: string): string {
  const raw = rawUrl.trim();
  if (!raw) return '';
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith('/')) return new URL(raw, window.location.origin).toString();
  return new URL(raw, window.location.href).toString();
}

function interactiveItemFrameUrl(item: WorldItem, url: string): string {
  const serviceKind = stringParam(item, 'serviceKind').toLowerCase();
  if (serviceKind !== 'game') return url;
  try {
    const frameUrl = new URL(url);
    frameUrl.searchParams.set('embed', 'chatgrid');
    return frameUrl.toString();
  } catch {
    return url;
  }
}

/** Keeps the raw WebUI version metadata in its own browser tab instead of the in-world iframe. */
function isWebUiVersionUrl(item: WorldItem, url: string): boolean {
  const serviceKind = stringParam(item, 'serviceKind').toLowerCase();
  if (serviceKind === 'version') return true;
  try {
    return /(?:^|\/)version(?:\.js)?$/i.test(new URL(url).pathname);
  } catch {
    return false;
  }
}

function canLaunchInteractiveItem(item: WorldItem): boolean {
  if (item.type !== 'service_link') return false;
  if (stringParam(item, 'targetLocation')) return false;
  return Boolean(resolveInteractiveItemUrl(stringParam(item, 'url')));
}

function openInteractiveItem(item: WorldItem): boolean {
  if (!canLaunchInteractiveItem(item)) return false;
  const url = resolveInteractiveItemUrl(stringParam(item, 'url'));
  const serviceKind = stringParam(item, 'serviceKind').toLowerCase();
  if (isWebUiVersionUrl(item, url)) {
    const versionTab = window.open(url, '_blank', 'noopener,noreferrer');
    updateStatus(
      versionTab
        ? `Opened ${item.title} in a new browser tab.`
        : `Your browser blocked the ${item.title} tab. Allow pop-ups for Endiginous and try again.`,
    );
    audio.sfxUiConfirm();
    return Boolean(versionTab);
  }
  dom.interactiveItemTitle.textContent = item.title;
  dom.interactiveItemFrame.title = item.title;
  dom.interactiveItemFrame.src = interactiveItemFrameUrl(item, url);
  dom.interactiveItemPanel.classList.remove('hidden');
  dom.interactiveItemPanel.hidden = false;
  dom.interactiveItemPanel.scrollIntoView({ block: 'start', behavior: 'smooth' });
  dom.interactiveItemFrame.addEventListener(
    'load',
    () => {
      focusInteractiveItemFrame(true);
    },
    { once: true },
  );
  updateStatus(serviceKind === 'game' ? `You opened ${item.title}. The game is ready in Endiginous.` : `You opened ${item.title} in Endiginous.`);
  audio.sfxUiConfirm();
  return true;
}

function openGameLaunchInvite(message: Extract<IncomingMessage, { type: 'item_game_launch' }>): boolean {
  const item = state.items.get(message.itemId);
  const launchItem: WorldItem =
    item && item.type === 'service_link'
      ? item
      : {
          id: message.itemId,
          type: 'service_link',
          title: message.title,
          locationId: currentLocationId,
          x: message.x,
          y: message.y,
          createdBy: message.actorId,
          updatedBy: message.actorId,
          createdAt: 0,
          updatedAt: 0,
          version: 0,
          capabilities: ['usable'],
          params: {
            serviceKind: 'game',
            url: message.url,
          },
          carrierId: null,
        };
  return openInteractiveItem(launchItem);
}

function isDoorTransitionItem(item: WorldItem | null | undefined): boolean {
  if (!item) return false;
  if (['cabin', 'house', 'room', 'shack', 'shed'].includes(item.type)) return true;
  if (item.type !== 'service_link') return false;
  const kind = stringParam(item, 'serviceKind').toLowerCase();
  if (['portal', 'game', 'app', 'service', 'site', 'station', 'tool'].includes(kind)) return false;
  return stringParam(item, 'targetLocation').length > 0;
}

function handleDoorTransitionUseResult(itemId: string | null | undefined): void {
  const item = itemId ? state.items.get(itemId) : null;
  if (!isDoorTransitionItem(item)) return;
  pendingDoorCloseCue = {
    x: item?.x ?? state.player.x,
    y: item?.y ?? state.player.y,
    expiresAt: Date.now() + 5_000,
  };
}

function handleDoorTransitionArrival(x: number, y: number): void {
  if (!pendingDoorCloseCue) return;
  const cue = pendingDoorCloseCue;
  pendingDoorCloseCue = null;
  if (Date.now() > cue.expiresAt || !audioLayers.item) return;
  window.setTimeout(() => {
    void audio.playSpatialSample(DOOR_CLOSE_SOUND_URL, { x, y }, getListenerPosition(), 0.9, HEARING_RADIUS);
  }, 420);
}

function focusInteractiveItemFrame(enterGame = false): void {
  if (dom.interactiveItemPanel.classList.contains('hidden')) return;
  dom.interactiveItemFrame.focus();
  if (enterGame) {
    dom.interactiveItemFrame.contentWindow?.postMessage({ type: 'moonstep-enter-game' }, '*');
  }
}

function closeInteractiveItem(): boolean {
  if (dom.interactiveItemPanel.classList.contains('hidden')) return false;
  dom.interactiveItemFrame.removeAttribute('src');
  dom.interactiveItemPanel.classList.add('hidden');
  dom.interactiveItemPanel.hidden = true;
  updateStatus('Interactive item closed.');
  audio.sfxUiCancel();
  dom.canvas.focus();
  return true;
}

dom.interactiveItemPanel.addEventListener('pointerdown', (event) => {
  if (event.target instanceof HTMLElement && event.target.closest('button, a')) return;
  window.setTimeout(() => focusInteractiveItemFrame(true), 0);
});

document.addEventListener(
  'keydown',
  (event) => {
    if (dom.interactiveItemPanel.classList.contains('hidden')) return;
    if (event.key !== 'Enter' && event.code !== 'Enter') return;
    if (document.activeElement === dom.interactiveItemFrame) return;
    if (event.target instanceof HTMLElement && event.target.closest('button, a, input, textarea, select')) return;
    event.preventDefault();
    focusInteractiveItemFrame(true);
    updateStatus('Game focused.');
  },
  true,
);

/** Navigates buffered chat lines and speaks the selected entry. */
function navigateChatBuffer(target: 'prev' | 'next' | 'first' | 'last'): void {
  if (messageBuffer.length === 0) {
    updateStatus('No chat messages.');
    audio.sfxUiCancel();
    return;
  }

  if (target === 'first') {
    messageCursor = 0;
  } else if (target === 'last') {
    messageCursor = messageBuffer.length - 1;
  } else if (target === 'prev') {
    messageCursor = Math.max(0, messageCursor - 1);
  } else if (target === 'next') {
    messageCursor = Math.min(messageBuffer.length - 1, messageCursor + 1);
  }

  updateStatus(messageBuffer[messageCursor]);
  if (target === 'prev' || target === 'next') {
    const atStart = messageCursor === 0;
    const atEnd = messageCursor === messageBuffer.length - 1;
    if (atStart || atEnd) {
      audio.sfxUiBlip();
    }
  }
}

/** Reads one entry from a dedicated public or system-message buffer. */
function navigateFilteredMessageBuffer(kind: 'public' | 'system', direction: 'prev' | 'next'): void {
  const buffer = kind === 'public' ? publicMessageBuffer : systemMessageBuffer;
  if (buffer.length === 0) {
    updateStatus(`No ${kind} messages.`);
    audio.sfxUiCancel();
    return;
  }
  let cursor = kind === 'public' ? publicMessageCursor : systemMessageCursor;
  cursor = direction === 'prev' ? Math.max(0, cursor - 1) : Math.min(buffer.length - 1, cursor + 1);
  if (kind === 'public') publicMessageCursor = cursor;
  else systemMessageCursor = cursor;
  updateStatus(`${kind === 'public' ? 'Public' : 'System'}: ${buffer[cursor]}`);
  if (cursor === 0 || cursor === buffer.length - 1) audio.sfxUiBlip();
}

/** Moves conversation focus between currently online users. */
function cycleFocusedConversation(direction: 'prev' | 'next'): void {
  const peers = Array.from(state.peers.values()).sort((a, b) => a.nickname.localeCompare(b.nickname));
  if (peers.length === 0) {
    updateStatus('No online users to focus.');
    audio.sfxUiCancel();
    return;
  }
  const currentIndex = peers.findIndex((peer) => peer.id === focusedConversationPeerId);
  const step = direction === 'next' ? 1 : -1;
  const nextIndex = currentIndex < 0
    ? (direction === 'next' ? 0 : peers.length - 1)
    : (currentIndex + step + peers.length) % peers.length;
  const peer = peers[nextIndex];
  focusedConversationPeerId = peer.id;
  focusedConversationPeerName = peer.nickname;
  state.directMessageTargetId = peer.id;
  state.directMessageTargetName = peer.nickname;
  const count = directConversationBuffers.get(conversationKey(peer.nickname))?.messages.length ?? 0;
  updateStatus(`Conversation with ${peer.nickname}, ${count} ${count === 1 ? 'message' : 'messages'}. Control M to write.`);
  audio.sfxUiBlip();
}

/** Reads the previous or next message in the focused two-person conversation. */
function navigateFocusedConversation(direction: 'prev' | 'next'): void {
  if (!focusedConversationPeerId) {
    cycleFocusedConversation('next');
    return;
  }
  const conversation = focusedConversationPeerName
    ? directConversationBuffers.get(conversationKey(focusedConversationPeerName))
    : undefined;
  if (!conversation || conversation.messages.length === 0) {
    updateStatus(`No direct messages with ${focusedConversationPeerName || 'this user'}.`);
    audio.sfxUiCancel();
    return;
  }
  conversation.cursor = direction === 'prev'
    ? Math.max(0, conversation.cursor - 1)
    : Math.min(conversation.messages.length - 1, conversation.cursor + 1);
  updateStatus(conversation.messages[conversation.cursor]);
  if (conversation.cursor === 0 || conversation.cursor === conversation.messages.length - 1) audio.sfxUiBlip();
}

/** Updates compact input/output device summary labels in the pre-connect UI. */
function updateDeviceSummary(): void {
  mediaSession.updateDeviceSummary();
}

/** Returns peer nicknames currently occupying the given grid cell. */
function getPeerNamesAtPosition(x: number, y: number): string[] {
  return Array.from(state.peers.values())
    .filter((peer) => (peer.locationId || currentLocationId) === currentLocationId && peer.x === x && peer.y === y)
    .map((peer) => peer.nickname);
}

/** Returns a user-facing item label including type information. */
function itemLabel(item: WorldItem): string {
  return `${item.title} (${itemTypeLabel(item.type)})`;
}

/** Adds a brief use hint for objects whose interaction is not obvious. */
function itemLabelWithInteractionHint(item: WorldItem): string {
  const hint = formatItemInteractionHint(item);
  return hint ? `${itemLabel(item)}. ${hint}.` : itemLabel(item);
}

/** Resolves effective spatial audio configuration for an item, with global fallbacks. */
function getItemSpatialConfig(item: WorldItem): { range: number; directional: boolean; facingDeg: number } {
  const global = getItemTypeGlobalProperties(item.type);
  const rawParamRange = Number(item.params.emitRange);
  const rawGlobalRange = Number(global.emitRange);
  const rawRange = Number.isFinite(rawParamRange) && rawParamRange > 0 ? rawParamRange : rawGlobalRange;
  const range = Number.isFinite(rawRange) && rawRange > 0 ? rawRange : 15;
  const directional = typeof item.params.directional === 'boolean' ? item.params.directional : global.directional === true;
  const rawFacing = Number(item.params.facing ?? 0);
  const facingDeg = Number.isFinite(rawFacing) ? normalizeDegrees(rawFacing) : 0;
  return { range, directional, facingDeg };
}

/** Enters help-view mode and announces the first help line. */
function openHelpViewer(lines: string[], returnMode: GameMode = 'normal'): void {
  if (lines.length === 0) {
    updateStatus('Help unavailable.');
    audio.sfxUiCancel();
    return;
  }
  helpViewerLines = lines;
  helpViewerReturnMode = returnMode;
  state.mode = 'helpView';
  helpViewerIndex = 0;
  updateStatus(helpViewerLines[helpViewerIndex]);
  audio.sfxUiBlip();
}

/** Returns non-carried items occupying a given grid position. */
function getItemsAtPosition(x: number, y: number, includeQuiet = false): WorldItem[] {
  return Array.from(state.items.values()).filter(
    (item) => !item.carrierId && item.x === x && item.y === y && (includeQuiet || !isItemQuiet(item)),
  );
}

/** Returns whether an item can seat a user under the current item metadata. */
function isSeatableItem(item: WorldItem): boolean {
  const kind = String(item.params.furnitureKind ?? item.params.objectKind ?? item.type).trim().toLowerCase();
  const posture = String(item.params.postureMode ?? '').trim().toLowerCase();
  const capacity = Number(item.params.seatingCapacity);
  if (Number.isFinite(capacity) && capacity <= 0) return false;
  return posture === 'sit' || posture === 'lie' || posture === 'sit_lie' || ['chair', 'couch', 'sofa', 'bench', 'stool', 'loveseat', 'bed'].includes(kind);
}

/** Finds the nearest couch/chair-like item close enough for space-to-sit. */
function getNearestSeatableItem(): WorldItem | null {
  let nearest: WorldItem | null = null;
  let nearestDistance = Infinity;
  for (const item of state.items.values()) {
    if (item.carrierId || isItemQuiet(item) || !isSeatableItem(item)) continue;
    const distance = Math.hypot(item.x - state.player.x, item.y - state.player.y);
    if (distance <= SEAT_INTERACTION_RADIUS && distance < nearestDistance) {
      nearest = item;
      nearestDistance = distance;
    }
  }
  return nearest;
}

/** Returns the current local listener position, including seated head-offset controls. */
function getListenerPosition(): { x: number; y: number; locationId: string } {
  if (state.player.posture === 'standing') {
    return { x: state.player.x, y: state.player.y, locationId: currentLocationId };
  }
  return { x: state.player.x + state.player.seatedOffset, y: state.player.y, locationId: currentLocationId };
}

/** Returns all items currently carried by the local player. */
function getCarriedItems(): WorldItem[] {
  if (!state.player.id) return [];
  return Array.from(state.items.values()).filter((item) => item.carrierId === state.player.id);
}

/** Returns the focused or first item currently carried by the local player, if any. */
function getCarriedItem(): WorldItem | null {
  const carried = getCarriedItems();
  if (state.focusedItemId) {
    const focused = carried.find((item) => item.id === state.focusedItemId);
    if (focused) return focused;
  }
  return carried[0] ?? null;
}

/** Returns whether one carried house object should behave as a radio remote. */
function isRadioRemoteItem(item: WorldItem | null): item is WorldItem {
  if (!item || item.type !== 'house_object') return false;
  const objectKind = String(item.params.objectKind ?? '').trim().toLowerCase();
  if (objectKind !== 'remote') return false;
  const title = item.title.trim().toLowerCase();
  const description = String(item.params.description ?? '').trim().toLowerCase();
  return title.includes('radio') || description.includes('radio');
}

/** Returns whether one carried house object should behave as a TV remote. */
function isTvRemoteItem(item: WorldItem | null): item is WorldItem {
  if (!item || item.type !== 'house_object') return false;
  const objectKind = String(item.params.objectKind ?? '').trim().toLowerCase();
  if (objectKind !== 'remote') return false;
  const title = item.title.trim().toLowerCase();
  const description = String(item.params.description ?? '').trim().toLowerCase();
  const text = `${title} ${description}`;
  return ['tv', 'television', 'movie', 'movies', 'channel', 'channels'].some((token) => text.includes(token));
}

/** Returns the carried radio or TV remote, if the local player has one in hand. */
function getCarriedMediaRemote(): { item: WorldItem; kind: 'radio' | 'tv' } | null {
  const carried = getCarriedItems();
  if (state.focusedItemId) {
    const focused = carried.find((item) => item.id === state.focusedItemId);
    if (isTvRemoteItem(focused)) return { item: focused, kind: 'tv' };
    if (isRadioRemoteItem(focused)) return { item: focused, kind: 'radio' };
    if (focused) return null;
  }
  const tv = carried.find((item) => isTvRemoteItem(item));
  if (tv) return { item: tv, kind: 'tv' };
  const radio = carried.find((item) => isRadioRemoteItem(item));
  if (radio) return { item: radio, kind: 'radio' };
  return null;
}

/** Returns true while the held remote's controls, rather than movement, own the arrows. */
function remoteControlsAreFocused(): boolean {
  return state.remoteControlsFocused && Boolean(getCarriedMediaRemote());
}

/** Returns whether a carried item can occupy a furniture surface slot. */
function isSurfacePlaceableItem(item: WorldItem): boolean {
  return item.type === 'house_object' || item.type === 'radio_station';
}

/** Returns whether a furniture item can receive a placed item. */
function isObjectSurfaceItem(item: WorldItem): boolean {
  return item.type === 'furniture' && item.params.supportsObjects !== false;
}

/** Returns how many item slots are still open on a furniture surface. */
function getOpenSurfaceSlots(surface: WorldItem): number {
  const slotCount = Number(surface.params.surfaceSlots ?? 0);
  if (!Number.isFinite(slotCount)) return 0;
  const occupied = Array.from(state.items.values()).filter(
    (item) =>
      isSurfacePlaceableItem(item) &&
      !item.carrierId &&
      item.params.surfaceId === surface.id,
  ).length;
  return Math.max(0, Math.floor(slotCount) - occupied);
}

/** Finds the focused or same-square furniture surface for automatic placement. */
function getAutomaticPlacementSurface(squareItems = getCurrentSquareItems()): WorldItem | null {
  const focused = getFocusedActionItem();
  if (focused && isObjectSurfaceItem(focused) && getOpenSurfaceSlots(focused) > 0) {
    return focused;
  }
  return squareItems.find((item) => isObjectSurfaceItem(item) && getOpenSurfaceSlots(item) > 0) ?? null;
}

/** Finds a placed house object, preferring the currently focused furniture surface when present. */
function getPlacedHouseObjectForInteraction(squareItems = getCurrentSquareItems()): WorldItem | null {
  const focused = getFocusedActionItem();
  if (focused && isObjectSurfaceItem(focused)) {
    const surfaceObject = squareItems.find(
      (item) => item.type === 'house_object' && item.params.surfaceId === focused.id,
    );
    if (surfaceObject) return surfaceObject;
  }
  return (
    squareItems.find(
      (item) => item.type === 'house_object' && typeof item.params.surfaceId === 'string' && item.params.surfaceId.length > 0,
    ) ?? null
  );
}

/** Describes why the physical interaction key has nothing surface-mounted to affect. */
function describeMissingPlacedHouseObject(squareItems = getCurrentSquareItems()): string {
  const focused = getFocusedActionItem();
  if (focused && isObjectSurfaceItem(focused)) {
    return `Nothing is sitting on ${itemLabel(focused)}.`;
  }
  const surface = squareItems.find((item) => isObjectSurfaceItem(item));
  if (surface) {
    return `Nothing is sitting on ${itemLabel(surface)}.`;
  }
  if (focused) {
    if (focused.type === 'radio_station') {
      return `No loose house object is on ${itemLabel(focused)}. Use Enter to operate the radio.`;
    }
    return `No placed house object is attached to ${itemLabel(focused)}.`;
  }
  const fixture = squareItems.find((item) => item.type !== 'house_object');
  if (fixture) {
    return `No placed house object is attached to ${itemLabel(fixture)}.`;
  }
  return 'No placed house object here.';
}

/** Returns items that can receive normal-mode focus for contextual actions. */
function getFocusableActionItems(): WorldItem[] {
  const items: WorldItem[] = [];
  for (const item of getCarriedItems()) {
    items.push(item);
  }
  for (const item of getCurrentSquareItems()) {
    if (item.capabilities.includes('usable') && !items.some((entry) => entry.id === item.id)) {
      items.push(item);
    }
  }
  return items;
}

/** Returns the currently focused item when it is still contextually available. */
function getFocusedActionItem(): WorldItem | null {
  if (!state.focusedItemId) return null;
  const available = getFocusableActionItems();
  return available.find((item) => item.id === state.focusedItemId) || null;
}

/** Cycles normal-mode item focus through carried and same-square action items. */
function cycleFocusedItemCommand(reverse = false): void {
  const items = getFocusableActionItems();
  if (items.length === 0) {
    state.focusedItemId = null;
    updateStatus('No carried or nearby items to focus.');
    audio.sfxUiCancel();
    return;
  }
  const currentIndex = state.focusedItemId ? items.findIndex((item) => item.id === state.focusedItemId) : -1;
  const direction = reverse ? -1 : 1;
  const nextIndex = ((currentIndex + direction) % items.length + items.length) % items.length;
  const item = items[nextIndex];
  state.focusedItemId = item.id;
  const hint = formatItemInteractionHint(item);
  updateStatus(`Focused ${itemLabel(item)}.${hint ? ` ${hint}.` : ''} Shift+Enter for related actions.`);
  audio.sfxUiBlip();
}

/** Remembers the item the user most recently targeted for direct item actions. */
function focusItemForAction(item: WorldItem): void {
  state.focusedItemId = item.id;
}

/** Returns the focused item id when it is one of the available choices. */
function preferredItemIdFor(items: WorldItem[]): string | null {
  if (!state.focusedItemId) return null;
  return items.some((item) => item.id === state.focusedItemId) ? state.focusedItemId : null;
}

/** Opens the shared item-selection flow for the provided context and items. */
function beginItemSelection(
  context: 'pickup' | 'delete' | 'edit' | 'use' | 'secondaryUse' | 'inspect' | 'manage',
  items: WorldItem[],
  preferredItemId: string | null = preferredItemIdFor(items),
): void {
  itemInteractionController.beginItemSelection(context, items, preferredItemId);
}

/** Builds available item-management actions for one selected item. */
function itemManagementOptionsFor(item: WorldItem) {
  return itemInteractionController.getManagementOptions(item);
}

/** Opens item-management options for one selected item. */
function beginItemManagement(item: WorldItem): void {
  focusItemForAction(item);
  itemInteractionController.beginItemManagement(item);
}

/** Opens item property browsing/editing mode for one item. */
function beginItemProperties(item: WorldItem, showAll = false): void {
  focusItemForAction(item);
  itemInteractionController.beginItemProperties(item, showAll);
}

/** Recomputes visible property rows for the active item-property view after item updates. */
function recomputeActiveItemPropertyKeys(itemId: string): void {
  itemInteractionController.recomputeActiveItemPropertyKeys(itemId);
}

/** Sends an item-use request for the selected item. */
function useItem(item: WorldItem): void {
  focusItemForAction(item);
  if (item.type === 'house_alarm') {
    pendingAlarmItemId = item.id;
    if (item.params.accessSetupComplete !== true) {
      state.mode = 'alarmSetupMethod';
      state.nicknameInput = '';
      state.cursorPos = 0;
      updateStatus('First-use alarm setup. Press 1 for signed-in account access, or 2 for account plus a private in-world keypad code. Escape cancels.');
      audio.sfxDeviceKeypad();
      return;
    }
    state.mode = 'alarmKeypad';
    state.nicknameInput = '';
    state.cursorPos = 0;
    updateStatus('Alarm keypad. Enter an in-world code, or press Enter blank to identify yourself. Escape cancels.');
    audio.sfxDeviceKeypad();
    return;
  }
  if (item.type !== 'radio_station' || shouldAnnounceRadioStatus()) updateStatus(`You use ${itemLabel(item)}.`);
  if (item.type === 'radio_station') {
    audio.sfxRadioPower();
  } else if (item.type === 'house_object') {
    audio.sfxSoftPlasticPress();
  }
  signaling.send({ type: 'item_use', itemId: item.id });
}

/** Selects the first-use alarm access method without exposing credentials. */
function handleAlarmSetupMethodInput(code: string): void {
  if (code === 'Escape') {
    pendingAlarmItemId = null;
    state.mode = 'normal';
    updateStatus('Alarm setup cancelled.');
    audio.sfxUiCancel();
    return;
  }
  if (code === 'Digit1' || code === 'Numpad1') {
    const itemId = pendingAlarmItemId;
    pendingAlarmItemId = null;
    state.mode = 'normal';
    if (itemId) signaling.send({ type: 'item_use', itemId, credential: 'setup:identity' });
    updateStatus('Enrolling your signed-in account.');
    audio.sfxUiConfirm();
    return;
  }
  if (code === 'Digit2' || code === 'Numpad2') {
    state.mode = 'alarmSetupCode';
    state.nicknameInput = '';
    state.cursorPos = 0;
    updateStatus('Enter a private 3 to 16 character in-world resident code, then press Enter. Digits, star, and pound are accepted.');
    audio.sfxDeviceKeypad();
  }
}

/** Enrolls a masked resident code during first-use alarm setup. */
function handleAlarmSetupCodeInput(code: string, key: string): void {
  if (code === 'Escape') {
    pendingAlarmItemId = null;
    state.nicknameInput = '';
    state.cursorPos = 0;
    state.mode = 'normal';
    updateStatus('Alarm setup cancelled.');
    audio.sfxUiCancel();
    return;
  }
  if (code === 'Enter') {
    if (state.nicknameInput.length < 3) {
      updateStatus('The resident code must contain at least 3 keypad characters.');
      audio.sfxUiCancel();
      return;
    }
    const itemId = pendingAlarmItemId;
    const residentCode = state.nicknameInput;
    pendingAlarmItemId = null;
    state.nicknameInput = '';
    state.cursorPos = 0;
    state.mode = 'normal';
    if (itemId) signaling.send({ type: 'item_use', itemId, credential: `setup:identity:${residentCode}` });
    updateStatus('Enrolling account and private resident code.');
    audio.sfxUiConfirm();
    return;
  }
  handleAlarmKeypadCharacterInput(code, key);
}

/** Applies one masked keypad edit shared by normal access and setup. */
function handleAlarmKeypadCharacterInput(code: string, key: string): void {
  if (code === 'Backspace') {
    if (state.nicknameInput.length > 0) {
      state.nicknameInput = state.nicknameInput.slice(0, -1);
      state.cursorPos = state.nicknameInput.length;
      updateStatus('Last keypad character removed.');
      audio.sfxDeviceKeypad();
    }
    return;
  }
  const value = /^Digit[0-9]$/.test(code)
    ? code.slice(-1)
    : /^Numpad[0-9]$/.test(code)
      ? code.slice(-1)
      : code === 'NumpadMultiply' || key === '*'
        ? '*'
        : code === 'NumpadDivide' || key === '#'
          ? '#'
          : '';
  if (!value || state.nicknameInput.length >= 16) return;
  state.nicknameInput += value;
  state.cursorPos = state.nicknameInput.length;
  updateStatus(`Keypad character entered. ${state.nicknameInput.length} total.`);
  audio.sfxDeviceKeypad();
}

/** Handles the private house-alarm keypad without speaking entered digits. */
function handleAlarmKeypadModeInput(code: string, key: string): void {
  if (code === 'Escape') {
    pendingAlarmItemId = null;
    state.nicknameInput = '';
    state.cursorPos = 0;
    state.mode = 'normal';
    updateStatus('Keypad cancelled.');
    audio.sfxUiCancel();
    return;
  }
  if (code === 'Enter') {
    const itemId = pendingAlarmItemId;
    const credential = state.nicknameInput;
    pendingAlarmItemId = null;
    state.nicknameInput = '';
    state.cursorPos = 0;
    state.mode = 'normal';
    if (!itemId) return;
    signaling.send({ type: 'item_use', itemId, credential });
    updateStatus('Keypad entry submitted.');
    audio.sfxUiConfirm();
    return;
  }
  handleAlarmKeypadCharacterInput(code, key);
}

/** Sends an item secondary-use request for the selected item. */
function secondaryUseItem(item: WorldItem): void {
  focusItemForAction(item);
  if (item.type !== 'radio_station' || shouldAnnounceRadioStatus()) updateStatus(`You try ${itemLabel(item)} another way.`);
  if (item.type === 'radio_station') {
    audio.sfxRadioTunerStep();
  } else if (item.type === 'house_object') {
    audio.sfxDeviceHardwareToggle();
  }
  signaling.send({ type: 'item_secondary_use', itemId: item.id });
}

/** Returns one surface's supported contents in stable left-to-right order. */
function getSurfaceContents(surface: WorldItem): WorldItem[] {
  return Array.from(state.items.values())
    .filter(
      (item) =>
        !item.carrierId &&
        item.locationId === surface.locationId &&
        item.params.surfaceId === surface.id,
    )
    .sort((a, b) => Number(a.params.surfaceOrder ?? 0) - Number(b.params.surfaceOrder ?? 0));
}

/** Resolves the focused furniture surface, including focus on one of its contents. */
function getFocusedSurface(): WorldItem | null {
  const focused = getFocusedActionItem();
  if (!focused) return null;
  if (isObjectSurfaceItem(focused)) return focused;
  const surfaceId = String(focused.params.surfaceId ?? '').trim();
  return surfaceId ? state.items.get(surfaceId) ?? null : null;
}

/** Performs a physical interaction without changing item custody. */
function interactItemCommand(): void {
  const focused = getFocusedActionItem();
  const squareItems = getCurrentSquareItems();
  const damaged = squareItems.find(
    (item) =>
      item.type === 'house_object' &&
      (item.params.condition === 'broken' || item.params.condition === 'cracked'),
  );
  if (damaged) {
    updateStatus(`You repair ${itemLabel(damaged)}.`);
    focusItemForAction(damaged);
    signaling.send({ type: 'item_interact', itemId: damaged.id, action: 'repair' });
    return;
  }

  const placedObject = getPlacedHouseObjectForInteraction(squareItems);
  if (!placedObject) {
    if (focused) {
      secondaryUseItem(focused);
      return;
    }
    updateStatus(describeMissingPlacedHouseObject(squareItems));
    audio.sfxUiCancel();
    return;
  }
  updateStatus(`You shove ${itemLabel(placedObject)} off its surface.`);
  focusItemForAction(placedObject);
  signaling.send({ type: 'item_interact', itemId: placedObject.id, action: 'shove_off' });
}

/** Picks up the last focused grabbable item from a furniture surface. */
function pickupSurfaceItemCommand(): void {
  const focused = getFocusedActionItem();
  const focusedSurface = getFocusedSurface();
  const directCandidate = focused && String(focused.params.surfaceId ?? '').trim() && focused.capabilities.includes('carryable') && !focused.carrierId
    ? focused
    : null;
  const surfaceCandidate = focusedSurface
    ? [...getSurfaceContents(focusedSurface)].reverse().find((item) => item.capabilities.includes('carryable') && !item.carrierId) ?? null
    : null;
  const candidate = directCandidate ?? surfaceCandidate ?? null;
  if (!candidate) {
    updateStatus('No grabbable item is available on the focused surface.');
    audio.sfxUiCancel();
    return;
  }
  focusItemForAction(candidate);
  updateStatus(`You take ${itemLabel(candidate)} from ${String(candidate.params.surfaceTitle || 'the surface')}.`);
  signaling.send({ type: 'item_pickup', itemId: candidate.id });
}

/** Announces contents of the focused furniture surface, or loose items on the floor. */
function describeSurfaceCommand(): void {
  const surface = getFocusedSurface();
  if (surface) {
    const contents = getSurfaceContents(surface);
    const description = contents.length > 0
      ? formatItemNarrationSummary(contents)
      : 'nothing';
    updateStatus(`${itemLabel(surface)} holds ${description}.`);
    audio.sfxUiBlip();
    return;
  }
  const floorItems = getCurrentSquareItems().filter(
    (item) =>
      !item.carrierId &&
      String(item.params.surfaceId ?? '').trim().length === 0,
  );
  const description = floorItems.length > 0
    ? formatItemNarrationSummary(floorItems)
    : 'nothing';
  updateStatus(`The floor here holds ${description}.`);
  audio.sfxUiBlip();
}

/** Reorders the focused item within its current furniture surface without leaving that surface. */
function moveFocusedSurfaceItemCommand(direction: 'left' | 'right'): void {
  const item = getFocusedActionItem();
  if (!item) {
    updateStatus('Focus an item on a table or shelf first.');
    audio.sfxUiCancel();
    return;
  }
  const surfaceId = String(item.params.surfaceId || '').trim();
  const surfaceTitle = String(item.params.surfaceTitle || '').trim();
  if (!surfaceId) {
    updateStatus(`${itemLabel(item)} is not sitting on a table or shelf.`);
    audio.sfxUiCancel();
    return;
  }
  updateStatus(`Moving ${itemLabel(item)} ${direction}${surfaceTitle ? ` on ${surfaceTitle}` : ''}.`);
  signaling.send({
    type: 'item_interact',
    itemId: item.id,
    action: direction === 'left' ? 'move_surface_left' : 'move_surface_right',
  });
}

/** Opens option-list selection mode for list-based item properties. */
function openItemPropertyOptionSelect(item: WorldItem, key: string): void {
  const dynamicOptions =
    item.type === 'radio_station' && key === 'linkedMediaGroup'
      ? radioLinkedMediaGroupOptions(item)
      : null;
  const options = dynamicOptions?.values ?? getItemPropertyOptionValues(item.type, key);
  if (!options || options.length === 0) {
    updateStatus(`No ${itemPropertyLabel(key)} choices nearby.`);
    audio.sfxUiCancel();
    return;
  }
  state.mode = 'itemPropertyOptionSelect';
  state.editingPropertyKey = key;
  state.itemPropertyOptionValues = options;
  state.itemPropertyOptionLabels = dynamicOptions?.labels ?? options;
  const currentValue = getItemPropertyValue(item, key);
  const currentIndex = options.indexOf(currentValue);
  state.itemPropertyOptionIndex = currentIndex >= 0 ? currentIndex : 0;
  updateStatus(`Select ${itemPropertyLabel(key)}: ${state.itemPropertyOptionLabels[state.itemPropertyOptionIndex]}`);
  audio.sfxUiBlip();
}

/** Returns the active text-input max length for the current UI mode, if applicable. */
function textInputMaxLengthForMode(mode: typeof state.mode): number | null {
  if (mode === 'nickname') return NICKNAME_MAX_LENGTH;
  if (mode === 'chat') return 500;
  if (mode === 'itemPropertyEdit') return 500;
  if (mode === 'micGainEdit') return 8;
  if (mode === 'adminRoleNameEdit') return 32;
  return null;
}

/** Applies pasted text into whichever mode currently owns the shared text edit buffer. */
function pasteIntoActiveTextInput(raw: string): boolean {
  const maxLength = textInputMaxLengthForMode(state.mode);
  if (maxLength === null) {
    return false;
  }
  const result = applyPastedText(raw, state.nicknameInput, state.cursorPos, maxLength, replaceTextOnNextType);
  if (!result.handled) return false;
  state.nicknameInput = result.newString;
  state.cursorPos = result.newCursorPos;
  replaceTextOnNextType = result.replaceTextOnNextType;
  return true;
}

/** Whether the current mode uses the shared single-line text editing pipeline. */
function isTextEditingMode(mode: typeof state.mode): boolean {
  return (
    mode === 'nickname' ||
    mode === 'chat' ||
    mode === 'itemPropertyEdit' ||
    mode === 'micGainEdit' ||
    mode === 'adminRoleNameEdit'
  );
}

/** Applies keyboard edits to the shared text buffer and emits cursor/deletion speech hints. */
function applyTextInputEdit(code: string, key: string, maxLength: number, ctrlKey = false, allowReplaceOnNextType = false): void {
  if (ctrlKey && code === 'KeyA') {
    replaceTextOnNextType = true;
    state.cursorPos = state.nicknameInput.length;
    updateStatus(`${state.nicknameInput} selected`);
    return;
  }
  if (ctrlKey && code === 'ArrowLeft') {
    state.cursorPos = moveCursorWordLeft(state.nicknameInput, state.cursorPos);
    const spoken = describeCursorWordOrCharacter(state.nicknameInput, state.cursorPos);
    if (spoken) updateStatus(spoken);
    return;
  }
  if (ctrlKey && code === 'ArrowRight') {
    state.cursorPos = moveCursorWordRight(state.nicknameInput, state.cursorPos);
    const spoken = describeCursorWordOrCharacter(state.nicknameInput, state.cursorPos);
    if (spoken) updateStatus(spoken);
    return;
  }

  const beforeText = state.nicknameInput;
  const beforeCursor = state.cursorPos;
  const mappedKey = mapTextInputKey(code, key);

  const replaceDecision = shouldReplaceCurrentText(code, key, replaceTextOnNextType);
  replaceTextOnNextType = replaceDecision.replaceTextOnNextType;
  if (allowReplaceOnNextType && replaceDecision.shouldReplace) {
    state.nicknameInput = key;
    state.cursorPos = key.length;
    return;
  }

  const result = applyTextInput(mappedKey, state.nicknameInput, state.cursorPos, maxLength);
  state.nicknameInput = result.newString;
  state.cursorPos = result.newCursorPos;
  if (code === 'Backspace') {
    const spoken = describeBackspaceDeletedCharacter(beforeText, beforeCursor);
    if (spoken) updateStatus(spoken);
  }
  if (code === 'Delete') {
    const spoken = describeDeleteDeletedCharacter(beforeText, beforeCursor);
    if (spoken) updateStatus(spoken);
  }
  if (code === 'ArrowLeft' || code === 'ArrowRight' || code === 'Home' || code === 'End') {
    const spoken = describeCursorCharacter(state.nicknameInput, state.cursorPos);
    if (spoken) updateStatus(spoken);
  }
}

/** Returns singular/plural square wording for distance announcements. */
function squareWord(distance: number): string {
  return distance === 1 ? 'square' : 'squares';
}

/** Builds a concise room-style coordinate phrase for the current grid location. */
function roomCoordinatePhrase(x: number, y: number): string {
  const location = currentLocationName || currentLocationOption()?.name || 'the grid';
  return `${location}, ${formatCoordinate(x)}, ${formatCoordinate(y)}`;
}

/** Returns a short surface phrase for IF-style movement narration. */
function currentSurfacePhrase(): string {
  const surface = profileForLocationFootsteps(currentLocationOption()).label.trim();
  return surface ? `on ${surface}` : 'through the grid';
}

/** Builds a spoken distance+direction phrase between two grid coordinates. */
function distanceDirectionPhrase(px: number, py: number, tx: number, ty: number): string {
  const distance = Math.round(Math.hypot(tx - px, ty - py));
  const direction = getDirection(px, py, tx, ty);
  if (direction === 'here') return 'here';
  return `${distance} ${squareWord(distance)} ${direction}`;
}

/** Describes where a peer is, including other rooms/locations when known. */
function peerLocationPhrase(peer: PeerState): string {
  const peerLocationId = peer.locationId || currentLocationId;
  const coordinates = `${formatCoordinate(peer.x)}, ${formatCoordinate(peer.y)}`;
  const presence = describePresence(peer.posture, peer.seatedItemId);
  if (peerLocationId && peerLocationId !== currentLocationId) {
    return `in ${locationNameForId(peerLocationId)} at ${coordinates}, ${presence}`;
  }
  return `${distanceDirectionPhrase(state.player.x, state.player.y, peer.x, peer.y)}, ${coordinates}, ${presence}`;
}

/** Gives a truthful, compact posture/mood/looking description for presence narration. */
function describePresence(posture: PeerState['posture'], seatedItemId?: string | null): string {
  const item = seatedItemId ? state.items.get(seatedItemId) : null;
  const kind = String(item?.params.furnitureKind ?? item?.params.objectKind ?? '').trim().toLowerCase();
  const furniture = item?.title || 'the furniture';
  const bedPhrase = kind === 'bed' ? 'in bed' : `on ${furniture}`;
  if (posture === 'lying') {
    const nextToYou = item && item.id === state.player.seatedItemId ? ' next to you' : '';
    return `lying${nextToYou} ${bedPhrase}, relaxed, looking around the room`;
  }
  if (posture === 'sitting') return `sitting ${bedPhrase}, at ease, looking around the room`;
  return 'standing, alert, looking around the room';
}

/** Names a one-step movement direction without the "directly" prefix. */
function movementDirectionPhrase(dx: number, dy: number): string {
  return getDirection(0, 0, dx, dy).replace(/^directly\s+/, '');
}

/** Builds the IF-style narration for a tile after movement or teleport. */
function describeTileArrival(x: number, y: number, dx = 0, dy = 0): string {
  const parts: string[] = [];
  const direction = dx || dy ? movementDirectionPhrase(dx, dy) : '';
  parts.push(direction ? `You walked ${direction} ${currentSurfacePhrase()} to ${roomCoordinatePhrase(x, y)}.` : `You are at ${roomCoordinatePhrase(x, y)}.`);

  const namesOnTile = getPeerNamesAtPosition(x, y);
  if (namesOnTile.length > 0) {
    parts.push(`You hear ${namesOnTile.join(', ')} here.`);
  }

  const itemsOnTile = getItemsAtPosition(x, y);
  if (itemsOnTile.length > 0) {
    parts.push(`You notice ${formatItemNarrationSummary(itemsOnTile)}.`);
  }

  return parts.join(' ');
}

/** Announces local movement with throttling unless the tile has something meaningful. */
function narrateLocalMovement(x: number, y: number, dx: number, dy: number, force = false): void {
  const now = performance.now();
  const direction = movementDirectionPhrase(dx, dy);
  const hasTileContext = getPeerNamesAtPosition(x, y).length > 0 || getItemsAtPosition(x, y).length > 0;
  if (!audioAnnouncementSettings.movementDirections) {
    if (hasTileContext) {
      const context = describeTileArrival(x, y).split('. ').slice(1).join('. ').trim();
      if (context) updateStatus(context);
    }
    return;
  }
  if (!force && !hasTileContext && direction === lastMovementNarrationDirection && now - lastMovementNarrationAt < MOVEMENT_NARRATION_INTERVAL_MS) {
    return;
  }
  lastMovementNarrationAt = now;
  lastMovementNarrationDirection = direction;
  updateStatus(describeTileArrival(x, y, dx, dy));
}

/** Announces a user-facing arrival after a location change. */
function narrateLocationArrival(locationName: string, x: number, y: number): void {
  const location = locationName.trim() || currentLocationName || 'the new location';
  const ambience = currentLocationOption()?.ambienceName?.trim();
  const ambiencePhrase = ambience ? ` ${ambience} ambience is playing.` : '';
  updateStatus(`You entered ${location} at ${formatCoordinate(x)}, ${formatCoordinate(y)}.${ambiencePhrase}`);
}

/** Narrates another user's nearby movement in room-style language. */
function narrateRemoteMovement(nickname: string, fromX: number, fromY: number, toX: number, toY: number): void {
  if (!audioAnnouncementSettings.movementDirections) return;
  const movementDelta = Math.hypot(toX - fromX, toY - fromY);
  if (movementDelta <= 0 || movementDelta > 1.5) return;
  const distanceToPlayer = Math.hypot(toX - state.player.x, toY - state.player.y);
  if (distanceToPlayer > 4) return;
  const direction = movementDirectionPhrase(toX - fromX, toY - fromY);
  const relative = distanceDirectionPhrase(state.player.x, state.player.y, toX, toY);
  updateStatus(`${nickname} walked ${direction}, ${relative}.`);
}

/** Formats a coordinate with up to 2 decimals while trimming trailing zeros. */
function formatCoordinate(value: number): string {
  if (!Number.isFinite(value)) return '0';
  return value.toFixed(2).replace(/\.?0+$/, '');
}

/** Picks one environment-aware footstep cue for a location surface and user identity. */
function randomFootstepCue(
  identity = state.player.id ?? state.player.nickname,
  nickname = state.player.nickname,
  locationId = currentLocationId,
): FootstepCue {
  const profile = profileForLocationFootsteps(locationOptionForId(locationId) ?? currentLocationOption());
  const safeIndexes = profile.sampleIndexes.filter((index) => index >= 1 && index <= FOOTSTEP_SOUND_URLS.length);
  const sampleIndexes = safeIndexes.length > 0 ? safeIndexes : DEFAULT_FOOTSTEP_PROFILE.sampleIndexes;
  const identityHash = hashText(`${identity}:${nickname}`);
  const sampleOffset = identityHash % sampleIndexes.length;
  const randomOffset = Math.floor(Math.random() * sampleIndexes.length);
  const sampleIndex = sampleIndexes[(sampleOffset + randomOffset) % sampleIndexes.length] ?? 1;
  const pitchRange = Math.max(0, profile.pitchMax - profile.pitchMin);
  const identityPitch = ((identityHash >>> 8) % 9 - 4) * 0.012;
  const playbackRate = Math.max(0.55, profile.pitchMin + Math.random() * pitchRange + identityPitch);
  return {
    url: FOOTSTEP_SOUND_URLS[sampleIndex - 1] ?? FOOTSTEP_SOUND_URLS[0],
    gain: profile.gain,
    fadeInMs: profile.fadeInMs ?? 0,
    playbackRate,
    identity,
    nickname,
    surface: profile.label,
  };
}

/** Stable tiny hash used only for deterministic per-user sound color. */
function hashText(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/** Stops active teleport loop audio, if one is running. */
function stopTeleportLoopAudio(): void {
  if (!activeTeleportLoopStop) return;
  activeTeleportLoopStop();
  activeTeleportLoopStop = null;
}

/** Starts animated teleport movement toward a target tile at fixed squares-per-second pace. */
function startTeleportTo(targetX: number, targetY: number, completionStatus: string): void {
  const startX = state.player.x;
  const startY = state.player.y;
  const distance = Math.hypot(targetX - startX, targetY - startY);
  const durationMs = Math.max(1, (distance / TELEPORT_SQUARES_PER_SECOND) * 1000);
  const nowMs = performance.now();
  activeTeleport = {
    startX,
    startY,
    targetX,
    targetY,
    startedAtMs: nowMs,
    durationMs,
    lastSyncAtMs: nowMs,
    lastSentX: Math.round(startX),
    lastSentY: Math.round(startY),
    completionStatus,
  };
  stopTeleportLoopAudio();
  activeTeleportLoopToken += 1;
  const loopToken = activeTeleportLoopToken;
  void audio.startLoopingSample(TELEPORT_START_SOUND_URL, TELEPORT_START_GAIN, {
    fadeInSeconds: 0.08,
    fadeOutSeconds: 0.1,
    startDelaySeconds: 0.04,
  }).then((stopLoop) => {
    if (!stopLoop) return;
    if (activeTeleport && loopToken === activeTeleportLoopToken) {
      activeTeleportLoopStop = stopLoop;
      return;
    }
    stopLoop();
  });
  void refreshAudioSubscriptionsForListeners(
    [
      { x: startX, y: startY },
      { x: targetX, y: targetY },
    ],
    true,
  );
  state.keysPressed.ArrowUp = false;
  state.keysPressed.ArrowDown = false;
  state.keysPressed.ArrowLeft = false;
  state.keysPressed.ArrowRight = false;
  lastWallCollisionDirection = null;
}

/** Advances active teleport animation, syncs intermediate server positions, and finalizes arrival. */
function updateTeleport(): void {
  if (!activeTeleport) return;
  const nowMs = performance.now();
  const elapsedMs = nowMs - activeTeleport.startedAtMs;
  const progress = Math.max(0, Math.min(1, elapsedMs / activeTeleport.durationMs));
  state.player.x = activeTeleport.startX + (activeTeleport.targetX - activeTeleport.startX) * progress;
  state.player.y = activeTeleport.startY + (activeTeleport.targetY - activeTeleport.startY) * progress;

  if (nowMs - activeTeleport.lastSyncAtMs >= movementTickMs) {
    activeTeleport.lastSyncAtMs = nowMs;
    const desiredX = Math.round(state.player.x);
    const desiredY = Math.round(state.player.y);
    const stepX = Math.sign(desiredX - activeTeleport.lastSentX);
    const stepY = Math.sign(desiredY - activeTeleport.lastSentY);
    const syncX = activeTeleport.lastSentX + stepX;
    const syncY = activeTeleport.lastSentY + stepY;
    if (syncX !== activeTeleport.lastSentX || syncY !== activeTeleport.lastSentY) {
      activeTeleport.lastSentX = syncX;
      activeTeleport.lastSentY = syncY;
      signaling.send({ type: 'update_position', x: syncX, y: syncY });
    }
  }

  if (progress < 1) {
    return;
  }
  const completionStatus = activeTeleport.completionStatus;
  state.player.x = activeTeleport.targetX;
  state.player.y = activeTeleport.targetY;
  signaling.send({ type: 'teleport_complete', x: activeTeleport.targetX, y: activeTeleport.targetY });
  activeTeleport = null;
  stopTeleportLoopAudio();
  void refreshAudioSubscriptions(true);
  void audio.playSample(TELEPORT_SOUND_URL, FOOTSTEP_GAIN);
  updateStatus(`${completionStatus} ${describeTileArrival(state.player.x, state.player.y)}`);
}

function isNearCarefulNavigationZone(x: number, y: number): boolean {
  if (x <= 0 || y <= 0 || x >= worldGridWidth - 1 || y >= worldGridHeight - 1) return true;
  for (const item of state.items.values()) {
    if (item.locationId && item.locationId !== currentLocationId) continue;
    if (Math.hypot(item.x - x, item.y - y) <= 1.5) return true;
  }
  for (const peer of state.peers.values()) {
    if (peer.locationId && peer.locationId !== currentLocationId) continue;
    if (Math.hypot(peer.x - x, peer.y - y) <= 1.5) return true;
  }
  return false;
}

function effectiveMovementTickMs(): number {
  const shiftHeld = Boolean(state.keysPressed.ShiftLeft || state.keysPressed.ShiftRight || state.keysPressed.Shift);
  const careful = isNearCarefulNavigationZone(state.player.x, state.player.y);
  if (careful) {
    return Math.round(movementTickMs * CAREFUL_MOVEMENT_TICK_MULTIPLIER);
  }
  if (shiftHeld) {
    return Math.max(80, Math.round(movementTickMs * RUN_MOVEMENT_TICK_MULTIPLIER));
  }
  return movementTickMs;
}

/** Main animation/update loop for movement, spatial audio, and rendering. */
function gameLoop(): void {
  if (!state.running) return;
  try {
    updateTeleport();
    handleMovement();
  } catch (error) {
    const now = performance.now();
    if (now - lastRuntimeRecoveryStatusAt >= RUNTIME_RECOVERY_STATUS_INTERVAL_MS) {
      lastRuntimeRecoveryStatusAt = now;
      console.error('Endiginous movement loop recovered after an error.', error);
      state.keysPressed = {};
      activeTeleport = null;
    }
  }
  try {
    const listenerPosition = getListenerPosition();
    if (!activeTeleport) {
      void refreshAudioSubscriptions();
    }
    audio.updateSpatialAudio(peerManager.getPeers(), listenerPosition);
    audio.updateSpatialSamples(listenerPosition);
    radioRuntime.updateSpatialAudio(state.items, listenerPosition);
    tvScreenRuntime.sync(state.items.values(), listenerPosition);
    itemEmitRuntime.updateSpatialAudio(state.items, listenerPosition);
    billboardRuntime.update(state.items, listenerPosition);
    updateItemBeacon();
    state.cursorVisible = Math.floor(Date.now() / 500) % 2 === 0;
    updateGridDashboard();
    renderer.draw(state);
  } catch (error) {
    const now = performance.now();
    if (now - lastRuntimeRecoveryStatusAt >= RUNTIME_RECOVERY_STATUS_INTERVAL_MS) {
      lastRuntimeRecoveryStatusAt = now;
      console.error('Endiginous presentation loop recovered after an error.', error);
    }
  } finally {
    if (state.running) {
      requestAnimationFrame(gameLoop);
    }
  }
}

/** Applies held-arrow movement with bounds checks, tile cues, and server position sync. */
function handleMovement(): void {
  if (state.mode !== 'normal') return;
  if (activeTeleport) return;
  if (
    remoteControlsAreFocused() &&
    (state.keysPressed.ArrowUp || state.keysPressed.ArrowDown || state.keysPressed.ArrowLeft || state.keysPressed.ArrowRight)
  ) {
    return;
  }
  const now = Date.now();
  if (now - state.player.lastMoveTime < effectiveMovementTickMs()) return;

  let dx = 0;
  let dy = 0;
  if (state.keysPressed.ArrowUp) dy = 1;
  if (state.keysPressed.ArrowDown) dy = -1;
  if (state.keysPressed.ArrowLeft) dx = -1;
  if (state.keysPressed.ArrowRight) dx = 1;

  if (dx === 0 && dy === 0) {
    lastWallCollisionDirection = null;
    lastAutoSeatItemId = '';
    return;
  }

  if (state.player.posture !== 'standing') {
    // Ordinary arrows must recover a seated reconnect. The server treats an
    // update_position packet as both standing up and moving, while keeping
    // horizontal arrows in a local offset mode made users appear stuck.
    signaling.send({ type: 'update_position', x: state.player.x + dx, y: state.player.y + dy });
    updateStatus('You stand up and move away from the furniture.');
    audio.sfxUiBlip();
    return;
  }

  const nextX = state.player.x + dx;
  const nextY = state.player.y + dy;
  const attemptedDirection = `${dx},${dy}`;
  if (nextX < 0 || nextY < 0 || nextX >= worldGridWidth || nextY >= worldGridHeight) {
    state.player.lastMoveTime = now;
    if (lastWallCollisionDirection !== attemptedDirection) {
      void audio.playSample(WALL_SOUND_URL, 1);
      updateStatus(`A boundary blocks you to the ${movementDirectionPhrase(dx, dy)}.`);
      lastWallCollisionDirection = attemptedDirection;
    }
    return;
  }

  state.player.x = nextX;
  state.player.y = nextY;
  lastWallCollisionDirection = null;
  state.player.lastMoveTime = now;
  void refreshAudioSubscriptions(true);
  const footstep = randomFootstepCue();
  void audio.playSample(footstep.url, footstep.gain, footstep.fadeInMs, footstep.playbackRate);
  audio.playStepSignature({ identity: footstep.identity, nickname: footstep.nickname });
  signaling.send({ type: 'update_position', x: nextX, y: nextY });

  const namesOnTile = getPeerNamesAtPosition(nextX, nextY);
  const itemsOnTile = getItemsAtPosition(nextX, nextY);
  if (namesOnTile.length > 0) {
    audio.sfxTileUserPing();
  }
  if (itemsOnTile.length > 0) {
    audio.sfxTileItemPing();
  }
  narrateLocalMovement(nextX, nextY, dx, dy);
  const nearestSeat = getNearestSeatableItem();
  if (nearestSeat && nearestSeat.id !== lastAutoSeatItemId) {
    lastAutoSeatItemId = nearestSeat.id;
    const kind = String(nearestSeat.params.furnitureKind ?? nearestSeat.params.objectKind ?? '').trim().toLowerCase();
    const posture = kind === 'bed' ? 'settle onto the bed' : 'gently settle into a relaxed sitting position';
    updateStatus(`You are close to ${nearestSeat.title}; you ${posture}.`);
    signaling.send({ type: 'item_use', itemId: nearestSeat.id });
  }
}

/** Checks microphone permission state when Permissions API support is available. */
async function checkMicPermission(): Promise<boolean> {
  return mediaSession.checkMicPermission();
}

/** Starts local microphone capture and rebuilds the outbound track pipeline. */
async function setupLocalMedia(audioDeviceId = ''): Promise<void> {
  await mediaSession.setupLocalMedia(audioDeviceId);
  authController.reapplyVoiceSendPermission();
}

/** Runs a short RMS sample to estimate and apply a usable microphone input gain. */
async function calibrateMicInputGain(): Promise<void> {
  await mediaSession.calibrateMicInputGain(clampMicInputGain, persistMicInputGain);
}

/** Stops local capture tracks and clears outbound stream references. */
function stopLocalMedia(): void {
  mediaSession.stopLocalMedia();
}

/** Maps host media/capture errors to user-facing remediation text. */
function describeMediaError(error: unknown): string {
  return mediaSession.describeMediaError(error);
}

/** Restores loopback state captured when entering microphone gain edit mode. */
function restoreLoopbackAfterMicGainEdit(): void {
  if (micGainLoopbackRestoreState === null) {
    return;
  }
  audio.setLoopbackEnabled(micGainLoopbackRestoreState);
  micGainLoopbackRestoreState = null;
}

/** Stops heartbeat timer and clears in-memory heartbeat state. */
function stopHeartbeat(): void {
  if (heartbeatTimerId !== null) {
    window.clearInterval(heartbeatTimerId);
    heartbeatTimerId = null;
  }
  heartbeatAwaitingPong = false;
}

/** Sends one heartbeat ping packet using reserved negative ids. */
function sendHeartbeatPing(): void {
  signaling.send({ type: 'ping', clientSentAt: heartbeatNextPingId });
  heartbeatNextPingId -= 1;
  heartbeatAwaitingPong = true;
}

/** Starts heartbeat timer for stale-connection detection. */
function startHeartbeat(): void {
  stopHeartbeat();
  heartbeatAwaitingPong = false;
  sendHeartbeatPing();
  heartbeatTimerId = window.setInterval(() => {
    if (!state.running) return;
    if (heartbeatAwaitingPong) {
      void reconnectAfterHeartbeatTimeout();
      return;
    }
    sendHeartbeatPing();
  }, HEARTBEAT_INTERVAL_MS);
}

/** Performs one reconnect attempt when heartbeat timeout indicates stale signaling. */
async function reconnectAfterHeartbeatTimeout(): Promise<void> {
  await reconnectWithRetry('heartbeat');
}

/** Performs immediate reconnect when websocket closes unexpectedly. */
async function reconnectAfterSocketClose(): Promise<void> {
  await reconnectWithRetry('socketClose');
}

/** Reconnects after disconnect with delay and bounded retry attempts. */
async function reconnectWithRetry(reason: 'heartbeat' | 'socketClose'): Promise<void> {
  if (reconnectInFlight || !autoReconnectEnabled) return;
  reconnectInFlight = true;
  stopHeartbeat();
  if (reason === 'heartbeat') {
    pushChatMessage('Connection stale. Reconnecting...');
  }
  disconnect(false);
  for (let attempt = 1; attempt <= RECONNECT_MAX_ATTEMPTS; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, RECONNECT_DELAY_MS));
    await connect();
    const waitStartedAt = Date.now();
    while (!state.running && Date.now() - waitStartedAt < 4_000) {
      await new Promise((resolve) => window.setTimeout(resolve, 100));
    }
    if (state.running) {
      reconnectInFlight = false;
      return;
    }
    if (attempt < RECONNECT_MAX_ATTEMPTS) {
      pushChatMessage(`Reconnect attempt ${attempt} failed. Retrying in 5 seconds...`);
    }
  }
  if (refreshClientForConnectionRecovery()) {
    pushChatMessage('Connection recovery is refreshing the client and restoring your saved session...');
    return;
  }
  pushChatMessage('Connection is still unavailable. Retrying automatically in 15 seconds...');
  audio.sfxUiCancel();
  reconnectInFlight = false;
  window.setTimeout(() => {
    void reconnectWithRetry('socketClose');
  }, 15_000);
}

/** Sends current auth request over signaling websocket after socket open. */
function sendAuthRequest(): void {
  authController.sendAuthRequest();
}

/** Handles server auth-required prompts prior to world welcome. */
function handleAuthRequired(message: Extract<IncomingMessage, { type: 'auth_required' }>): void {
  applyGridBranding(message.gridName, message.welcomeMessage);
  const expectedClientRevision = String(message.expectedClientRevision ?? '').trim();
  if (!reloadScheduledForVersionMismatch && expectedClientRevision && expectedClientRevision !== APP_CLIENT_REVISION) {
    reloadScheduledForVersionMismatch = true;
    const serverVersion = String(message.serverVersion ?? '').trim() || 'unknown';
    pushChatMessage(
      `Server ${serverVersion} expects client ${expectedClientRevision}. Reloading client...`,
    );
    window.setTimeout(() => {
      reloadClientForVersion(expectedClientRevision);
    }, 50);
    return;
  }
  authController.handleAuthRequired(message);
}

/** Applies auth result state and terminates failed auth attempts quickly. */
async function handleAuthResult(message: Extract<IncomingMessage, { type: 'auth_result' }>): Promise<void> {
  if (message.nickname) {
    const resolved = sanitizeName(message.nickname);
    if (resolved) {
      state.player.nickname = resolved;
    }
  }
  await authController.handleAuthResult(message);
}

/** Handles server-pushed role/permission refresh events for the current session. */
function handleAuthPermissions(message: Extract<IncomingMessage, { type: 'auth_permissions' }>): void {
  authController.handleAuthPermissions(message);
}

/** Returns available admin-menu root actions based on current permission set. */
function getAvailableAdminActions(): AdminMenuAction[] {
  return adminController.getAvailableAdminActions();
}

/** Handles server role-list response for admin menu flows. */
function handleAdminRolesList(message: Extract<IncomingMessage, { type: 'admin_roles_list' }>): void {
  adminController.handleAdminRolesList(message);
}

/** Handles server user-list response for admin menu flows. */
function handleAdminUsersList(message: Extract<IncomingMessage, { type: 'admin_users_list' }>): void {
  adminController.handleAdminUsersList(message);
}

/** Handles server platform overview response for admin menu flows. */
function handleAdminPlatformOverview(message: Extract<IncomingMessage, { type: 'admin_platform_overview' }>): void {
  adminController.handleAdminPlatformOverview(message);
}

/** Handles server notification-list response for admin menu flows. */
function handleAdminNotificationsList(message: Extract<IncomingMessage, { type: 'admin_notifications_list' }>): void {
  adminController.handleAdminNotificationsList(message);
}

function handleAdminAmbienceCatalog(message: Extract<IncomingMessage, { type: 'admin_ambience_catalog' }>): void {
  adminController.handleAdminAmbienceCatalog(message);
}

/** Handles server transfer-target list response for item-management transfer flow. */
function handleItemTransferTargets(message: Extract<IncomingMessage, { type: 'item_transfer_targets' }>): void {
  itemInteractionController.handleItemTransferTargets(message);
}

/** Handles structured admin action result packets. */
function handleAdminActionResult(message: Extract<IncomingMessage, { type: 'admin_action_result' }>): void {
  adminController.handleAdminActionResult(message);
  audio.sfxUiConfirm();
}

/** Applies server-backed ntfy preferences for the signed-in Endiginous identity. */
function handleNtfyPreferences(message: Extract<IncomingMessage, { type: 'ntfy_preferences' }>): void {
  dom.ntfyNotificationsToggle.disabled = !message.configured;
  dom.ntfyNotificationsToggle.checked = message.enabled;
  dom.ntfyNotificationsStatus.textContent = message.configured
    ? (message.message || (message.enabled ? 'ntfy notifications are enabled.' : 'ntfy notifications are disabled.'))
    : 'ntfy delivery is not configured on this server.';
  if (message.subscriptionUrl) {
    dom.ntfySubscriptionLink.href = message.subscriptionUrl;
    dom.ntfySubscriptionLink.classList.remove('hidden');
    dom.rotateNtfyTopicButton.classList.remove('hidden');
  } else {
    dom.ntfySubscriptionLink.removeAttribute('href');
    dom.ntfySubscriptionLink.classList.add('hidden');
    dom.rotateNtfyTopicButton.classList.add('hidden');
  }
}

/** Applies server-owned FlexPBX eligibility and convenience dialing settings. */
function handleFlexPbxDialingPreferences(
  message: Extract<IncomingMessage, { type: 'flexpbx_dialing_preferences' }>,
): void {
  flexPbxServerState = {
    verified: message.verified,
    outboundAllowed: message.outboundAllowed,
    message: message.message,
  };
  flexPbxDialingPreferences = {
    enabled: message.enabled,
    prefixes: parseFlexPbxPrefixes(message.prefixes.join(', ')),
  };
  settings.saveFlexPbxDialingPreferences(flexPbxDialingPreferences);
  syncFlexPbxDialingControls();
}

/** Builds dependencies shared by connect/disconnect flow helpers. */
function getConnectionFlowDeps(): ConnectFlowDeps {
  return {
    state,
    dom,
    sanitizeName,
    updateStatus: (message) => {
      if (!state.running) {
        setConnectionStatus(message);
        return;
      }
      if (message === 'Disconnected.') {
        setConnectionStatus('Disconnected.');
      } else if (message.startsWith('Connect failed.')) {
        setConnectionStatus(message);
      }
      if (reconnectInFlight && message === 'Disconnected.') {
        return;
      }
      pushChatMessage(message);
    },
    updateConnectAvailability,
    mediaIsConnecting: () => mediaSession.isConnecting(),
    mediaSetConnecting: (value) => mediaSession.setConnecting(value),
    mediaStopLocalMedia: () => stopLocalMedia(),
    signalingConnect: (handler) => signaling.connect(handler as (message: IncomingMessage) => Promise<void>),
    signalingSendAuth: () => sendAuthRequest(),
    signalingDisconnect: () => signaling.disconnect(),
    onMessage: (message) => onSignalingMessage(message as IncomingMessage),
    peerManagerCleanupAll: () => peerManager.cleanupAll(),
    radioCleanupAll: () => radioRuntime.cleanupAll(),
    emitCleanupAll: () => itemEmitRuntime.cleanupAll(),
    playLogoutSound: () => {
      void audio.playSample(SYSTEM_SOUND_URLS.logout, 1);
    },
  };
}

/** Performs end-to-end connect flow: validation, media setup, then signaling connection. */
async function connect(): Promise<void> {
  autoReconnectEnabled = true;
  setConnectionStatus('Connecting...');
  await runConnectFlow(getConnectionFlowDeps());
}

/** Tears down active session state, media, peers, and UI back to pre-connect mode. */
function disconnect(intentional = true): void {
  if (intentional) {
    autoReconnectEnabled = false;
  }
  stopHeartbeat();
  runDisconnectFlow(getConnectionFlowDeps());
  setConnectionStatus('Disconnected.');
  pendingEscapeDisconnect = false;
  restoreLoopbackAfterMicGainEdit();
  subscriptionRefreshPending = false;
  subscriptionRefreshInFlight = false;
  lastSubscriptionRefreshAt = 0;
  lastSubscriptionRefreshTileX = Math.round(state.player.x);
  lastSubscriptionRefreshTileY = Math.round(state.player.y);
  stopTeleportLoopAudio();
  activeTeleport = null;
  peerNegotiationReady = false;
  pendingSignalMessages = [];
  itemInteractionController.reset();
  itemBehaviorRegistry.cleanup();
}

async function hasValidAuthSessionCookie(): Promise<boolean> {
  try {
    const response = await fetch(AUTH_SESSION_COOKIE_CHECK_URL, {
      method: 'GET',
      credentials: 'include',
      headers: {
        [AUTH_SESSION_COOKIE_CLIENT_HEADER]: '1',
      },
      cache: 'no-store',
    });
    return response.status === 204;
  } catch (error) {
    console.warn('Unable to check saved auth session.', error);
    return false;
  }
}

async function autoConnectFromSavedSessionCookie(): Promise<void> {
  if (state.running || mediaSession.isConnecting()) {
    return;
  }
  const hasCookie = await hasValidAuthSessionCookie();
  authController.setSavedSessionCookieAvailable(hasCookie);
  if (!hasCookie || state.running || mediaSession.isConnecting()) {
    return;
  }
  setConnectionStatus('Restoring saved session...');
  await connect();
}

/** Starts peer negotiation only after welcome + media setup sequencing is complete. */
async function activatePeerNegotiation(): Promise<void> {
  if (!state.running) return;
  if (peerNegotiationReady) return;
  peerNegotiationReady = true;
  for (const peer of state.peers.values()) {
    await peerManager.createOrGetPeer(peer.id, true, peer);
  }
  if (pendingSignalMessages.length === 0) return;
  const queued = pendingSignalMessages;
  pendingSignalMessages = [];
  for (const signal of queued) {
    await onAppMessage(signal);
  }
}

/** Drops stale voice/media runtimes so reconnects rebuild full streams cleanly. */
function resetRealtimeStreamsForReconnect(): void {
  peerNegotiationReady = false;
  pendingSignalMessages = [];
  peerManager.cleanupAll();
  radioRuntime.resetPlaybackRecovery();
  itemEmitRuntime.resetPlaybackRecovery();
}

const onAppMessage = createOnMessageHandler({
  getWorldGridSize: () => worldGridSize,
  getCurrentLocationId: () => currentLocationId,
  setWorldGridSize: (size) => {
    worldGridSize = size;
  },
  setWorldGridDimensions: (width, height) => {
    worldGridWidth = Math.max(1, Math.min(worldGridSize, width));
    worldGridHeight = Math.max(1, Math.min(worldGridSize, height));
  },
  setMovementTickMs: (value) => {
    movementTickMs = Math.max(1, value);
  },
  setWorldLocations,
  setCurrentLocation,
  setConnecting: (value) => {
    mediaSession.setConnecting(value);
    updateConnectAvailability();
  },
  rendererSetGridSize: (size) => renderer.setGridSize(size),
  applyServerItemUiDefinitions: (defs) => applyServerItemUiDefinitions(defs as Parameters<typeof applyServerItemUiDefinitions>[0]),
  state,
  dom,
  signalingSend: (message) => signaling.send(message as OutgoingMessage),
  peerManager,
  refreshAudioSubscriptions,
  cleanupItemAudio: (itemId) => {
    radioRuntime.cleanup(itemId);
    itemEmitRuntime.cleanup(itemId);
    billboardRuntime.cleanup(itemId);
  },
  applyAudioLayerState,
  syncLocationAmbience,
  gameLoop,
  sanitizeName,
  randomFootstepCue,
  playRemoteSpatialStepOrTeleport: (cue, peerX, peerY) => {
    const listenerPosition = getListenerPosition();
    const url = typeof cue === 'string' ? cue : cue.url;
    const gain = url === TELEPORT_START_SOUND_URL ? TELEPORT_START_GAIN : FOOTSTEP_GAIN;
    const playbackRate = typeof cue === 'string' ? 1 : cue.playbackRate;
    void audio.playSpatialSample(
      url,
      { x: peerX, y: peerY },
      listenerPosition,
      typeof cue === 'string' ? gain : cue.gain,
      undefined,
      playbackRate,
    );
    if (typeof cue !== 'string') {
      audio.playStepSignature({
        identity: cue.identity,
        nickname: cue.nickname,
        sourcePosition: { x: peerX, y: peerY },
        playerPosition: listenerPosition,
        range: HEARING_RADIUS,
      });
    }
  },
  narrateLocationArrival,
  narrateRemoteMovement,
  handleItemActionResultStatus: (message) => itemBehaviorRegistry.onActionResultStatus(message),
  handleMediaCastState: (message) => {
    if (message.active) {
      activeCastTargetByCaster.set(message.casterId, { itemId: message.targetItemId, mediaKind: message.mediaKind });
    } else {
      activeCastTargetByCaster.delete(message.casterId);
      remoteCastMedia.get(message.casterId)?.parentElement?.remove();
      remoteCastMedia.delete(message.casterId);
    }
    const target = state.items.get(message.targetItemId);
    if (!target) return;
    target.params = {
      ...target.params,
      castActive: message.active,
      castDeviceName: message.deviceName,
      castStationCode: message.stationCode,
      castStationName: message.stationName,
      castNowPlaying: message.title,
      castArtist: message.artist,
      castMediaKind: message.mediaKind,
      castCasterId: message.casterId,
    };
    updateStatus(message.active
      ? `${message.casterNickname} is casting ${message.title || 'media'} to ${target.title} as ${message.stationCode}.`
      : `${message.casterNickname} stopped casting from ${target.title}.`);
  },
  handleWorldPhoneState: (message) => {
    updateStatus(message.message || `World phone ${message.status}.`);
    if (message.status === 'connected') audio.sfxUiConfirm();
    if (message.status === 'failed' || message.status === 'ended') audio.sfxUiCancel();
  },
  handleInteractiveItemLaunch: openInteractiveItem,
  handleGameLaunchInvite: openGameLaunchInvite,
  handleDoorTransitionArrival,
  handleDoorTransitionUseResult,
  handleItemBehaviorIncomingMessage: (message) => itemBehaviorRegistry.onIncomingMessage(message),
  handleItemBehaviorPeerLeft: (senderId) => itemBehaviorRegistry.onPeerLeft(senderId),
  TELEPORT_SOUND_URL,
  TELEPORT_START_SOUND_URL,
  getAudioLayers: () => audioLayers,
  pushChatMessage,
  pushPublicChatMessage,
  pushDirectChatMessage,
  resetChatHistoryForReplay,
  classifySystemMessageSound,
  ACTION_SOUND_URL,
  SYSTEM_SOUND_URLS,
  playSample: (url, gain = 1) => {
    void audio.playSample(url, gain);
  },
  updateStatus,
  audioUiBlip: () => audio.sfxUiBlip(),
  audioUiConfirm: () => audio.sfxUiConfirm(),
  audioUiCancel: () => audio.sfxUiCancel(),
  getCarriedItemId: () => getCarriedItem()?.id ?? null,
  recomputeActiveItemPropertyKeys,
  itemPropertyLabel,
  getItemPropertyValue,
  getItemById: (itemId) => state.items.get(itemId),
  shouldAnnounceItemPropertyEcho: () => Date.now() >= suppressItemPropertyEchoUntilMs,
  playLocateToneAt: (x, y) => {
    const listenerPosition = getListenerPosition();
    audio.sfxLocate({ x: x - listenerPosition.x, y: y - listenerPosition.y });
  },
  resolveIncomingSoundUrl,
  playIncomingItemUseSound: (url, x, y, range) => {
    const listenerPosition = getListenerPosition();
    void audio.playSpatialSample(url, { x, y }, listenerPosition, 1, range ?? HEARING_RADIUS);
    if (/\/sounds\/spin\.ogg(?:[?#].*)?$/i.test(url)) {
      audio.playSpatialWheelFlourish({ x, y }, listenerPosition, range ?? HEARING_RADIUS);
    }
  },
  playClockAnnouncement: (sounds, x, y, range) => {
    if (sounds.length === 0) {
      void audio.playSpatialSample(ACTION_SOUND_URL, { x, y }, getListenerPosition(), 0.72, range ?? HEARING_RADIUS);
      return;
    }
    void clockAnnouncer.playSequence(sounds.map(resolveIncomingSoundUrl), x, y, range);
  },
  handleAuthRequired,
  handleAuthResult,
  handleAuthPermissions,
  handleAdminRolesList,
  handleAdminUsersList,
  handleAdminPlatformOverview,
  handleAdminNotificationsList,
  handleAdminAmbienceCatalog,
  handleAdminActionResult,
  handleNtfyPreferences,
  handleFlexPbxDialingPreferences,
  handleItemTransferTargets,
  isPeerNegotiationReady: () => peerNegotiationReady,
  enqueuePendingSignal: (message) => {
    pendingSignalMessages.push(message);
    if (pendingSignalMessages.length > 500) {
      pendingSignalMessages.splice(0, pendingSignalMessages.length - 500);
    }
  },
});

/** Handles signaling packets with heartbeat/restart metadata before app-level dispatch. */
async function onSignalingMessage(message: IncomingMessage): Promise<void> {
  if (message.type === 'pong' && message.clientSentAt < 0) {
    heartbeatAwaitingPong = false;
    return;
  }
  let restartAnnouncement: string | null = null;
  let connectedAnnouncement: string | null = null;
  let playSelfLoginSound = false;
  if (message.type === 'welcome') {
    autoReconnectEnabled = true;
    clearConnectionRecoveryMarker();
    applyGridBranding(message.serverInfo?.gridName, message.serverInfo?.welcomeMessage);
    const uiAdminActions =
      (message.uiDefinitions as { adminMenu?: { actions?: Array<{ id: string; label: string }> } } | undefined)?.adminMenu?.actions ??
      message.auth?.adminMenuActions;
    authController.applyWelcomeAuth(message.auth, uiAdminActions);
    const incomingInstanceId = String(message.serverInfo?.instanceId ?? '').trim() || null;
    const incomingServerVersion = String(message.serverInfo?.serverVersion ?? '').trim() || 'unknown';
    const expectedClientRevision = String(message.serverInfo?.expectedClientRevision ?? '').trim();
    connectedAnnouncement = reconnectInFlight
      ? `Reconnected to server. Version ${incomingServerVersion}.`
      : `Connected to server. Version ${incomingServerVersion}.`;
    playSelfLoginSound = !reconnectInFlight;
    if (
      !reloadScheduledForVersionMismatch &&
      expectedClientRevision &&
      expectedClientRevision !== APP_CLIENT_REVISION
    ) {
      reloadScheduledForVersionMismatch = true;
      pushChatMessage(`Server expects client ${expectedClientRevision}. Reloading client...`);
      window.setTimeout(() => {
        reloadClientForVersion(expectedClientRevision);
      }, 50);
      return;
    }
    if (activeServerInstanceId && incomingInstanceId && activeServerInstanceId !== incomingInstanceId) {
      restartAnnouncement = 'Server restarted.';
    }
    activeServerInstanceId = incomingInstanceId;
    if (reconnectInFlight || state.running) {
      resetRealtimeStreamsForReconnect();
    }
    signaling.send({ type: 'welcome_ready' });
    startHeartbeat();
  }
  await onAppMessage(message);
  if (message.type === 'welcome') {
    flushQueuedChatMessages();
    // World admission is complete when welcome has been applied. Do not keep
    // the UI at "Joining world" while microphone permission or device setup
    // is waiting on the embedded browser.
    if (connectedAnnouncement) {
      setConnectionStatus(connectedAnnouncement);
      pushChatMessage(connectedAnnouncement);
      connectedAnnouncement = null;
    }
    await setupMediaAfterAuth();
    if (playSelfLoginSound) {
      void audio.playSample(SYSTEM_SOUND_URLS.logon, 1);
    }
  }
  itemBehaviorRegistry.onUseResultMessage(message);
  itemBehaviorRegistry.onWorldUpdate();
  applyConfiguredPeerListenGains();
  if (restartAnnouncement) {
    setConnectionStatus(restartAnnouncement);
    pushChatMessage(restartAnnouncement);
    audio.sfxUiConfirm();
  }
  if (connectedAnnouncement) {
    setConnectionStatus(connectedAnnouncement);
    pushChatMessage(connectedAnnouncement);
  }
}

/** Requests microphone access and initializes local media after successful auth/welcome. */
async function setupMediaAfterAuth(): Promise<void> {
  if (!state.running) return;
  const canProceed = await checkMicPermission();
  if (!canProceed) {
    setConnectionStatus('Connected to the world. Microphone unavailable; navigation and listening still work.');
    await activatePeerNegotiation();
    return;
  }
  try {
    await populateAudioDevices();
    if (dom.audioInputSelect.options.length === 0) {
      setConnectionStatus('Connected to the world. No microphone found; navigation and listening still work.');
      await activatePeerNegotiation();
      return;
    }
    const inputDeviceId = dom.audioInputSelect.value || mediaSession.getPreferredInputDeviceId();
    await setupLocalMedia(inputDeviceId);
  } catch (error) {
    console.error(error);
    setConnectionStatus(describeMediaError(error));
  } finally {
    await activatePeerNegotiation();
    await refreshAudioSubscriptions(true);
    await applyAudioLayerState();
  }
}

/** Toggles local microphone track mute state. */
function toggleMute(): void {
  if (!authController.getVoiceSendAllowed()) {
    updateStatus('Voice send is disabled for this account.');
    audio.sfxUiCancel();
    return;
  }
  state.isMuted = !state.isMuted;
  mediaSession.applyMuteToTrack(state.isMuted);
  updateStatus(state.isMuted ? 'Muted.' : 'Unmuted.');
}

function getCurrentSquareItems(): WorldItem[] {
  return getItemsAtPosition(state.player.x, state.player.y, true);
}

function getUsableItemsOnCurrentSquare(): WorldItem[] {
  return getCurrentSquareItems().filter((item) => item.capabilities.includes('usable'));
}

function getManageableItemsOnCurrentSquare(): WorldItem[] {
  return getCurrentSquareItems().filter((item) => itemManagementOptionsFor(item).length > 0);
}

function canEditCurrentItem(): boolean {
  return getCurrentSquareItems().length > 0 || Boolean(getCarriedItem());
}

function canInspectCurrentItem(): boolean {
  return canEditCurrentItem();
}

function openNicknameEditor(): void {
  state.mode = 'nickname';
  state.nicknameInput = state.player.nickname;
  state.cursorPos = state.player.nickname.length;
  replaceTextOnNextType = true;
  updateStatus(`Nickname edit: ${state.nicknameInput}`);
  audio.sfxUiBlip();
}

function toggleOutputModeCommand(): void {
  outputMode = audio.toggleOutputMode();
  mediaSession.saveOutputMode(outputMode);
  updateStatus(outputMode === 'mono' ? 'Mono output.' : 'Stereo output.');
  audio.sfxUiBlip();
}

function toggleLoopbackCommand(): void {
  const enabled = audio.toggleLoopback();
  updateStatus(enabled ? 'Loopback on.' : 'Loopback off.');
  audio.sfxUiBlip();
}

function adjustMasterVolumeCommand(step: number): void {
  const next = audio.adjustMasterVolume(step);
  persistMasterVolume(next);
  updateStatus(`Master volume ${next}`);
  audio.sfxEffectLevel(next === 50);
}

function openEffectSelectCommand(): void {
  const currentEffect = audio.getCurrentEffect();
  const currentIndex = EFFECT_SEQUENCE.findIndex((effect) => effect.id === currentEffect.id);
  state.effectSelectIndex = currentIndex >= 0 ? currentIndex : 0;
  state.mode = 'effectSelect';
  announceMenuEntry('Effects', EFFECT_SEQUENCE[state.effectSelectIndex].label);
}

function adjustEffectValueCommand(step: number): void {
  const adjusted = audio.adjustCurrentEffectLevel(step);
  if (!adjusted) return;
  persistEffectLevels();
  audio.sfxEffectLevel(adjusted.value === adjusted.defaultValue);
  updateStatus(`${adjusted.label} ${adjusted.value}`);
}

function speakCoordinatesCommand(): void {
  updateStatus(`${formatCoordinate(state.player.x)}, ${formatCoordinate(state.player.y)}`);
  audio.sfxUiBlip();
}

function speakLocationCommand(): void {
  const location = currentLocationName || currentLocationOption()?.name || currentLocationId || 'the grid';
  updateStatus(`You are in ${location}.`);
  audio.sfxUiBlip();
}

function formatLocationOption(location: WorldLocationOption): string {
  const here = location.id === currentLocationId ? ', current location' : '';
  return `${location.name}${here}. ${location.description}`;
}

function listLocationsCommand(): void {
  if (worldLocationOptions.length === 0) {
    updateStatus('No locations available.');
    audio.sfxUiCancel();
    return;
  }
  const currentIndex = worldLocationOptions.findIndex((location) => location.id === currentLocationId);
  state.itemListIndex = Math.max(0, currentIndex);
  state.mode = 'listLocations';
  const locationCount = worldLocationOptions.length;
  announceMenuEntry(`${locationCount} ${locationCount === 1 ? 'location' : 'locations'}`, formatLocationOption(worldLocationOptions[state.itemListIndex]));
}

function openMicGainEditCommand(): void {
  if (!authController.getVoiceSendAllowed()) {
    updateStatus('Voice send is disabled for this account.');
    audio.sfxUiCancel();
    return;
  }
  state.mode = 'micGainEdit';
  state.nicknameInput = formatSteppedNumber(audio.getOutboundInputGain(), MIC_INPUT_GAIN_STEP);
  state.cursorPos = state.nicknameInput.length;
  replaceTextOnNextType = true;
  micGainLoopbackRestoreState = audio.isLoopbackEnabled();
  audio.setLoopbackEnabled(true);
  announceMenuEntry('Microphone gain', state.nicknameInput);
}

function calibrateMicrophoneCommand(): void {
  if (!authController.getVoiceSendAllowed()) {
    updateStatus('Voice send is disabled for this account.');
    audio.sfxUiCancel();
    return;
  }
  void calibrateMicInputGain();
}

function openAdminMenuCommand(): void {
  adminController.openAdminMenu();
}

function useItemCommand(): void {
  if (state.player.posture !== 'standing' && state.player.seatedItemId) {
    const seat = state.items.get(state.player.seatedItemId);
    if (seat) {
      useItem(seat);
      return;
    }
  }
  const focused = getFocusedActionItem();
  if (focused) {
    useItem(focused);
    return;
  }
  const carried = getCarriedItem();
  if (carried) {
    useItem(carried);
    return;
  }
  const usable = getUsableItemsOnCurrentSquare();
  const nearestSeat = getNearestSeatableItem();
  if (nearestSeat && !usable.some((item) => item.id === nearestSeat.id)) {
    useItem(nearestSeat);
    return;
  }
  if (usable.length === 0) {
    updateStatus('No usable items here.');
    audio.sfxUiCancel();
    return;
  }
  if (usable.length === 1) {
    useItem(usable[0]);
    return;
  }
  beginItemSelection('use', usable);
}

function secondaryUseItemCommand(): void {
  const focused = getFocusedActionItem();
  if (focused) {
    secondaryUseItem(focused);
    return;
  }
  const carried = getCarriedItem();
  if (carried) {
    secondaryUseItem(carried);
    return;
  }
  const usable = getUsableItemsOnCurrentSquare();
  if (usable.length === 0) {
    updateStatus('No usable items here.');
    audio.sfxUiCancel();
    return;
  }
  if (usable.length === 1) {
    secondaryUseItem(usable[0]);
    return;
  }
  beginItemSelection('secondaryUse', usable);
}

function radioRemoteControlCommand(action: 'station_next' | 'station_previous' | 'volume_up' | 'volume_down'): void {
  const remote = getCarriedMediaRemote();
  if (!remote) {
    updateStatus('Hold a radio or TV remote first.');
    audio.sfxUiCancel();
    return;
  }
  const labelByAction = {
    station_next: 'next station',
    station_previous: 'previous station',
    volume_up: 'volume up',
    volume_down: 'volume down',
  } as const;
  if (remote.kind !== 'tv' || shouldAnnounceRadioStatus()) {
    updateStatus(`${remote.kind === 'tv' ? 'TV' : 'Radio'} remote ${labelByAction[action]}.`);
  }
  if (action === 'station_next' || action === 'station_previous') {
    audio.sfxDevicePresetButton();
  } else {
    audio.sfxDeviceKeypad();
  }
  signaling.send({ type: 'item_remote_control', itemId: remote.item.id, action });
}

function radioRemoteButtonCommand(
  action: 'station_first' | 'station_last' | 'power_toggle' | 'info',
): void {
  const remote = getCarriedMediaRemote();
  if (!remote || !state.remoteControlsFocused) {
    updateStatus('Press Tab to focus the held remote controls first.');
    audio.sfxUiCancel();
    return;
  }
  signaling.send({ type: 'item_remote_control', itemId: remote.item.id, action });
  audio.sfxDeviceKeypad();
}

let activeCastStream: MediaStream | null = null;
const activeCastTargetByCaster = new Map<string, { itemId: string; mediaKind: 'audio' | 'video' }>();
const remoteCastMedia = new Map<string, HTMLMediaElement>();
let localCastMedia: HTMLMediaElement | null = null;
let localCastMetadata: {
  targetItemId: string;
  mediaKind: 'audio' | 'video';
  deviceName: string;
  stationCode: string;
} | null = null;

function createCastMediaSurface(
  element: HTMLMediaElement,
  label: string,
  position: 'local' | 'remote',
  onStop: () => void,
): HTMLDivElement {
  const surface = document.createElement('div');
  surface.dataset.castSurface = 'true';
  surface.setAttribute('role', 'region');
  surface.setAttribute('aria-label', `${label} controls`);
  Object.assign(surface.style, position === 'local'
    ? {
        position: 'fixed', left: '1rem', bottom: '1rem', width: 'min(24rem, calc(100vw - 2rem))',
        zIndex: '18', background: 'var(--panel, #181818)', padding: '0.5rem',
      }
    : {
        position: 'fixed', right: '1rem', bottom: '1rem', width: 'min(32rem, calc(100vw - 2rem))',
        zIndex: '19', background: 'var(--panel, #181818)', padding: '0.5rem',
      });
  const heading = document.createElement('p');
  heading.textContent = label;
  heading.style.margin = '0 0 0.35rem';
  const stop = document.createElement('button');
  stop.type = 'button';
  stop.textContent = 'Stop cast';
  stop.setAttribute('aria-label', `Stop ${label}`);
  stop.addEventListener('click', onStop);
  element.controls = true;
  element.setAttribute('aria-label', label);
  surface.append(heading, element, stop);
  return surface;
}

function handleRemoteCastStream(casterId: string, stream: MediaStream): void {
  const target = activeCastTargetByCaster.get(casterId);
  if (!target) return;
  remoteCastMedia.get(casterId)?.parentElement?.remove();
  const element = document.createElement(target.mediaKind === 'video' ? 'video' : 'audio');
  element.autoplay = true;
  element.controls = true;
  element.muted = false;
  element.srcObject = stream;
  const label = `Cast from ${casterId}`;
  const surface = createCastMediaSurface(element, label, 'remote', () => {
    element.pause();
    stream.getTracks().forEach((track) => track.stop());
    surface.remove();
    remoteCastMedia.delete(casterId);
    updateStatus(`${label} stopped.`);
  });
  document.body.append(surface);
  remoteCastMedia.set(casterId, element);
  void element.play().catch(() => updateStatus(`Cast received. Press the cast media control to start playback if ${IS_NATIVE_CLIENT ? 'the desktop client' : 'the browser'} blocked autoplay.`));
}

function setLocalCastPlayback(stream: MediaStream | null): void {
  localCastMedia?.parentElement?.remove();
  localCastMedia = null;
  if (!stream) return;
  const hasVideo = stream.getVideoTracks().length > 0;
  const element = document.createElement(hasVideo ? 'video' : 'audio');
  element.autoplay = true;
  element.controls = true;
  element.muted = false;
  element.srcObject = stream;
  const surface = createCastMediaSurface(element, 'Local cast playback', 'local', () => {
    stopLocalCast();
  });
  document.body.append(surface);
  localCastMedia = element;
  void element.play().catch(() => updateStatus('Local cast is ready. Press the local cast playback control to start it.'));
}

function stopLocalCast(): void {
  const metadata = localCastMetadata;
  activeCastStream?.getTracks().forEach((track) => track.stop());
  activeCastStream = null;
  void peerManager.replaceCastStream(null);
  setLocalCastPlayback(null);
  localCastMetadata = null;
  if (metadata) {
    signaling.send({
      type: 'media_cast',
      targetItemId: metadata.targetItemId,
      active: false,
      mediaKind: metadata.mediaKind,
      deviceName: metadata.deviceName,
      stationCode: metadata.stationCode,
      stationName: metadata.deviceName,
      title: '',
      artist: '',
    });
  }
  updateStatus('Local cast stopped.');
}

/** Starts a user-approved local screen/window/tab/app cast and publishes its receiver metadata. */
async function castToNearestDevice(): Promise<void> {
  const candidates = Array.from(state.items.values()).filter((item) => {
    if (item.locationId && item.locationId !== currentLocationId) return false;
    const kind = String(item.params.objectKind ?? '').trim().toLowerCase();
    return item.type === 'radio_station' || kind === 'tv';
  });
  const target = candidates.sort((a, b) => Math.hypot(a.x - state.player.x, a.y - state.player.y) - Math.hypot(b.x - state.player.x, b.y - state.player.y))[0];
  if (!target) {
    updateStatus('There is no TV or radio receiver nearby.');
    audio.sfxUiCancel();
    return;
  }
  activeCastStream?.getTracks().forEach((track) => track.stop());
  try {
    activeCastStream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      } as MediaTrackConstraints,
      systemAudio: 'include',
      preferCurrentTab: false,
    } as DisplayMediaStreamOptions & { systemAudio?: 'include'; preferCurrentTab?: boolean });
    setLocalCastPlayback(activeCastStream);
    await peerManager.replaceCastStream(activeCastStream);
  } catch {
    setLocalCastPlayback(null);
    activeCastStream = null;
    updateStatus('Casting was cancelled, or no local screen, window, tab, or app media source was available.');
    audio.sfxUiCancel();
    return;
  }
  const deviceName = String(activeCastStream.getVideoTracks()[0]?.label || activeCastStream.getAudioTracks()[0]?.label || 'Local media').slice(0, 80);
  const stationCode = `CAST-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
  localCastMetadata = { targetItemId: target.id, mediaKind: target.type === 'radio_station' ? 'audio' : 'video', deviceName, stationCode };
  if (dom.castLocalOnlyToggle.checked) {
    await peerManager.replaceCastStream(null);
    localCastMetadata = null;
    updateStatus(`Playing the cast locally from ${deviceName}; it is not being sent into the world.`);
    return;
  }
  signaling.send({
    type: 'media_cast',
    targetItemId: target.id,
    active: true,
    mediaKind: target.type === 'radio_station' ? 'audio' : 'video',
    deviceName,
    stationCode,
    stationName: deviceName,
    title: 'Local device cast',
    artist: state.player.nickname,
  });
  activeCastStream.getTracks().forEach((track) => track.addEventListener('ended', () => {
    stopLocalCast();
  }, { once: true }));
  updateStatus(`Casting to ${target.title} as ${stationCode}.`);
  audio.sfxUiConfirm();
}

/** Opens the carried in-world phone without exposing PBX credentials to the client. */
function openWorldPhoneCommand(): void {
  const phone = state.carriedItemId ? state.items.get(state.carriedItemId) : undefined;
  if (!phone || String(phone.params.objectKind ?? '').trim().toLowerCase() !== 'phone') {
    updateStatus('Carry your world phone first.');
    audio.sfxUiCancel();
    return;
  }
  const action = (window.prompt('World phone: enter an in-world extension or user first (the primary dialing path). Outbound phone numbers are optional and require server verification; A to answer, H to hang up, C for contacts, or M for audio mode.') || '').trim();
  if (!action) return;
  const upper = action.toUpperCase();
  if (upper === 'A' || upper === 'H' || upper === 'C') {
    signaling.send({ type: 'world_phone', itemId: phone.id, action: upper === 'A' ? 'answer' : upper === 'H' ? 'hangup' : 'contacts' });
    return;
  }
  if (upper === 'M') {
    const mode = (window.prompt('Audio mode: left, right, speaker, or local') || '').trim().toLowerCase();
    const audioMode = mode === 'right' ? 'ear_right' : mode === 'speaker' ? 'speaker' : mode === 'local' ? 'local_only' : 'ear_left';
    signaling.send({ type: 'world_phone', itemId: phone.id, action: 'set_audio_mode', audioMode });
    return;
  }
  signaling.send({ type: 'world_phone', itemId: phone.id, action: 'dial', target: action });
}

function speakUsersCommand(): void {
  const location = currentLocationName || currentLocationOption()?.name || currentLocationId || 'the grid';
  const allUsers = [state.player.nickname, ...Array.from(state.peers.values()).map((peer) => peer.nickname)];
  const label = allUsers.length === 1 ? 'user is' : 'users are';
  updateStatus(`You are in ${location}. ${allUsers.length} connected ${label}: ${allUsers.join(', ')}`);
  audio.sfxUiBlip();
}

function addItemCommand(): void {
  const itemTypeSequence = getItemTypeSequence();
  if (itemTypeSequence.length === 0) {
    updateStatus('No item types available.');
    audio.sfxUiCancel();
    return;
  }
  state.addItemTypeIndex = Math.max(0, Math.min(state.addItemTypeIndex, itemTypeSequence.length - 1));
  state.mode = 'addItem';
  announceMenuEntry('Add item', itemTypeLabel(itemTypeSequence[state.addItemTypeIndex]));
}

function listItemsCommand(): void {
  state.sortedItemIds = Array.from(state.items.entries())
    .filter(([, item]) => !item.carrierId && !isItemQuiet(item))
    .sort(
      (a, b) =>
        Math.hypot(a[1].x - state.player.x, a[1].y - state.player.y) -
        Math.hypot(b[1].x - state.player.x, b[1].y - state.player.y),
    )
    .map(([id]) => id);
  if (state.sortedItemIds.length === 0) {
    updateStatus('No items to list.');
    audio.sfxUiCancel();
    return;
  }
  const preferredIndex = state.focusedItemId ? state.sortedItemIds.indexOf(state.focusedItemId) : -1;
  state.itemListIndex = preferredIndex >= 0 ? preferredIndex : 0;
  state.mode = 'listItems';
  const selected = state.items.get(state.sortedItemIds[state.itemListIndex]);
  if (!selected) {
    audio.sfxUiCancel();
    return;
  }
  const itemCount = state.sortedItemIds.length;
  const itemLabelText = itemCount === 1 ? 'item' : 'items';
  announceMenuEntry(
    `${itemCount} ${itemLabelText}`,
    `${itemLabelWithInteractionHint(selected)}, ${distanceDirectionPhrase(state.player.x, state.player.y, selected.x, selected.y)}, ${selected.x}, ${selected.y}`,
  );
}

function locateNearestItemCommand(): void {
  const nearest = getNearestItem(state);
  if (!nearest.itemId) {
    updateStatus('No items to locate.');
    audio.sfxUiCancel();
    return;
  }
  const item = state.items.get(nearest.itemId);
  if (!item) return;
  focusItemForAction(item);
  audio.sfxLocate({ x: item.x - state.player.x, y: item.y - state.player.y }, HEARING_RADIUS);
  updateStatus(`${itemLabelWithInteractionHint(item)}, ${distanceDirectionPhrase(state.player.x, state.player.y, item.x, item.y)}, ${item.x}, ${item.y}`);
}

/** Plays a gentle proximity beacon for nearby discoverable items when enabled. */
function updateItemBeacon(): void {
  if (!audioLayers.item) return;
  const nowMs = Date.now();
  const tileKey = `${Math.round(state.player.x)},${Math.round(state.player.y)}`;
  let nearest: { item: WorldItem; distance: number } | null = null;
  for (const item of state.items.values()) {
    if (!shouldBeaconItem(item)) continue;
    const distance = Math.hypot(item.x - state.player.x, item.y - state.player.y);
    if (distance > ITEM_BEACON_RADIUS) continue;
    if (!nearest || distance < nearest.distance) {
      nearest = { item, distance };
    }
  }
  if (!nearest) {
    lastItemBeaconTile = tileKey;
    lastItemBeaconItemId = '';
    return;
  }
  const required = isItemAnnouncementRequired(nearest.item);
  const interval = required ? Math.floor(ITEM_BEACON_INTERVAL_MS * 0.75) : ITEM_BEACON_INTERVAL_MS;
  if (
    lastItemBeaconTile === tileKey &&
    lastItemBeaconItemId === nearest.item.id &&
    nowMs - lastItemBeaconAtMs < interval
  ) {
    return;
  }
  lastItemBeaconTile = tileKey;
  lastItemBeaconItemId = nearest.item.id;
  lastItemBeaconAtMs = nowMs;
  audio.sfxItemBeacon({ x: nearest.item.x - state.player.x, y: nearest.item.y - state.player.y }, ITEM_BEACON_RADIUS);
}

function pickupDropItemCommand(moveAttached = false): void {
  const carriedItems = getCarriedItems();
  const carriedSurface = carriedItems.find((item) => item.type === 'furniture') ?? null;
  const carried = carriedSurface ?? getCarriedItem();
  if (carried) {
    const surface = isSurfacePlaceableItem(carried) ? getAutomaticPlacementSurface() : null;
    if (surface && !moveAttached) {
      updateStatus(`You place ${itemLabel(carried)} on ${itemLabel(surface)}.`);
      focusItemForAction(surface);
      signaling.send({
        type: 'item_drop',
        itemId: carried.id,
        x: surface.x,
        y: surface.y,
        targetSurfaceId: surface.id,
      });
      return;
    }
    focusItemForAction(carried);
    signaling.send({
      type: 'item_drop',
      itemId: carried.id,
      x: state.player.x,
      y: state.player.y,
      moveAttached: moveAttached || carried.type === 'furniture',
    });
    return;
  }
  const squareItems = getCurrentSquareItems();
  if (squareItems.length === 0) {
    updateStatus('No items to pick up.');
    audio.sfxUiCancel();
    return;
  }
  const focused = getFocusedActionItem();
  const pickupTarget = focused && squareItems.some((item) => item.id === focused.id)
    ? focused
    : squareItems.length === 1
      ? squareItems[0]
      : null;
  if (pickupTarget) {
    focusItemForAction(pickupTarget);
    signaling.send({
      type: 'item_pickup',
      itemId: pickupTarget.id,
      moveAttached: moveAttached || pickupTarget.type === 'furniture',
    });
    return;
  }
  beginItemSelection('pickup', squareItems);
}

function pickupDropAttachedItemsCommand(): void {
  pickupDropItemCommand(true);
}

function openItemManagementCommand(): void {
  const squareItems = getCurrentSquareItems();
  if (squareItems.length === 0) {
    updateStatus('No items to manage on this square.');
    audio.sfxUiCancel();
    return;
  }
  const manageable = squareItems.filter((item) => itemManagementOptionsFor(item).length > 0);
  if (manageable.length === 0) {
    updateStatus('No permitted item management actions here.');
    audio.sfxUiCancel();
    return;
  }
  if (manageable.length === 1) {
    beginItemManagement(manageable[0]);
    return;
  }
  beginItemSelection('manage', manageable);
}

function editItemCommand(): void {
  const squareItems = getCurrentSquareItems();
  const carried = getCarriedItem();
  if (squareItems.length === 0) {
    if (!carried) {
      updateStatus('No editable item here.');
      audio.sfxUiCancel();
      return;
    }
    beginItemProperties(carried);
    return;
  }
  if (squareItems.length === 1) {
    beginItemProperties(squareItems[0]);
    return;
  }
  beginItemSelection('edit', squareItems);
}

function inspectItemCommand(): void {
  const squareItems = getCurrentSquareItems();
  const carried = getCarriedItem();
  if (squareItems.length === 0) {
    if (!carried) {
      updateStatus('No item to inspect.');
      audio.sfxUiCancel();
      return;
    }
    beginItemProperties(carried, true);
    return;
  }
  if (squareItems.length === 1) {
    beginItemProperties(squareItems[0], true);
    return;
  }
  beginItemSelection('inspect', squareItems);
}

function pingServerCommand(): void {
  signaling.send({ type: 'ping', clientSentAt: Date.now() });
}

function listUsersCommand(): void {
  if (state.peers.size === 0) {
    updateStatus('No users to list.');
    audio.sfxUiCancel();
    return;
  }
  state.sortedPeerIds = Array.from(state.peers.entries())
    .sort((a, b) => a[1].nickname.localeCompare(b[1].nickname, undefined, { sensitivity: 'base' }))
    .map(([id]) => id);
  state.listIndex = 0;
  state.mode = 'listUsers';
  const first = state.peers.get(state.sortedPeerIds[0]);
  if (!first) {
    audio.sfxUiCancel();
    return;
  }
  const userCount = state.sortedPeerIds.length;
  const userLabelText = userCount === 1 ? 'user' : 'users';
  const gainPhrase = `volume ${formatSteppedNumber(getPeerListenGainForNickname(first.nickname), MIC_INPUT_GAIN_STEP)}`;
  announceMenuEntry(`${userCount} ${userLabelText}`, `${first.nickname}, ${gainPhrase}, ${peerLocationPhrase(first)}`);
}

function locateNearestUserCommand(): void {
  const nearest = getNearestPeer(state);
  if (!nearest.peerId) {
    updateStatus('No users to locate.');
    audio.sfxUiCancel();
    return;
  }
  const peer = state.peers.get(nearest.peerId);
  if (!peer) return;
  if ((peer.locationId || currentLocationId) === currentLocationId) {
    audio.sfxLocate({ x: peer.x - state.player.x, y: peer.y - state.player.y });
  } else {
    audio.sfxUiBlip();
  }
  updateStatus(`${peer.nickname}, ${peerLocationPhrase(peer)}`);
}

function openHelpCommand(): void {
  openHelpViewer(mainHelpViewerLines);
}

function openChatCommand(): void {
  state.mode = 'chat';
  state.nicknameInput = '';
  state.cursorPos = 0;
  state.directMessageTargetId = null;
  state.directMessageTargetName = null;
  replaceTextOnNextType = false;
  updateStatus('Room chat.');
  audio.sfxUiBlip();
}

function getSelectedOrNearestPeer(): PeerState | null {
  const selectedPeerId =
    state.mode === 'listUsers' && state.sortedPeerIds.length > 0
      ? state.sortedPeerIds[state.listIndex] || null
      : null;
  const selectedPeer = selectedPeerId ? state.peers.get(selectedPeerId) : null;
  if (selectedPeer) {
    return selectedPeer;
  }
  const nearest = getNearestPeer(state);
  const nearestPeer = nearest.peerId ? state.peers.get(nearest.peerId) : null;
  return nearestPeer ?? null;
}

function openDirectMessageCommand(): void {
  const focusedTarget = focusedConversationPeerId ? state.peers.get(focusedConversationPeerId) ?? null : null;
  const target = focusedTarget ?? getSelectedOrNearestPeer();
  if (!target) {
    updateStatus('No user to message.');
    audio.sfxUiCancel();
    return;
  }
  state.mode = 'chat';
  state.nicknameInput = '';
  state.cursorPos = 0;
  state.directMessageTargetId = target.id;
  state.directMessageTargetName = target.nickname;
  focusedConversationPeerId = target.id;
  focusedConversationPeerName = target.nickname;
  replaceTextOnNextType = false;
  updateStatus(`Direct message to ${target.nickname}.`);
  audio.sfxUiBlip();
}

function formatUserActionOption(option: UserActionOption, target: PeerState): string {
  return `${option.label} ${target.nickname}, ${peerLocationPhrase(target)}`;
}

function availableUserActionOptions(target: PeerState): UserActionOption[] {
  return USER_ACTION_OPTIONS.filter((option) => {
    if (option.id !== 'release_hand') return true;
    return state.player.handHeldById === target.id;
  });
}

function getUserActionTarget(): PeerState | null {
  if (userActionTargetId) {
    const target = state.peers.get(userActionTargetId);
    if (target) return target;
  }
  return getSelectedOrNearestPeer();
}

function openUserActionMenuCommand(): void {
  const focused = getFocusedActionItem();
  if (focused) {
    secondaryUseItem(focused);
    return;
  }
  const target = getSelectedOrNearestPeer();
  if (!target) {
    secondaryUseItemCommand();
    return;
  }
  userActionTargetId = target.id;
  userActionMenuIndex = 0;
  state.mode = 'userActionMenu';
  const options = availableUserActionOptions(target);
  announceMenuEntry('User actions', formatUserActionOption(options[userActionMenuIndex] ?? options[0], target));
}

function allowNearbyUserCommand(): void {
  const target = getSelectedOrNearestPeer();
  if (!target) {
    updateStatus('No nearby user to allow into the house.');
    audio.sfxUiCancel();
    return;
  }
  signaling.send({ type: 'chat_message', message: `/allow ${target.nickname}` });
  updateStatus(`Requesting entry approval for ${target.nickname}.`);
}

function runUserAction(option: UserActionOption, target: PeerState): void {
  state.mode = 'normal';
  userActionTargetId = null;
  if (option.id === 'walk_to') {
    signaling.send({ type: 'chat_message', message: `/walkto ${target.nickname}` });
    return;
  }
  if (option.id === 'teleport_to') {
    signaling.send({ type: 'chat_message', message: `/teleportto ${target.nickname}` });
    return;
  }
  if (option.id === 'direct_message') {
    state.mode = 'chat';
    state.nicknameInput = '';
    state.cursorPos = 0;
    state.directMessageTargetId = target.id;
    state.directMessageTargetName = target.nickname;
    replaceTextOnNextType = false;
    updateStatus(`Direct message to ${target.nickname}.`);
    audio.sfxUiBlip();
    return;
  }
  signaling.send({ type: 'user_action', actionId: option.id, targetId: target.id });
}

function runDynamicUserAction(target: PeerState): void {
  const candidates = availableUserActionOptions(target).filter((option) => DYNAMIC_USER_ACTION_IDS.includes(option.id));
  const selected = candidates[Math.floor(Math.random() * candidates.length)] || USER_ACTION_OPTIONS[0];
  runUserAction(selected, target);
}

function escapeCommand(): void {
  if (remoteControlsAreFocused()) {
    state.remoteControlsFocused = false;
    updateStatus('Remote controls released. Arrow keys move again; press Tab to refocus the remote.');
    audio.sfxUiCancel();
    return;
  }
  if (IS_NATIVE_CLIENT) {
    pendingEscapeDisconnect = false;
    updateStatus('Escape does not disconnect the desktop client. Use File, Sign out or Exit.');
    audio.sfxUiCancel();
    return;
  }
  if (pendingEscapeDisconnect) {
    pendingEscapeDisconnect = false;
    disconnect();
    return;
  }
  pendingEscapeDisconnect = true;
  updateStatus('Press Escape again to disconnect.');
  audio.sfxUiCancel();
}

const mainModeCommandHandlers: Record<MainModeCommand, () => void> = {
  editNickname: openNicknameEditor,
  openNotifications: () => adminController.openNotifications(),
  toggleMute,
  toggleOutputMode: toggleOutputModeCommand,
  toggleLoopback: toggleLoopbackCommand,
  toggleVoiceLayer: () => toggleAudioLayer('voice'),
  toggleItemLayer: () => toggleAudioLayer('item'),
  toggleMediaLayer: () => toggleAudioLayer('media'),
  toggleWorldLayer: () => toggleAudioLayer('world'),
  cycleAnnouncementMode: cycleAnnouncementModeCommand,
  toggleItemBeacons: toggleItemBeaconsCommand,
  masterVolumeUp: () => adjustMasterVolumeCommand(5),
  masterVolumeDown: () => adjustMasterVolumeCommand(-5),
  openEffectSelect: openEffectSelectCommand,
  effectValueUp: () => adjustEffectValueCommand(5),
  effectValueDown: () => adjustEffectValueCommand(-5),
  speakCoordinates: speakCoordinatesCommand,
  speakLocation: speakLocationCommand,
  openMicGainEdit: openMicGainEditCommand,
  calibrateMicrophone: calibrateMicrophoneCommand,
  cycleFocusedItem: () => cycleFocusedItemCommand(false),
  useItem: useItemCommand,
  secondaryUseItem: secondaryUseItemCommand,
  radioRemoteStationNext: () => radioRemoteControlCommand('station_next'),
  radioRemoteStationPrevious: () => radioRemoteControlCommand('station_previous'),
  radioRemoteStationFirst: () => radioRemoteButtonCommand('station_first'),
  radioRemoteStationLast: () => radioRemoteButtonCommand('station_last'),
  radioRemoteVolumeUp: () => radioRemoteControlCommand('volume_up'),
  radioRemoteVolumeDown: () => radioRemoteControlCommand('volume_down'),
  radioRemotePowerToggle: () => radioRemoteButtonCommand('power_toggle'),
  radioRemoteInfo: () => radioRemoteButtonCommand('info'),
  castToDevice: () => void castToNearestDevice(),
  openWorldPhone: openWorldPhoneCommand,
  openUserActionMenu: openUserActionMenuCommand,
  allowNearbyUser: allowNearbyUserCommand,
  interactItem: interactItemCommand,
  pickupSurfaceItem: pickupSurfaceItemCommand,
  describeSurface: describeSurfaceCommand,
  speakUsers: speakUsersCommand,
  addItem: addItemCommand,
  locateNearestItem: locateNearestItemCommand,
  listItems: listItemsCommand,
  pickupDropItem: pickupDropItemCommand,
  pickupDropAttachedItems: pickupDropAttachedItemsCommand,
  openItemManagement: openItemManagementCommand,
  editItem: editItemCommand,
  inspectItem: inspectItemCommand,
  pingServer: pingServerCommand,
  locateNearestUser: locateNearestUserCommand,
  listUsers: listUsersCommand,
  listLocations: listLocationsCommand,
  openHelp: openHelpCommand,
  openChat: openChatCommand,
  openDirectMessage: openDirectMessageCommand,
  openAdminMenu: openAdminMenuCommand,
  chatPrev: () => navigateChatBuffer('prev'),
  chatNext: () => navigateChatBuffer('next'),
  chatFirst: () => navigateChatBuffer('first'),
  chatLast: () => navigateChatBuffer('last'),
  escape: escapeCommand,
};

function getAvailableCommandPaletteEntriesForMode(mode: GameMode): Array<CommandDescriptor & { run: () => void | Promise<void> }> {
  if (mode === 'normal') {
    const descriptors = getAvailableMainModeCommands({
      voiceSendAllowed: authController.getVoiceSendAllowed(),
      mainHelpAvailable: mainHelpViewerLines.length > 0,
      hasAdminActions: getAvailableAdminActions().length > 0,
      itemTypeCount: getItemTypeSequence().length,
      visibleItemCount: Array.from(state.items.values()).filter((item) => !item.carrierId).length,
      userCount: state.peers.size,
      hasDirectMessageTarget: state.peers.size > 0,
      locationCount: worldLocationOptions.length,
      chatMessageCount: messageBuffer.length,
      hasCarriedItem: Boolean(getCarriedItem()),
      hasCarriedRadioRemote: Boolean(getCarriedMediaRemote()),
      squareItemCount: getCurrentSquareItems().length,
      usableItemCount: getUsableItemsOnCurrentSquare().length,
      manageableItemCount: getManageableItemsOnCurrentSquare().length,
      hasEditableItemTarget: canEditCurrentItem(),
      hasInspectableItemTarget: canInspectCurrentItem(),
      hasFocusedUserTarget: state.peers.size > 0 || Boolean(getCarriedItem()) || getUsableItemsOnCurrentSquare().length > 0,
    });
    return descriptors.map((descriptor) => ({
      ...descriptor,
      label: getServerMainModeCommandMetadata(descriptor.id)?.label ?? descriptor.label,
      tooltip: getServerMainModeCommandMetadata(descriptor.id)?.tooltip ?? descriptor.tooltip,
      run: mainModeCommandHandlers[descriptor.id],
    }));
  }
  if (itemBehaviorRegistry.canOpenModeCommandPalette(mode)) {
    return itemBehaviorRegistry.getModeCommands(mode).map((descriptor) => ({
      ...descriptor,
      run: () => {
        itemBehaviorRegistry.runModeCommand(mode, descriptor.id);
      },
    }));
  }
  return [];
}

function canOpenCommandPaletteInMode(mode: GameMode): boolean {
  return mode === 'normal' || mode === 'commandPalette' || itemBehaviorRegistry.canOpenModeCommandPalette(mode);
}

function openCommandPalette(): void {
  const sourceMode = state.mode;
  if (sourceMode === 'commandPalette') {
    return;
  }
  const commands = getAvailableCommandPaletteEntriesForMode(sourceMode);
  if (commands.length === 0) {
    updateStatus('No commands available in this mode.');
    audio.sfxUiCancel();
    return;
  }
  commandPaletteCommands.splice(0, commandPaletteCommands.length, ...commands);
  commandPaletteIndex = 0;
  commandPaletteReturnMode = sourceMode;
  state.mode = 'commandPalette';
  announceMenuEntry('Commands', formatCommandMenuLabel(commandPaletteCommands[0]));
}

function executeCommandPaletteSelection(): void {
  const selected = commandPaletteCommands[commandPaletteIndex];
  if (!selected) return;
  state.mode = commandPaletteReturnMode;
  void selected.run();
}

/** Handles command-mode keybindings while in main gameplay mode. */
function handleNormalModeInput(code: string, shiftKey: boolean, ctrlKey: boolean): void {
  if (code !== 'Escape' && pendingEscapeDisconnect) {
    pendingEscapeDisconnect = false;
  }
  if (ctrlKey && shiftKey && (code === 'KeyJ' || code === 'KeyK')) {
    moveFocusedSurfaceItemCommand(code === 'KeyJ' ? 'left' : 'right');
    return;
  }
  if (ctrlKey && (code === 'Comma' || code === 'Period')) {
    if (shiftKey) cycleFocusedConversation(code === 'Comma' ? 'prev' : 'next');
    else navigateFocusedConversation(code === 'Comma' ? 'prev' : 'next');
    return;
  }
  if (ctrlKey && (code === 'BracketLeft' || code === 'BracketRight')) {
    navigateFilteredMessageBuffer(shiftKey ? 'system' : 'public', code === 'BracketLeft' ? 'prev' : 'next');
    return;
  }
  if (getCarriedMediaRemote()) {
    if (code === 'Tab') {
      if (shiftKey) {
        cycleFocusedItemCommand(true);
        state.remoteControlsFocused = Boolean(getCarriedMediaRemote());
      } else {
        const remote = getCarriedItems().find((item) => isRadioRemoteItem(item) || isTvRemoteItem(item));
        if (remote) {
          state.focusedItemId = remote.id;
          state.remoteControlsFocused = true;
          updateStatus(`Focused ${itemLabel(remote)} controls.`);
          audio.sfxUiBlip();
        }
      }
      return;
    }
    if (code === 'Escape') {
      escapeCommand();
      return;
    }
    if (!state.remoteControlsFocused) {
      return;
    }
    if (code === 'Home') {
      radioRemoteButtonCommand('station_first');
      return;
    }
    if (code === 'End') {
      radioRemoteButtonCommand('station_last');
      return;
    }
    if (code === 'KeyO') {
      radioRemoteButtonCommand('power_toggle');
      return;
    }
    if (code === 'KeyI') {
      radioRemoteButtonCommand('info');
      return;
    }
    if (code === 'KeyC' || (shiftKey && code === 'KeyK')) {
      void castToNearestDevice();
      return;
    }
    if (code === 'Space') {
      radioRemoteControlCommand(shiftKey ? 'station_previous' : 'station_next');
      return;
    }
    if (code === 'ArrowRight') {
      radioRemoteControlCommand('station_next');
      return;
    }
    if (code === 'ArrowLeft') {
      radioRemoteControlCommand('station_previous');
      return;
    }
    if (code === 'ArrowUp') {
      radioRemoteControlCommand('volume_up');
      return;
    }
    if (code === 'ArrowDown') {
      radioRemoteControlCommand('volume_down');
      return;
    }
    if (code === 'Period') {
      radioRemoteControlCommand('station_next');
      return;
    }
    if (code === 'Comma') {
      radioRemoteControlCommand('station_previous');
      return;
    }
  }
  if (code === 'Tab') {
    if (shiftKey) {
      cycleFocusedItemCommand(true);
      state.remoteControlsFocused = Boolean(getCarriedMediaRemote());
      return;
    }
    const remote = getCarriedItems().find((item) => isRadioRemoteItem(item) || isTvRemoteItem(item));
    if (remote) {
      state.focusedItemId = remote.id;
      state.remoteControlsFocused = true;
      updateStatus(`Focused ${itemLabel(remote)} controls.`);
      audio.sfxUiBlip();
      return;
    }
    cycleFocusedItemCommand(false);
    return;
  }
  const command = resolveMainModeCommand(code, shiftKey, ctrlKey, input.source === 'native' ? 'desktop' : 'web');
  if (!command) return;
  mainModeCommandHandlers[command]();
}

/** Handles linear help viewer navigation and exit keys. */
function handleHelpViewModeInput(code: string): void {
  if (helpViewerLines.length === 0) {
    state.mode = 'normal';
    updateStatus('Help unavailable.');
    audio.sfxUiCancel();
    return;
  }

  if (code === 'ArrowDown') {
    helpViewerIndex = Math.min(helpViewerLines.length - 1, helpViewerIndex + 1);
    updateStatus(helpViewerLines[helpViewerIndex]);
    audio.sfxUiBlip();
    return;
  }
  if (code === 'ArrowUp') {
    helpViewerIndex = Math.max(0, helpViewerIndex - 1);
    updateStatus(helpViewerLines[helpViewerIndex]);
    audio.sfxUiBlip();
    return;
  }
  if (code === 'Home') {
    helpViewerIndex = 0;
    updateStatus(helpViewerLines[helpViewerIndex]);
    audio.sfxUiBlip();
    return;
  }
  if (code === 'End') {
    helpViewerIndex = helpViewerLines.length - 1;
    updateStatus(helpViewerLines[helpViewerIndex]);
    audio.sfxUiBlip();
    return;
  }
  if (code === 'Escape') {
    state.mode = helpViewerReturnMode;
    updateStatus('Closed help.');
    audio.sfxUiCancel();
  }
}

/** Handles command palette list navigation, tooltips, and execution. */
function handleCommandPaletteModeInput(code: string, key: string): void {
  if (commandPaletteCommands.length === 0) {
    state.mode = commandPaletteReturnMode;
    updateStatus('No commands available.');
    audio.sfxUiCancel();
    return;
  }
  const control = handleListControlKey(code, key, commandPaletteCommands, commandPaletteIndex, (entry) => formatCommandMenuLabel(entry));
  if (control.type === 'move') {
    commandPaletteIndex = control.index;
    updateStatus(formatCommandMenuLabel(commandPaletteCommands[commandPaletteIndex]));
    audio.sfxUiBlip();
    return;
  }
  if (code === 'Space') {
    const selected = commandPaletteCommands[commandPaletteIndex];
    if (!selected) return;
    updateStatus(selected.tooltip || 'No tooltip available.');
    audio.sfxUiBlip();
    return;
  }
  if (control.type === 'select') {
    executeCommandPaletteSelection();
    return;
  }
  if (control.type === 'cancel') {
    state.mode = commandPaletteReturnMode;
    updateStatus('Closed commands.');
    audio.sfxUiCancel();
  }
}

/** Handles chat compose mode including submit/cancel and inline editing keys. */
function handleChatModeInput(code: string, key: string, ctrlKey: boolean): void {
  const editAction = getEditSessionAction(code);
  if (editAction === 'submit') {
    const rawMessage = state.nicknameInput;
    if (rawMessage.trim().length > 0) {
      sendOrQueueChatMessage(rawMessage);
      state.mode = 'normal';
      state.nicknameInput = '';
      state.cursorPos = 0;
      state.directMessageTargetId = null;
      state.directMessageTargetName = null;
      if (!/^\/me(?:\s|$)/i.test(rawMessage)) {
        audio.sfxUiConfirm();
      }
    } else {
      state.mode = 'normal';
      audio.sfxUiCancel();
      updateStatus('Cancelled.');
    }
    return;
  }

  if (editAction === 'cancel') {
    state.mode = 'normal';
    state.nicknameInput = '';
    state.cursorPos = 0;
    state.directMessageTargetId = null;
    state.directMessageTargetName = null;
    updateStatus('Cancelled.');
    audio.sfxUiCancel();
    return;
  }

  applyTextInputEdit(code, key, 500, ctrlKey);
}

/** Handles direct microphone gain editing mode with keyboard stepping and validation. */
function handleMicGainEditModeInput(code: string, key: string, ctrlKey: boolean): void {
  if (code === 'ArrowUp' || code === 'ArrowDown' || code === 'PageUp' || code === 'PageDown') {
    const raw = Number(state.nicknameInput.trim());
    const base = Number.isFinite(raw) ? raw : audio.getOutboundInputGain();
    const multiplier = code === 'PageUp' || code === 'PageDown' ? 10 : 1;
    const delta = (code === 'ArrowUp' || code === 'PageUp' ? MIC_INPUT_GAIN_STEP : -MIC_INPUT_GAIN_STEP) * multiplier;
    const attempted = snapNumberToStep(base + delta, MIC_INPUT_GAIN_STEP, MIC_CALIBRATION_MIN_GAIN);
    const next = clampMicInputGain(attempted);
    state.nicknameInput = formatSteppedNumber(next, MIC_INPUT_GAIN_STEP);
    state.cursorPos = state.nicknameInput.length;
    replaceTextOnNextType = false;
    audio.setOutboundInputGain(next);
    updateStatus(state.nicknameInput);
    if (Math.abs(next - base) < 1e-9 || Math.abs(next - attempted) > 1e-9) {
      audio.sfxUiCancel();
    } else {
      audio.sfxUiBlip();
    }
    return;
  }

  const editAction = getEditSessionAction(code);
  if (editAction === 'submit') {
    const value = Number(state.nicknameInput.trim());
    if (!Number.isFinite(value)) {
      updateStatus(`Volume must be between ${MIC_CALIBRATION_MIN_GAIN} and ${MIC_CALIBRATION_MAX_GAIN}.`);
      audio.sfxUiCancel();
      return;
    }
    const snapped = snapNumberToStep(value, MIC_INPUT_GAIN_STEP, MIC_CALIBRATION_MIN_GAIN);
    if (snapped < MIC_CALIBRATION_MIN_GAIN || snapped > MIC_CALIBRATION_MAX_GAIN) {
      updateStatus(`Volume must be between ${MIC_CALIBRATION_MIN_GAIN} and ${MIC_CALIBRATION_MAX_GAIN}.`);
      audio.sfxUiCancel();
      return;
    }
    const applied = audio.setOutboundInputGain(snapped);
    persistMicInputGain(applied);
    state.mode = 'normal';
    replaceTextOnNextType = false;
    restoreLoopbackAfterMicGainEdit();
    updateStatus(`Microphone gain set to ${formatSteppedNumber(applied, MIC_INPUT_GAIN_STEP)}.`);
    audio.sfxUiConfirm();
    return;
  }

  if (editAction === 'cancel') {
    state.mode = 'normal';
    replaceTextOnNextType = false;
    restoreLoopbackAfterMicGainEdit();
    updateStatus('Cancelled.');
    audio.sfxUiCancel();
    return;
  }

  applyTextInputEdit(code, key, 8, ctrlKey, true);
}

/** Handles effect menu list navigation and selection. */
function handleEffectSelectModeInput(code: string, key: string): void {
  const control = handleListControlKey(code, key, EFFECT_SEQUENCE, state.effectSelectIndex, (effect) => effect.label);
  if (control.type === 'move') {
    state.effectSelectIndex = control.index;
    updateStatus(EFFECT_SEQUENCE[state.effectSelectIndex].label);
    audio.sfxUiBlip();
    return;
  }

  if (control.type === 'select') {
    const selected = EFFECT_SEQUENCE[state.effectSelectIndex];
    const effect = audio.setOutboundEffect(selected.id);
    state.mode = 'normal';
    updateStatus(effect.label);
    audio.sfxUiBlip();
    return;
  }

  if (control.type === 'cancel') {
    state.mode = 'normal';
    updateStatus('Cancelled.');
    audio.sfxUiCancel();
  }
}

/** Handles list navigation for nearby/known users and teleport-on-select. */
function handleListModeInput(code: string, key: string): void {
  if (state.sortedPeerIds.length === 0) {
    state.mode = 'normal';
    return;
  }

  if (code === 'ArrowLeft' || code === 'ArrowRight') {
    const peerId = state.sortedPeerIds[state.listIndex];
    const entry = state.peers.get(peerId);
    if (!entry) return;
    const current = getPeerListenGainForNickname(entry.nickname);
    const delta = code === 'ArrowRight' ? MIC_INPUT_GAIN_STEP : -MIC_INPUT_GAIN_STEP;
    const attempted = snapNumberToStep(current + delta, MIC_INPUT_GAIN_STEP, MIC_CALIBRATION_MIN_GAIN);
    const next = clampMicInputGain(attempted);
    setPeerListenGainForNickname(entry.nickname, next);
    peerManager.setPeerListenGain(peerId, next);
    updateStatus(`${entry.nickname} volume ${formatSteppedNumber(next, MIC_INPUT_GAIN_STEP)}.`);
    if (Math.abs(next - current) < 1e-9 || Math.abs(next - attempted) > 1e-9) {
      audio.sfxUiCancel();
    } else {
      audio.sfxUiBlip();
    }
    return;
  }

  const control = handleListControlKey(
    code,
    key,
    state.sortedPeerIds,
    state.listIndex,
    (peerId) => state.peers.get(peerId)?.nickname ?? '',
  );
  if (control.type === 'move') {
    state.listIndex = control.index;
    const entry = state.peers.get(state.sortedPeerIds[state.listIndex]);
    if (!entry) return;
    const gainPhrase = `volume ${formatSteppedNumber(getPeerListenGainForNickname(entry.nickname), MIC_INPUT_GAIN_STEP)}`;
    updateStatus(`${entry.nickname}, ${gainPhrase}, ${peerLocationPhrase(entry)}`);
    if (control.reason === 'initial') {
      audio.sfxUiBlip();
    }
    return;
  }

  if (control.type === 'select') {
    const entry = state.peers.get(state.sortedPeerIds[state.listIndex]);
    if (!entry) return;
    const entryLocationId = entry.locationId || currentLocationId;
    if (entryLocationId !== currentLocationId) {
      updateStatus(`${entry.nickname} is ${peerLocationPhrase(entry)}.`);
      audio.sfxUiBlip();
      return;
    }
    if (state.player.x === entry.x && state.player.y === entry.y) {
      updateStatus('Already here.');
      return;
    }
    state.mode = 'normal';
    startTeleportTo(entry.x, entry.y, `Moved to ${entry.nickname}.`);
    return;
  }

  if (control.type === 'cancel') {
    state.mode = 'normal';
    updateStatus('Exit list mode.');
    audio.sfxUiCancel();
  }
}

/** Handles contextual actions toward the selected, focused, or nearest user. */
function handleUserActionMenuModeInput(code: string, key: string): void {
  const target = getUserActionTarget();
  if (!target) {
    state.mode = 'normal';
    userActionTargetId = null;
    updateStatus('User no longer available.');
    audio.sfxUiCancel();
    return;
  }

  const options = availableUserActionOptions(target);
  if (userActionMenuIndex >= options.length) {
    userActionMenuIndex = Math.max(0, options.length - 1);
  }
  const control = handleListControlKey(code, key, options, userActionMenuIndex, (option) =>
    formatUserActionOption(option, target),
  );
  if (control.type === 'move') {
    userActionMenuIndex = control.index;
    updateStatus(formatUserActionOption(options[userActionMenuIndex], target));
    if (control.reason === 'initial') {
      audio.sfxUiBlip();
    }
    return;
  }
  if (code === 'Space') {
    runDynamicUserAction(target);
    return;
  }
  if (control.type === 'select') {
    const selected = options[userActionMenuIndex];
    if (!selected) return;
    runUserAction(selected, target);
    return;
  }
  if (control.type === 'cancel') {
    state.mode = 'normal';
    userActionTargetId = null;
    updateStatus('Exit user actions.');
    audio.sfxUiCancel();
  }
}

/** Handles item list navigation and teleport-on-select. */
function handleListItemsModeInput(code: string, key: string): void {
  if (state.sortedItemIds.length === 0) {
    state.mode = 'normal';
    return;
  }

  const control = handleListControlKey(code, key, state.sortedItemIds, state.itemListIndex, (itemId) => {
    const item = state.items.get(itemId);
    return item ? itemLabel(item) : '';
  });
  if (control.type === 'move') {
    state.itemListIndex = control.index;
    const item = state.items.get(state.sortedItemIds[state.itemListIndex]);
    if (!item) return;
    updateStatus(
      `${itemLabel(item)}, ${distanceDirectionPhrase(state.player.x, state.player.y, item.x, item.y)}, ${item.x}, ${item.y}`,
    );
    if (control.reason === 'initial') {
      audio.sfxUiBlip();
    }
    return;
  }
  if (control.type === 'select') {
    const item = state.items.get(state.sortedItemIds[state.itemListIndex]);
    if (!item) return;
    focusItemForAction(item);
    if (state.player.x === item.x && state.player.y === item.y) {
      updateStatus('Already here.');
      return;
    }
    state.mode = 'normal';
    startTeleportTo(item.x, item.y, `Moved to ${itemLabel(item)}.`);
    return;
  }
  if (control.type === 'cancel') {
    state.mode = 'normal';
    updateStatus('Exit item list mode.');
    audio.sfxUiCancel();
  }
}

/** Handles location list navigation and travel-on-select. */
function handleLocationListModeInput(code: string, key: string): void {
  if (worldLocationOptions.length === 0) {
    state.mode = 'normal';
    return;
  }

  const control = handleListControlKey(code, key, worldLocationOptions, state.itemListIndex, (location) => location.name);
  if (control.type === 'move') {
    state.itemListIndex = control.index;
    updateStatus(formatLocationOption(worldLocationOptions[state.itemListIndex]));
    if (control.reason === 'initial') {
      audio.sfxUiBlip();
    }
    return;
  }
  if (control.type === 'select') {
    const location = worldLocationOptions[state.itemListIndex];
    if (!location) return;
    if (location.id === currentLocationId) {
      updateStatus(currentLocationName ? `Already in ${currentLocationName}.` : 'Already here.');
      audio.sfxUiBlip();
      return;
    }
    state.mode = 'normal';
    updateStatus(`You head toward ${location.name}.`);
    audio.sfxUiConfirm();
    signaling.send({ type: 'change_location', locationId: location.id });
    return;
  }
  if (control.type === 'cancel') {
    state.mode = 'normal';
    updateStatus('Exit location list mode.');
    audio.sfxUiCancel();
  }
}

/** Handles add-item type selection and item-type tooltip readout. */
function handleAddItemModeInput(code: string, key: string): void {
  const itemTypeSequence = getItemTypeSequence();
  if (itemTypeSequence.length === 0) {
    state.mode = 'normal';
    updateStatus('No item types available.');
    audio.sfxUiCancel();
    return;
  }
  const control = handleListControlKey(code, key, itemTypeSequence, state.addItemTypeIndex, (itemType) => itemTypeLabel(itemType));
  if (control.type === 'move') {
    state.addItemTypeIndex = control.index;
    updateStatus(`${itemTypeLabel(itemTypeSequence[state.addItemTypeIndex])}.`);
    audio.sfxUiBlip();
    return;
  }
  if (code === 'Space') {
    const itemType = itemTypeSequence[state.addItemTypeIndex];
    const tooltip = getItemTypeTooltip(itemType);
    updateStatus(tooltip ? tooltip : 'No tooltip available.');
    audio.sfxUiBlip();
    return;
  }
  if (control.type === 'select') {
    signaling.send({ type: 'item_add', itemType: itemTypeSequence[state.addItemTypeIndex] });
    state.mode = 'normal';
    return;
  }
  if (control.type === 'cancel') {
    state.mode = 'normal';
    updateStatus('Cancelled.');
    audio.sfxUiCancel();
  }
}

/** Handles generic selected-item list flow used by pickup/delete/edit/use/inspect contexts. */
function handleSelectItemModeInput(code: string, key: string, shiftKey = false): void {
  itemInteractionController.handleSelectItemModeInput(code, key, shiftKey);
}

/** Handles item-management action menu (`z`) for the selected square item. */
function handleItemManageOptionsModeInput(code: string, key: string): void {
  itemInteractionController.handleItemManageOptionsModeInput(code, key);
}

/** Handles target-user selection for item transfer action. */
function handleItemManageTransferUserModeInput(code: string, key: string): void {
  itemInteractionController.handleItemManageTransferUserModeInput(code, key);
}

/** Handles standardized yes/no confirmation for pending item-management actions. */
function handleConfirmYesNoModeInput(code: string, key: string): void {
  itemInteractionController.handleConfirmYesNoModeInput(code, key);
}

/** Handles top-level Shift+Z admin menu action selection. */
function handleAdminMenuModeInput(code: string, key: string): void {
  adminController.handleAdminMenuModeInput(code, key);
}

/** Handles role list selection flow, including add-role entry. */
function handleAdminRoleListModeInput(code: string, key: string): void {
  adminController.handleAdminRoleListModeInput(code, key);
}

/** Handles role permission toggle and delete flow. */
function handleAdminRolePermissionListModeInput(code: string, key: string): void {
  adminController.handleAdminRolePermissionListModeInput(code, key);
}

/** Handles replacement-role selection while deleting a role. */
function handleAdminRoleDeleteReplacementModeInput(code: string, key: string): void {
  adminController.handleAdminRoleDeleteReplacementModeInput(code, key);
}

/** Handles user list selection for change-role/ban/unban flows. */
function handleAdminUserListModeInput(code: string, key: string): void {
  adminController.handleAdminUserListModeInput(code, key);
}

/** Handles role selection for a previously selected user target. */
function handleAdminUserRoleSelectModeInput(code: string, key: string): void {
  adminController.handleAdminUserRoleSelectModeInput(code, key);
}

/** Handles yes/no confirmation for delete-account admin flow. */
function handleAdminUserDeleteConfirmModeInput(code: string, key: string): void {
  adminController.handleAdminUserDeleteConfirmModeInput(code, key);
}

/** Handles text edit for new-role creation from admin role list. */
function handleAdminRoleNameEditModeInput(code: string, key: string, ctrlKey: boolean): void {
  adminController.handleAdminRoleNameEditModeInput(code, key, ctrlKey);
}

function handleAdminAmbienceLocationListModeInput(code: string, key: string): void {
  adminController.handleAdminAmbienceLocationListModeInput(code, key);
}

function handleAdminAmbienceSoundListModeInput(code: string, key: string): void {
  adminController.handleAdminAmbienceSoundListModeInput(code, key);
}

function handleNotificationsModeInput(code: string, key: string): void {
  adminController.handleNotificationsModeInput(code, key);
}

const itemPropertyEditor = createItemPropertyEditor({
  state,
  signalingSend: (message) => signaling.send(message as OutgoingMessage),
  getItemPropertyValue,
  itemPropertyLabel,
  isItemPropertyEditable,
  getItemPropertyOptionValues: getItemPropertyOptionsForItem,
  openItemPropertyOptionSelect,
  describeItemPropertyHelp,
  getItemPropertyMetadata,
  validateNumericItemPropertyInput,
  applyTextInputEdit,
  setReplaceTextOnNextType: (value) => {
    replaceTextOnNextType = value;
  },
  suppressItemPropertyEchoMs: (ms) => {
    suppressItemPropertyEchoUntilMs = Math.max(suppressItemPropertyEchoUntilMs, Date.now() + Math.max(0, ms));
  },
  onPreviewPropertyChange: (item, key, value) => {
    itemBehaviorRegistry.onPropertyPreviewChange(item, key, value);
  },
  updateStatus,
  sfxUiBlip: () => audio.sfxUiBlip(),
  sfxUiCancel: () => audio.sfxUiCancel(),
  hostLabel: IS_NATIVE_CLIENT ? 'desktop client' : 'browser',
});

/** Handles nickname edit mode submission/cancel and text editing keys. */
function handleNicknameModeInput(code: string, key: string, ctrlKey: boolean): void {
  const editAction = getEditSessionAction(code);
  if (editAction === 'submit') {
    const clean = sanitizeName(state.nicknameInput);
    if (clean) {
      const payload: OutgoingMessage = { type: 'update_nickname', nickname: clean };
      signaling.send(payload);
      audio.sfxUiConfirm();
    } else {
      updateStatus('Cancelled.');
      audio.sfxUiCancel();
    }
    state.mode = 'normal';
    replaceTextOnNextType = false;
    return;
  }

  if (editAction === 'cancel') {
    state.mode = 'normal';
    replaceTextOnNextType = false;
    updateStatus('Cancelled.');
    audio.sfxUiCancel();
    return;
  }

  applyTextInputEdit(code, key, NICKNAME_MAX_LENGTH, ctrlKey, true);
}

function handleModeInput(input: ModeInput): void {
  if (itemBehaviorRegistry.handleModeInput(state.mode, input)) {
    return;
  }
  dispatchModeInput({
    mode: state.mode,
    input,
    handlers: {
      nickname: ({ code: currentCode, key: currentKey, ctrlKey: currentCtrlKey }) =>
        handleNicknameModeInput(currentCode, currentKey, currentCtrlKey),
      chat: ({ code: currentCode, key: currentKey, ctrlKey: currentCtrlKey }) =>
        handleChatModeInput(currentCode, currentKey, currentCtrlKey),
      alarmKeypad: ({ code: currentCode, key: currentKey }) =>
        handleAlarmKeypadModeInput(currentCode, currentKey),
      alarmSetupMethod: ({ code: currentCode }) => handleAlarmSetupMethodInput(currentCode),
      alarmSetupCode: ({ code: currentCode, key: currentKey }) =>
        handleAlarmSetupCodeInput(currentCode, currentKey),
      micGainEdit: ({ code: currentCode, key: currentKey, ctrlKey: currentCtrlKey }) =>
        handleMicGainEditModeInput(currentCode, currentKey, currentCtrlKey),
      commandPalette: ({ code: currentCode, key: currentKey }) => handleCommandPaletteModeInput(currentCode, currentKey),
      effectSelect: ({ code: currentCode, key: currentKey }) => handleEffectSelectModeInput(currentCode, currentKey),
      helpView: ({ code: currentCode }) => handleHelpViewModeInput(currentCode),
      listUsers: ({ code: currentCode, key: currentKey }) => handleListModeInput(currentCode, currentKey),
      userActionMenu: ({ code: currentCode, key: currentKey }) => handleUserActionMenuModeInput(currentCode, currentKey),
      listItems: ({ code: currentCode, key: currentKey }) => handleListItemsModeInput(currentCode, currentKey),
      listLocations: ({ code: currentCode, key: currentKey }) => handleLocationListModeInput(currentCode, currentKey),
      addItem: ({ code: currentCode, key: currentKey }) => handleAddItemModeInput(currentCode, currentKey),
      selectItem: ({ code: currentCode, key: currentKey, shiftKey: currentShiftKey }) =>
        handleSelectItemModeInput(currentCode, currentKey, currentShiftKey),
      itemManageOptions: ({ code: currentCode, key: currentKey }) => handleItemManageOptionsModeInput(currentCode, currentKey),
      itemManageTransferUser: ({ code: currentCode, key: currentKey }) =>
        handleItemManageTransferUserModeInput(currentCode, currentKey),
      confirmYesNo: ({ code: currentCode, key: currentKey }) => handleConfirmYesNoModeInput(currentCode, currentKey),
      adminMenu: ({ code: currentCode, key: currentKey }) => handleAdminMenuModeInput(currentCode, currentKey),
      adminRoleList: ({ code: currentCode, key: currentKey }) => handleAdminRoleListModeInput(currentCode, currentKey),
      adminRolePermissionList: ({ code: currentCode, key: currentKey }) =>
        handleAdminRolePermissionListModeInput(currentCode, currentKey),
      adminRoleDeleteReplacement: ({ code: currentCode, key: currentKey }) =>
        handleAdminRoleDeleteReplacementModeInput(currentCode, currentKey),
      adminUserList: ({ code: currentCode, key: currentKey }) => handleAdminUserListModeInput(currentCode, currentKey),
      adminUserRoleSelect: ({ code: currentCode, key: currentKey }) => handleAdminUserRoleSelectModeInput(currentCode, currentKey),
      adminUserDeleteConfirm: ({ code: currentCode, key: currentKey }) => handleAdminUserDeleteConfirmModeInput(currentCode, currentKey),
      adminRoleNameEdit: ({ code: currentCode, key: currentKey, ctrlKey: currentCtrlKey }) =>
        handleAdminRoleNameEditModeInput(currentCode, currentKey, currentCtrlKey),
      adminAmbienceLocationList: ({ code: currentCode, key: currentKey }) =>
        handleAdminAmbienceLocationListModeInput(currentCode, currentKey),
      adminAmbienceSoundList: ({ code: currentCode, key: currentKey }) =>
        handleAdminAmbienceSoundListModeInput(currentCode, currentKey),
      notifications: ({ code: currentCode, key: currentKey }) =>
        handleNotificationsModeInput(currentCode, currentKey),
      itemProperties: ({ code: currentCode, key: currentKey }) =>
        itemPropertyEditor.handleItemPropertiesModeInput(currentCode, currentKey),
      itemPropertyEdit: ({ code: currentCode, key: currentKey, ctrlKey: currentCtrlKey }) =>
        itemPropertyEditor.handleItemPropertyEditModeInput(currentCode, currentKey, currentCtrlKey),
      itemPropertyOptionSelect: ({ code: currentCode, key: currentKey }) =>
        itemPropertyEditor.handleItemPropertyOptionSelectModeInput(currentCode, currentKey),
    },
    onNormalMode: handleNormalModeInput,
  });
}

/** Enumerates audio devices, updates selectors, and persists preferred choices. */
async function populateAudioDevices(): Promise<void> {
  await mediaSession.populateAudioDevices();
}

/** Opens settings modal and focuses device controls. */
function openSettings(): void {
  lastFocusedElement = document.activeElement;
  for (const child of Array.from(document.querySelector('main.app')?.children ?? [])) {
    if (child !== dom.settingsModal && child instanceof HTMLElement) child.inert = true;
  }
  dom.settingsModal.classList.remove('hidden');
  dom.settingsModal.hidden = false;
  syncAnnouncementSettingsControls();
  syncFlexPbxDialingControls();
  void populateAudioDevices();
  if (state.running) {
    signaling.send({ type: 'ntfy_preferences_get' });
    signaling.send({ type: 'flexpbx_dialing_preferences_get' });
  }
  dom.audioInputSelect.focus();
}

// Native desktop opens this same accessible dialog from its File menu. The
// separate canvas button is intentionally omitted so device settings have one
// clear home.
if (IS_NATIVE_CLIENT) {
  (window as Window & { chatGridNativeOpenSettings?: () => boolean }).chatGridNativeOpenSettings = () => {
    openSettings();
    return true;
  };
  (window as Window & { chatGridNativeApplyAudioSettings?: (value: unknown) => void }).chatGridNativeApplyAudioSettings = (value) => {
    if (!value || typeof value !== 'object') return;
    const next = value as Partial<{
      outputMode: 'mono' | 'stereo'; masterVolume: number; microphoneGain: number;
      layers: Partial<AudioLayerState>; announcementMode: string; radioAnnouncementMode: string;
      itemBeacons: boolean; movementDirections: boolean;
    }>;
    if (next.outputMode === 'mono' || next.outputMode === 'stereo') {
      outputMode = next.outputMode;
      audio.setOutputMode(outputMode);
      settings.saveOutputMode(outputMode);
    }
    if (Number.isFinite(next.masterVolume)) persistMasterVolume(audio.setMasterVolume(Number(next.masterVolume)));
    if (Number.isFinite(next.microphoneGain)) persistMicInputGain(audio.setOutboundInputGain(Number(next.microphoneGain)));
    if (next.layers) {
      audioLayers = { ...audioLayers, ...next.layers };
      persistAudioLayerState();
      void applyAudioLayerState();
    }
    if (typeof next.announcementMode === 'string') setAnnouncementMode(next.announcementMode);
    if (typeof next.radioAnnouncementMode === 'string') setRadioAnnouncementMode(next.radioAnnouncementMode);
    if (typeof next.itemBeacons === 'boolean') setItemBeacons(next.itemBeacons);
    if (typeof next.movementDirections === 'boolean') setMovementDirections(next.movementDirections);
  };
}

dom.ntfyNotificationsToggle.addEventListener('change', () => {
  signaling.send({ type: 'ntfy_preferences_update', enabled: dom.ntfyNotificationsToggle.checked });
  dom.ntfyNotificationsStatus.textContent = 'Saving ntfy notification settings...';
});

dom.rotateNtfyTopicButton.addEventListener('click', () => {
  signaling.send({ type: 'ntfy_preferences_update', enabled: true, rotateTopic: true });
  dom.ntfyNotificationsStatus.textContent = 'Replacing the private ntfy topic...';
});

/** Closes settings modal and restores focus back to prior element or game canvas. */
function closeSettings(): void {
  dom.settingsModal.classList.add('hidden');
  dom.settingsModal.hidden = true;
  for (const child of Array.from(document.querySelector('main.app')?.children ?? [])) {
    if (child !== dom.settingsModal && child instanceof HTMLElement) child.inert = false;
  }
  if (lastFocusedElement instanceof HTMLElement) {
    lastFocusedElement.focus();
  } else {
    dom.canvas.focus();
  }
}

setupKeyboardInputHandlers({
  dom: {
    settingsModal: dom.settingsModal,
    canvas: dom.canvas,
  },
  state,
  isTextEditingMode,
  closeSettings,
  hasBlockedArrowTeleport: (code) => Boolean(activeTeleport && code.startsWith('Arrow')),
  handleModeInput,
  runImmediateMovement: handleMovement,
  canOpenCommandPaletteInMode,
  openCommandPalette,
  getModeKeyUpTarget: (activeMode) => itemBehaviorRegistry.getModeKeyUpTarget(activeMode, commandPaletteReturnMode),
  onModeKeyUp: (mode, { code, shiftKey }) => {
    itemBehaviorRegistry.handleModeKeyUp(mode, {
      code,
      shiftKey,
    });
  },
  pasteIntoActiveTextInput,
  updateStatus,
  setReplaceTextOnNextType: (value) => {
    replaceTextOnNextType = value;
  },
  closeInteractiveItem,
});

dom.readGuideButton.addEventListener('click', () => {
  if (joinGuideReaderActive) {
    closeJoinGuideReader();
    return;
  }
  openJoinGuideReader();
});

window.addEventListener('chatgrid-cast-to-device', () => {
  void castToNearestDevice();
});

document.addEventListener('keydown', handleJoinGuideReaderKey);

midiControllerHandle = setupMidiInputHandlers({
  button: dom.midiButton,
  state,
  handleMidiNoteOn: (mode, midi, velocity) => itemBehaviorRegistry.handleMidiNoteOn(mode, midi, velocity),
  handleMidiNoteOff: (mode, midi) => itemBehaviorRegistry.handleMidiNoteOff(mode, midi),
  updateStatus,
  sfxUiBlip: () => audio.sfxUiBlip(),
  sfxUiCancel: () => audio.sfxUiCancel(),
});

dom.interactiveItemCloseButton.addEventListener('click', () => {
  closeInteractiveItem();
});
setupDomUiHandlers({
  dom,
  updateConnectAvailability,
  connect,
  disconnect,
  closeSettings,
  openSettings,
  updateStatus,
  sfxUiBlip: () => audio.sfxUiBlip(),
  setupLocalMedia,
  setPreferredInput: (id, name) => {
    mediaSession.setPreferredInput(id, name);
  },
  setPreferredOutput: (id, name) => {
    mediaSession.setPreferredOutput(id, name);
  },
  updateDeviceSummary,
  setOutputDevice: (id) => peerManager.setOutputDevice(id),
  setAnnouncementMode,
  setRadioAnnouncementMode,
  setItemBeacons,
  setMovementDirections,
  setFlexPbxDialingPreferences,
});
authController.setupUiHandlers({
  connect,
});
authController.initializeUi();
updateDeviceSummary();
syncAnnouncementSettingsControls();
syncFlexPbxDialingControls();
setConnectionStatus(
  STARTED_FROM_VERSION_RELOAD
    ? 'Client updated. Reconnecting...'
    : activeWelcomeMessage,
);
if (STARTED_FROM_VERSION_RELOAD) {
  clearVersionReloadMarker();
}
if (
  STARTED_FROM_VERSION_RELOAD
  || isConnectionRecoveryReload()
  || initialExternalAuthAssertion
  || initialAuthUsername.trim().length > 0
) {
  window.setTimeout(() => {
    void connect();
  }, 0);
} else {
  void autoConnectFromSavedSessionCookie();
}
