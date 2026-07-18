import { type IncomingMessage } from './protocol';
import { type WorldItem } from '../state/gameState';

/**
 * Dependency contract for creating a message handler without hard-coupling to `main.ts`.
 */
type MessageHandlerDeps = {
  getWorldGridSize: () => number;
  getCurrentLocationId: () => string;
  setWorldGridSize: (size: number) => void;
  setMovementTickMs: (value: number) => void;
  setWorldLocations: (
    locations: Array<{
      id: string;
      name: string;
      kind: string;
      description: string;
      spawnX: number;
      spawnY: number;
      ambienceKey?: string;
      ambienceName?: string;
    }>,
    currentLocationId?: string,
  ) => void;
  setCurrentLocation: (locationId: string, locationName: string) => void;
  setConnecting: (value: boolean) => void;
  rendererSetGridSize: (size: number) => void;
  applyServerItemUiDefinitions: (defs: unknown) => boolean;
  state: {
    addItemTypeIndex: number;
    player: {
      id: string | null;
      nickname: string;
      x: number;
      y: number;
      posture?: 'standing' | 'sitting' | 'lying';
      seatedItemId?: string | null;
      seatedOffset?: number;
      handHeldById?: string | null;
    };
    running: boolean;
    peers: Map<
      string,
      {
        id: string;
        userId?: string | null;
        nickname: string;
        locationId?: string;
        x: number;
        y: number;
        posture?: 'standing' | 'sitting' | 'lying';
        seatedItemId?: string | null;
        seatedOffset?: number;
        handHeldById?: string | null;
      }
    >;
    items: Map<string, WorldItem>;
    mode: string;
    selectedItemId: string | null;
    itemPropertyKeys: string[];
    itemPropertyIndex: number;
    carriedItemId: string | null;
  };
  dom: {
    connectButton: HTMLElement;
    disconnectButton: HTMLElement;
    focusGridButton: HTMLElement;
    canvas: HTMLCanvasElement;
    instructions: HTMLElement;
  };
  signalingSend: (message: unknown) => void;
  peerManager: {
    createOrGetPeer: (id: string, initiator: boolean, user: { id: string; nickname: string; locationId?: string; x: number; y: number }) => Promise<unknown>;
    handleSignal: (message: IncomingMessage) => Promise<{ id: string; nickname: string; locationId?: string; x: number; y: number }>;
    setPeerPosition: (id: string, x: number, y: number) => void;
    setPeerNickname: (id: string, nickname: string) => void;
    removePeer: (id: string) => void;
  };
  refreshAudioSubscriptions: (force?: boolean) => Promise<void>;
  cleanupItemAudio: (itemId: string) => void;
  applyAudioLayerState: () => Promise<void>;
  syncLocationAmbience: () => Promise<void>;
  gameLoop: () => void;
  sanitizeName: (value: string) => string;
  randomFootstepCue: (
    identity?: string,
    nickname?: string,
    locationId?: string,
  ) => { url: string; gain: number; fadeInMs: number; playbackRate: number; identity: string; nickname: string; surface?: string };
  playRemoteSpatialStepOrTeleport: (
    cue: string | { url: string; gain: number; fadeInMs: number; playbackRate: number },
    peerX: number,
    peerY: number,
  ) => void;
  narrateLocationArrival: (locationName: string, x: number, y: number) => void;
  narrateRemoteMovement: (nickname: string, fromX: number, fromY: number, toX: number, toY: number) => void;
  handleItemActionResultStatus: (message: Extract<IncomingMessage, { type: 'item_action_result' }>) => boolean;
  handleInteractiveItemLaunch: (item: WorldItem) => boolean;
  handleGameLaunchInvite: (message: Extract<IncomingMessage, { type: 'item_game_launch' }>) => boolean;
  handleDoorTransitionArrival: (x: number, y: number) => void;
  handleDoorTransitionUseResult: (itemId: string | null | undefined) => void;
  handleItemBehaviorIncomingMessage: (message: IncomingMessage) => boolean;
  handleItemBehaviorPeerLeft: (senderId: string) => void;
  TELEPORT_SOUND_URL: string;
  TELEPORT_START_SOUND_URL: string;
  getAudioLayers: () => { world: boolean; voice: boolean; item: boolean };
  pushChatMessage: (message: string, announce?: boolean) => void;
  shouldAnnounceRadioAction: () => boolean;
  pushPublicChatMessage: (message: string) => void;
  pushDirectChatMessage: (message: string, peerId: string, peerName: string) => void;
  classifySystemMessageSound: (message: string) => 'logon' | 'logout' | 'notify' | null;
  ACTION_SOUND_URL: string;
  SYSTEM_SOUND_URLS: { logon: string; logout: string; notify: string };
  playSample: (url: string, gain?: number) => void;
  updateStatus: (message: string) => void;
  audioUiBlip: () => void;
  audioUiConfirm: () => void;
  audioUiCancel: () => void;
  getCarriedItemId: () => string | null;
  recomputeActiveItemPropertyKeys: (itemId: string) => void;
  itemPropertyLabel: (key: string) => string;
  getItemPropertyValue: (item: WorldItem, key: string) => string;
  getItemById: (itemId: string) => WorldItem | undefined;
  shouldAnnounceItemPropertyEcho: () => boolean;
  playLocateToneAt: (x: number, y: number) => void;
  resolveIncomingSoundUrl: (url: string) => string;
  playIncomingItemUseSound: (url: string, x: number, y: number, range?: number) => void;
  playClockAnnouncement: (sounds: string[], x: number, y: number, range?: number) => void;
  handleAuthRequired: (message: Extract<IncomingMessage, { type: 'auth_required' }>) => void;
  handleAuthResult: (message: Extract<IncomingMessage, { type: 'auth_result' }>) => Promise<void>;
  handleAuthPermissions: (message: Extract<IncomingMessage, { type: 'auth_permissions' }>) => void;
  handleAdminRolesList: (message: Extract<IncomingMessage, { type: 'admin_roles_list' }>) => void;
  handleAdminUsersList: (message: Extract<IncomingMessage, { type: 'admin_users_list' }>) => void;
  handleAdminPlatformOverview: (message: Extract<IncomingMessage, { type: 'admin_platform_overview' }>) => void;
  handleAdminNotificationsList: (message: Extract<IncomingMessage, { type: 'admin_notifications_list' }>) => void;
  handleAdminAmbienceCatalog: (message: Extract<IncomingMessage, { type: 'admin_ambience_catalog' }>) => void;
  handleAdminActionResult: (message: Extract<IncomingMessage, { type: 'admin_action_result' }>) => void;
  handleNtfyPreferences: (message: Extract<IncomingMessage, { type: 'ntfy_preferences' }>) => void;
  handleItemTransferTargets: (message: Extract<IncomingMessage, { type: 'item_transfer_targets' }>) => void;
  isPeerNegotiationReady: () => boolean;
  enqueuePendingSignal: (message: Extract<IncomingMessage, { type: 'signal' }>) => void;
};

