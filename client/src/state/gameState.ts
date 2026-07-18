export const GRID_SIZE = 41;
export const HEARING_RADIUS = 20;
export const MOVE_COOLDOWN_MS = 200;

export type ItemType = string;

export type WorldItem = {
  id: string;
  type: ItemType;
  title: string;
  locationId?: string;
  x: number;
  y: number;
  createdBy: string;
  updatedBy: string;
  createdAt: number;
  updatedAt: number;
  version: number;
  capabilities: string[];
  useSound?: string;
  emitSound?: string;
  params: Record<string, unknown>;
  carrierId?: string | null;
  display?: Record<string, string>;
};

export type SelectionContext = 'pickup' | 'drop' | 'delete' | 'edit' | 'use' | 'secondaryUse' | 'inspect' | 'manage' | null;

export type GameMode =
  | 'normal'
  | 'commandPalette'
  | 'helpView'
  | 'nickname'
  | 'chat'
  | 'alarmKeypad'
  | 'alarmSetupMethod'
  | 'alarmSetupCode'
  | 'micGainEdit'
  | 'effectSelect'
  | 'listUsers'
  | 'userActionMenu'
  | 'listItems'
  | 'listLocations'
  | 'addItem'
  | 'selectItem'
  | 'itemProperties'
  | 'itemPropertyEdit'
  | 'itemPropertyOptionSelect'
  | 'itemManageOptions'
  | 'itemManageTransferUser'
  | 'confirmYesNo'
  | 'adminMenu'
  | 'adminRoleList'
  | 'adminRolePermissionList'
  | 'adminRoleDeleteReplacement'
  | 'adminUserList'
  | 'adminUserRoleSelect'
  | 'adminUserDeleteConfirm'
  | 'adminRoleNameEdit'
  | 'adminAmbienceLocationList'
  | 'adminAmbienceSoundList'
  | 'notifications'
  | 'pianoUse';

export type Player = {
  id: string | null;
  nickname: string;
  x: number;
  y: number;
  posture: 'standing' | 'sitting' | 'lying';
  seatedItemId: string | null;
  seatedOffset: number;
  handHeldById: string | null;
  lastMoveTime: number;
};

export type PeerState = {
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
};

export type GameState = {
  running: boolean;
  mode: GameMode;
  keysPressed: Record<string, boolean>;
  nicknameInput: string;
  cursorPos: number;
  cursorVisible: boolean;
  sortedPeerIds: string[];
  listIndex: number;
  sortedItemIds: string[];
  itemListIndex: number;
  selectedItemIds: string[];
  selectionContext: SelectionContext;
  selectedItemIndex: number;
  selectedItemId: string | null;
  focusedItemId: string | null;
  directMessageTargetId: string | null;
  directMessageTargetName: string | null;
  itemPropertyKeys: string[];
  itemPropertyIndex: number;
  editingPropertyKey: string | null;
  itemPropertyOptionValues: string[];
  itemPropertyOptionLabels: string[];
  itemPropertyOptionIndex: number;
  effectSelectIndex: number;
  addItemTypeIndex: number;
  isMuted: boolean;
  player: Player;
  peers: Map<string, PeerState>;
  items: Map<string, WorldItem>;
  carriedItemId: string | null;
  remoteControlsFocused: boolean;
};

export function createInitialState(): GameState {
  return {
    running: false,
    mode: 'normal',
    keysPressed: {},
    nicknameInput: '',
    cursorPos: 0,
    cursorVisible: true,
    sortedPeerIds: [],
    listIndex: 0,
    sortedItemIds: [],
    itemListIndex: 0,
    selectedItemIds: [],
    selectionContext: null,
    selectedItemIndex: 0,
    selectedItemId: null,
    focusedItemId: null,
    directMessageTargetId: null,
    directMessageTargetName: null,
    itemPropertyKeys: [],
    itemPropertyIndex: 0,
    editingPropertyKey: null,
    itemPropertyOptionValues: [],
    itemPropertyOptionLabels: [],
    itemPropertyOptionIndex: 0,
    effectSelectIndex: 0,
    addItemTypeIndex: 0,
    isMuted: false,
    player: {
      id: null,
      nickname: 'anon',
      x: 20,
      y: 20,
      posture: 'standing',
      seatedItemId: null,
      seatedOffset: 0,
      handHeldById: null,
      lastMoveTime: 0,
    },
    peers: new Map(),
    items: new Map(),
    carriedItemId: null,
    remoteControlsFocused: true,
  };
}

export function getNearestPeer(state: GameState): { peerId: string | null; distance: number } {
  let nearest: string | null = null;
  let minDist = Infinity;
  for (const [id, peer] of state.peers.entries()) {
    const dist = Math.hypot(peer.x - state.player.x, peer.y - state.player.y);
    if (dist < minDist) {
      minDist = dist;
      nearest = id;
    }
  }
  return { peerId: nearest, distance: minDist };
}

export function getDirection(px: number, py: number, tx: number, ty: number): string {
  const dx = tx - px;
  const dy = ty - py;
  if (dx === 0 && dy === 0) return 'here';
  if (dx === 0) return dy > 0 ? 'directly north' : 'directly south';
  if (dy === 0) return dx > 0 ? 'directly east' : 'directly west';

  const octants = ['east', 'northeast', 'north', 'northwest', 'west', 'southwest', 'south', 'southeast'] as const;
  const step = Math.PI / 4;
  const rawIndex = Math.round(Math.atan2(dy, dx) / step);
  const index = ((rawIndex % octants.length) + octants.length) % octants.length;
  return octants[index];
}

export function getNearestItem(state: GameState): { itemId: string | null; distance: number } {
  let nearest: string | null = null;
  let minDist = Infinity;
  for (const [id, item] of state.items.entries()) {
    if (item.carrierId) continue;
    if (isItemQuiet(item)) continue;
    const dist = Math.hypot(item.x - state.player.x, item.y - state.player.y);
    if (dist < minDist) {
      minDist = dist;
      nearest = id;
    }
  }
  return { itemId: nearest, distance: minDist };
}

export function isItemQuiet(item: WorldItem): boolean {
  const visibility = String(item.params.itemVisibility ?? '').trim().toLowerCase();
  const mode = String(item.params.billboardMode ?? '').trim().toLowerCase();
  return visibility === 'quiet' || visibility === 'hidden' || mode === 'audio_only';
}