/**
 * Builds the websocket message dispatcher used by the signaling client.
 */
export function createOnMessageHandler(deps: MessageHandlerDeps): (message: IncomingMessage) => Promise<void> {
  return async function onMessage(message: IncomingMessage): Promise<void> {
    switch (message.type) {
      case 'auth_required':
        deps.handleAuthRequired(message);
        break;

      case 'auth_result':
        await deps.handleAuthResult(message);
        break;
      case 'auth_permissions':
        deps.handleAuthPermissions(message);
        break;
      case 'admin_roles_list':
        deps.handleAdminRolesList(message);
        break;
      case 'admin_users_list':
        deps.handleAdminUsersList(message);
        break;
      case 'admin_platform_overview':
        deps.handleAdminPlatformOverview(message);
        break;
      case 'admin_notifications_list':
        deps.handleAdminNotificationsList(message);
        break;
      case 'admin_ambience_catalog':
        deps.handleAdminAmbienceCatalog(message);
        break;
      case 'admin_action_result':
        deps.handleAdminActionResult(message);
        break;
      case 'ntfy_preferences':
        deps.handleNtfyPreferences(message);
        break;
      case 'item_transfer_targets':
        deps.handleItemTransferTargets(message);
        break;

      case 'welcome':
        if (message.worldConfig?.gridSize && Number.isInteger(message.worldConfig.gridSize) && message.worldConfig.gridSize > 0) {
          deps.setWorldGridSize(message.worldConfig.gridSize);
        }
        if (message.worldConfig?.movementTickMs && Number.isInteger(message.worldConfig.movementTickMs) && message.worldConfig.movementTickMs > 0) {
          deps.setMovementTickMs(message.worldConfig.movementTickMs);
        }
        deps.setWorldLocations(message.worldConfig?.locations ?? [], message.worldConfig?.locationId);
        deps.rendererSetGridSize(deps.getWorldGridSize());
        const schemaReady = deps.applyServerItemUiDefinitions(message.uiDefinitions);
        if (!schemaReady) {
          deps.updateStatus('Item schema missing from server. Item menus unavailable.');
        }
        deps.state.addItemTypeIndex = 0;
        deps.state.player.id = message.id;
        deps.state.running = true;
        deps.setConnecting(false);
        deps.state.player.x = Math.max(0, Math.min(deps.getWorldGridSize() - 1, message.player.x));
        deps.state.player.y = Math.max(0, Math.min(deps.getWorldGridSize() - 1, message.player.y));
        deps.state.player.posture = message.player.posture ?? 'standing';
        deps.state.player.seatedItemId = message.player.seatedItemId ?? null;
        deps.state.player.seatedOffset = message.player.seatedOffset ?? 0;
        deps.state.player.handHeldById = message.player.handHeldById ?? null;
        deps.dom.connectButton.classList.add('hidden');
        deps.dom.disconnectButton.classList.remove('hidden');
        deps.dom.focusGridButton.classList.remove('hidden');
        deps.dom.canvas.classList.remove('hidden');
        deps.dom.instructions.classList.remove('hidden');
        document.getElementById('joinGuide')?.classList.add('hidden');
        const dashboard = document.getElementById('gridDashboard');
        dashboard?.classList.remove('hidden');
        if (dashboard) dashboard.hidden = false;
        deps.dom.canvas.focus();

        deps.signalingSend({ type: 'update_position', x: deps.state.player.x, y: deps.state.player.y });
        deps.signalingSend({ type: 'update_nickname', nickname: deps.state.player.nickname });

        for (const user of message.users) {
          deps.state.peers.set(user.id, { ...user });
        }
        deps.state.items.clear();
        for (const item of message.items || []) {
          deps.state.items.set(item.id, {
            ...item,
            carrierId: item.carrierId ?? null,
          });
        }
        await deps.refreshAudioSubscriptions(true);
        await deps.applyAudioLayerState();
        deps.gameLoop();
        break;

      case 'location_changed': {
        if (message.id === deps.state.player.id) {
          deps.state.player.x = message.x;
          deps.state.player.y = message.y;
          deps.state.player.posture = 'standing';
          deps.state.player.seatedItemId = null;
          deps.state.player.seatedOffset = 0;
          deps.state.player.handHeldById = null;
          deps.state.peers.clear();
          deps.state.items.clear();
          deps.state.carriedItemId = null;
          deps.setCurrentLocation(message.locationId, message.locationName);
          deps.narrateLocationArrival(message.locationName, message.x, message.y);
          deps.handleDoorTransitionArrival(message.x, message.y);
          await deps.refreshAudioSubscriptions(true);
          await deps.applyAudioLayerState();
          deps.gameLoop();
          break;
        }
        deps.state.peers.set(message.id, {
          id: message.id,
          userId: message.userId ?? null,
          nickname: deps.sanitizeName(message.nickname || 'user...') || 'user...',
          locationId: message.locationId,
          x: message.x,
          y: message.y,
          posture: 'standing',
          seatedItemId: null,
          seatedOffset: 0,
          handHeldById: null,
        });
        break;
      }

      case 'signal': {
        if (!deps.isPeerNegotiationReady()) {
          deps.enqueuePendingSignal(message);
          if (!deps.state.peers.has(message.senderId)) {
          deps.state.peers.set(message.senderId, {
            id: message.senderId,
            userId: null,
            nickname: deps.sanitizeName(message.senderNickname || 'user...') || 'user...',
            locationId: message.locationId ?? undefined,
            x: Number.isFinite(message.x) ? message.x : 20,
            y: Number.isFinite(message.y) ? message.y : 20,
            });
          }
          break;
        }
        const peer = await deps.peerManager.handleSignal(message);
        if (!deps.state.peers.has(peer.id)) {
          deps.state.peers.set(peer.id, {
            id: peer.id,
            userId: null,
            nickname: deps.sanitizeName(peer.nickname) || 'user...',
            locationId: peer.locationId,
            x: peer.x,
            y: peer.y,
          });
        }
        break;
      }

      case 'update_position': {
        if (message.id === deps.state.player.id) {
          deps.state.player.x = message.x;
          deps.state.player.y = message.y;
          deps.state.player.posture = message.posture ?? 'standing';
          deps.state.player.seatedItemId = message.seatedItemId ?? null;
          deps.state.player.seatedOffset = message.seatedOffset ?? 0;
          deps.state.player.handHeldById = message.handHeldById ?? null;
          break;
        }
        const peer = deps.state.peers.get(message.id);
        if (!peer) {
          const discoveredPeer = {
            id: message.id,
            userId: null,
            nickname: deps.sanitizeName(message.nickname || 'user...') || 'user...',
            locationId: message.locationId,
            x: message.x,
            y: message.y,
            posture: message.posture ?? 'standing',
            seatedItemId: message.seatedItemId ?? null,
            seatedOffset: message.seatedOffset ?? 0,
            handHeldById: message.handHeldById ?? null,
          };
          deps.state.peers.set(message.id, discoveredPeer);
          if (deps.isPeerNegotiationReady()) {
            await deps.peerManager.createOrGetPeer(message.id, true, discoveredPeer);
          }
        }
        const prevX = peer?.x ?? message.x;
        const prevY = peer?.y ?? message.y;
        if (peer) {
          peer.locationId = message.locationId ?? peer.locationId;
          peer.x = message.x;
          peer.y = message.y;
          peer.posture = message.posture ?? 'standing';
          peer.seatedItemId = message.seatedItemId ?? null;
          peer.seatedOffset = message.seatedOffset ?? 0;
          peer.handHeldById = message.handHeldById ?? null;
        }
        deps.peerManager.setPeerPosition(message.id, message.x, message.y);
        if (peer) {
          const movementDelta = Math.hypot(message.x - prevX, message.y - prevY);
          const peerLocationId = message.locationId ?? peer.locationId;
          if (movementDelta <= 1.5 && deps.getAudioLayers().world && peerLocationId === deps.getCurrentLocationId()) {
            deps.playRemoteSpatialStepOrTeleport(
              deps.randomFootstepCue(peer.userId ?? message.id, peer.nickname, peerLocationId),
              peer.x,
              peer.y,
            );
          }
          deps.narrateRemoteMovement(peer.nickname, prevX, prevY, peer.x, peer.y);
        }
        break;
      }

      case 'teleport_complete': {
        if (deps.getAudioLayers().world) {
          deps.playIncomingItemUseSound(deps.TELEPORT_SOUND_URL, message.x, message.y);
        }
        break;
      }

      case 'update_nickname': {
        const peer = deps.state.peers.get(message.id);
        if (peer) {
          peer.nickname = deps.sanitizeName(message.nickname) || 'user...';
        }
        deps.peerManager.setPeerNickname(message.id, deps.sanitizeName(message.nickname) || 'user...');
        break;
      }

      case 'user_left': {
        const peer = deps.state.peers.get(message.id);
        if (peer) {
          deps.updateStatus(`${peer.nickname} has left.`);
        }
        deps.handleItemBehaviorPeerLeft(message.id);
        deps.state.peers.delete(message.id);
        deps.peerManager.removePeer(message.id);
        break;
      }

      case 'chat_message': {
        if (message.action) {
          deps.pushChatMessage(message.message);
          deps.playSample(deps.ACTION_SOUND_URL, 1);
        } else if (message.system) {
          deps.pushChatMessage(message.message);
          const normalized = message.message.trim().toLowerCase();
          if (normalized === 'server reboot already in progress.') {
            deps.audioUiBlip();
            break;
          }
          const sound = deps.classifySystemMessageSound(message.message);
          if (sound) {
            deps.playSample(deps.SYSTEM_SOUND_URLS[sound], 1);
          }
        } else {
          const sender = message.senderNickname || 'Unknown';
          deps.pushPublicChatMessage(`${sender}: ${message.message}`);
        }
        break;
      }

      case 'direct_message': {
        const peerId = message.outgoing ? message.targetId : message.senderId;
        const peerName = message.outgoing
          ? (message.targetNickname || 'Unknown')
          : (message.senderNickname || 'Unknown');
        const label = message.outgoing
          ? `DM to ${message.targetNickname || 'Unknown'}`
          : `DM from ${message.senderNickname || 'Unknown'}`;
        deps.pushDirectChatMessage(`${label}: ${message.message}`, peerId, peerName);
        deps.playSample(deps.SYSTEM_SOUND_URLS.notify, 1);
        break;
      }

      case 'social_action': {
        const text = message.message.trim();
        if (text) {
          deps.pushChatMessage(text);
        }
        const soundUrl = deps.resolveIncomingSoundUrl(message.sound || '');
        if (soundUrl && deps.getAudioLayers().world) {
          deps.playIncomingItemUseSound(soundUrl, message.x, message.y, message.range);
        } else if (deps.getAudioLayers().world) {
          deps.playIncomingItemUseSound(deps.ACTION_SOUND_URL, message.x, message.y, message.range);
        }
        break;
      }

      case 'user_action_result': {
        deps.updateStatus(message.message);
        if (message.ok) {
          deps.audioUiConfirm();
        } else {
          deps.audioUiCancel();
        }
        break;
      }

      case 'pong': {
        const elapsed = Math.max(0, Date.now() - message.clientSentAt);
        deps.updateStatus(`Ping ${elapsed} ms`);
        deps.audioUiBlip();
        break;
      }

      case 'nickname_result': {
        deps.state.player.nickname = deps.sanitizeName(message.effectiveNickname) || 'user...';
        if (!message.accepted) {
          deps.pushChatMessage(message.reason || 'Nickname unavailable.');
          deps.audioUiCancel();
        }
        break;
      }

      case 'item_upsert': {
        deps.state.items.set(message.item.id, {
          ...message.item,
          carrierId: message.item.carrierId ?? null,
        });
        deps.state.carriedItemId = deps.getCarriedItemId();
        deps.recomputeActiveItemPropertyKeys(message.item.id);
        if (deps.state.mode === 'itemProperties' && deps.state.selectedItemId === message.item.id) {
          const key = deps.state.itemPropertyKeys[deps.state.itemPropertyIndex];
          if (key && deps.shouldAnnounceItemPropertyEcho()) {
            deps.updateStatus(`${deps.itemPropertyLabel(key)}: ${deps.getItemPropertyValue(message.item, key)}`);
          }
        }
        await deps.refreshAudioSubscriptions(true);
        await deps.syncLocationAmbience();
        break;
      }

      case 'item_remove': {
        deps.state.items.delete(message.itemId);
        deps.state.carriedItemId = deps.getCarriedItemId();
        deps.cleanupItemAudio(message.itemId);
        await deps.refreshAudioSubscriptions(true);
        await deps.syncLocationAmbience();
        break;
      }

      case 'item_action_result': {
        const handledByItemBehavior = deps.handleItemActionResultStatus(message);
        if (handledByItemBehavior) {
          break;
        }
        const text = message.message.trim();
        if (message.ok) {
          if (message.action === 'use' || message.action === 'secondary_use') {
            const item = message.itemId ? deps.getItemById(message.itemId) : null;
            const announce = item?.type !== 'radio_station' || deps.shouldAnnounceRadioAction();
            if (text) {
              deps.pushChatMessage(text, announce);
            }
            if (message.action === 'use' && item && deps.handleInteractiveItemLaunch(item)) {
              break;
            }
            if (message.action === 'use') {
              deps.handleDoorTransitionUseResult(message.itemId);
            }
            if (message.action === 'use' && !item?.useSound && item && item.type !== 'piano' && item.type !== 'clock') {
              deps.playLocateToneAt(item.x, item.y);
            }
          } else if (message.action !== 'update') {
            if (text) {
              deps.pushChatMessage(text);
            }
            deps.audioUiConfirm();
          }
        } else {
          if (text) {
            deps.pushChatMessage(text);
          }
          deps.audioUiCancel();
        }
        break;
      }

      case 'item_use_sound': {
        const soundUrl = deps.resolveIncomingSoundUrl(message.sound);
        if (!soundUrl) break;
        if (deps.getAudioLayers().item) {
          deps.playIncomingItemUseSound(soundUrl, message.x, message.y, message.range);
        }
        break;
      }

      case 'agent_voice': {
        // Agent speech belongs to the voice layer.  It used to be gated by
        // the item-sound layer, so muting item cues also made Claudia silent.
        // Keep item enabled as a compatibility fallback for older settings,
        // but voice alone must be enough to hear agent speech.
        if (deps.getAudioLayers().voice || deps.getAudioLayers().item) {
          const audioUrl = deps.resolveIncomingSoundUrl(message.audioUrl);
          if (audioUrl) {
            deps.playIncomingItemUseSound(audioUrl, message.x, message.y, message.range);
          }
        }
        break;
      }

      case 'item_game_launch': {
        if (message.actorId === deps.state.player.id) break;
        if (message.x !== deps.state.player.x || message.y !== deps.state.player.y) {
          deps.updateStatus(`${message.actorNickname} started ${message.title} nearby.`);
          break;
        }
        if (deps.handleGameLaunchInvite(message)) {
          deps.pushChatMessage(`${message.actorNickname} started ${message.title} for everyone on this square.`);
        }
        break;
      }

      case 'item_piano_note': {
        if (!deps.getAudioLayers().item) break;
        deps.handleItemBehaviorIncomingMessage(message);
        break;
      }

      case 'item_clock_announce': {
        if (!deps.getAudioLayers().item) break;
        deps.playClockAnnouncement(message.sounds, message.x, message.y, message.range);
        break;
      }

      case 'item_piano_status': {
        deps.handleItemBehaviorIncomingMessage(message);
        break;
      }
    }
  };
}
