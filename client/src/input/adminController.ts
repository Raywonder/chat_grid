import { handleListControlKey } from './listController';
import { getEditSessionAction } from './editSession';
import { handleYesNoMenuInput, YES_NO_OPTIONS } from './yesNoMenu';
import type { IncomingMessage, OutgoingMessage } from '../network/protocol';
import type { GameMode } from '../state/gameState';

export type AdminMenuAction = {
  id: string;
  label: string;
  tooltip?: string;
};

export type AdminRoleSummary = {
  id: number;
  name: string;
  isSystem: boolean;
  userCount: number;
  permissions: string[];
};

export type AdminUserSummary = {
  id: string;
  username: string;
  role: string;
  status: 'active' | 'disabled';
};

export type AdminNotificationSummary = {
  id: string;
  createdAt: number;
  kind: string;
  title: string;
  message: string;
  targetUserId?: string | null;
  actorUserId?: string | null;
  read?: boolean;
};

type AdminAmbienceLocation = { id: string; name: string; currentSoundId: string; currentSoundLabel: string };
type AdminAmbienceSound = {
  id: string; label: string; category: string; url: string; sourceFilename: string;
  durationSeconds: number; loopStartSeconds: number; loopEndSeconds: number; seamCrossfadeSeconds: number;
};

export type AdminPendingUserMutation =
  | { action: 'set_role'; username: string; role: string }
  | { action: 'ban'; username: string }
  | { action: 'unban'; username: string }
  | { action: 'delete_account'; username: string };

type AdminPendingUserAction = 'set_role' | 'ban' | 'unban' | 'delete_account' | null;

type AdminControllerDeps = {
  state: {
    mode: GameMode;
    nicknameInput: string;
    cursorPos: number;
  };
  signalingSend: (message: OutgoingMessage) => void;
  announceMenuEntry: (title: string, firstOption: string) => void;
  updateStatus: (message: string) => void;
  sfxUiBlip: () => void;
  sfxUiCancel: () => void;
  applyTextInputEdit: (code: string, key: string, maxLength: number, ctrlKey?: boolean, allowReplaceOnNextType?: boolean) => void;
  setReplaceTextOnNextType: (value: boolean) => void;
};

/**
 * Creates the admin menu/runtime controller so `main.ts` can treat admin flows as one subsystem.
 */
export function createAdminController(deps: AdminControllerDeps): {
  setServerAdminMenuActions: (actions: Array<{ id: string; label: string; tooltip?: string }> | null | undefined) => void;
  getAvailableAdminActions: () => AdminMenuAction[];
  openAdminMenu: () => void;
  handleAdminRolesList: (message: Extract<IncomingMessage, { type: 'admin_roles_list' }>) => void;
  handleAdminUsersList: (message: Extract<IncomingMessage, { type: 'admin_users_list' }>) => void;
  handleAdminPlatformOverview: (message: Extract<IncomingMessage, { type: 'admin_platform_overview' }>) => void;
  handleAdminNotificationsList: (message: Extract<IncomingMessage, { type: 'admin_notifications_list' }>) => void;
  openNotifications: () => void;
  handleNotificationsModeInput: (code: string, key: string) => void;
  handleAdminAmbienceCatalog: (message: Extract<IncomingMessage, { type: 'admin_ambience_catalog' }>) => void;
  handleAdminActionResult: (message: Extract<IncomingMessage, { type: 'admin_action_result' }>) => void;
  handleAdminMenuModeInput: (code: string, key: string) => void;
  handleAdminRoleListModeInput: (code: string, key: string) => void;
  handleAdminRolePermissionListModeInput: (code: string, key: string) => void;
  handleAdminRoleDeleteReplacementModeInput: (code: string, key: string) => void;
  handleAdminUserListModeInput: (code: string, key: string) => void;
  handleAdminUserRoleSelectModeInput: (code: string, key: string) => void;
  handleAdminUserDeleteConfirmModeInput: (code: string, key: string) => void;
  handleAdminRoleNameEditModeInput: (code: string, key: string, ctrlKey: boolean) => void;
  handleAdminAmbienceLocationListModeInput: (code: string, key: string) => void;
  handleAdminAmbienceSoundListModeInput: (code: string, key: string) => void;
} {
  const adminMenuActions: AdminMenuAction[] = [];
  let serverAdminMenuActions: AdminMenuAction[] = [];
  let adminMenuIndex = 0;
  let adminRoles: AdminRoleSummary[] = [];
  let adminRoleIndex = 0;
  let adminPermissionKeys: string[] = [];
  let adminPermissionTooltips: Record<string, string> = {};
  let adminRolePermissionIndex = 0;
  let adminRoleDeleteReplacementIndex = 0;
  let adminUsers: AdminUserSummary[] = [];
  let adminUserIndex = 0;
  let adminPendingUserAction: AdminPendingUserAction = null;
  let adminSelectedRoleName = '';
  let adminSelectedUsername = '';
  let adminPendingUserMutation: AdminPendingUserMutation | null = null;
  let adminDeleteConfirmIndex = 0;
  let adminAmbienceLocations: AdminAmbienceLocation[] = [];
  let adminAmbienceSounds: AdminAmbienceSound[] = [];
  let adminAmbienceLocationIndex = 0;
  let adminAmbienceSoundIndex = 0;
  let adminPendingAmbience: { locationId: string; soundId: string } | null = null;
  let notifications: AdminNotificationSummary[] = [];
  let notificationIndex = 0;
  let notificationScope: 'own' | 'admin' = 'own';
  let notificationReturnMode: 'normal' | 'adminMenu' = 'normal';

  function setListIndex(index: number, length: number): number {
    if (length <= 0) return 0;
    return Math.max(0, Math.min(index, length - 1));
  }

  function formatTimestamp(value: number): string {
    if (!Number.isFinite(value) || value <= 0) return 'unknown time';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'unknown time';
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  }

  function notificationScopeLabel(scope = notificationScope): string {
    return scope === 'admin' ? 'Admin notifications' : 'My notifications';
  }

  function notificationPositionLabel(): string {
    if (notifications.length === 0) return '0 of 0';
    return `${notificationIndex + 1} of ${notifications.length}`;
  }

  function notificationDetail(entry: AdminNotificationSummary): string {
    const state = entry.read ? 'read' : 'unread';
    const kind = entry.kind ? ` Type ${entry.kind}.` : '';
    return `${state} notification ${notificationPositionLabel()}. ${entry.title}. ${entry.message} Received ${formatTimestamp(entry.createdAt)}.${kind}`;
  }

  function announceSelectedNotification(): void {
    const selected = notifications[notificationIndex];
    if (!selected) {
      deps.updateStatus(`${notificationScopeLabel()}. No notifications.`);
      return;
    }
    deps.updateStatus(notificationDetail(selected));
  }

  function userListLabel(entry: AdminUserSummary): string {
    return `${entry.username}, role ${entry.role}, ${entry.status}`;
  }

  function userDetail(entry: AdminUserSummary): string {
    const action =
      adminPendingUserAction === 'set_role'
        ? 'Press Enter to choose a new role.'
        : adminPendingUserAction === 'ban'
          ? 'Press Enter to disable this account.'
          : adminPendingUserAction === 'unban'
            ? 'Press Enter to enable this account.'
            : adminPendingUserAction === 'delete_account'
              ? 'Press Enter to review account deletion.'
              : 'Press Escape to return to the admin menu.';
    return `User ${adminUserIndex + 1} of ${adminUsers.length}. ${entry.username}. Role ${entry.role}. Status ${entry.status}. ${action}`;
  }

  function setServerAdminMenuActions(actions: Array<{ id: string; label: string; tooltip?: string }> | null | undefined): void {
    serverAdminMenuActions = (actions || [])
      .map((entry) => ({
        id: String(entry.id || '').trim(),
        label: String(entry.label || '').trim(),
        tooltip: typeof entry.tooltip === 'string' && entry.tooltip.trim().length > 0 ? entry.tooltip.trim() : undefined,
      }))
      .filter((entry) => entry.id.length > 0 && entry.label.length > 0);
  }

  function getAvailableAdminActions(): AdminMenuAction[] {
    return [...serverAdminMenuActions];
  }

  function openAdminMenu(): void {
    const actions = getAvailableAdminActions();
    if (actions.length === 0) {
      deps.updateStatus('No admin actions available.');
      deps.sfxUiCancel();
      return;
    }
    adminMenuActions.splice(0, adminMenuActions.length, ...actions);
    adminMenuIndex = 0;
    deps.state.mode = 'adminMenu';
    deps.announceMenuEntry('Admin', adminMenuActions[0].label);
  }

  function handleAdminRolesList(message: Extract<IncomingMessage, { type: 'admin_roles_list' }>): void {
    adminRoles = [...message.roles].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
    adminPermissionKeys = [...message.permissionKeys].sort((a, b) => a.localeCompare(b));
    adminPermissionTooltips = { ...(message.permissionTooltips ?? {}) };
    if (adminPendingUserAction === 'set_role' && adminSelectedUsername) {
      deps.state.mode = 'adminUserRoleSelect';
      const selectedUser = adminUsers.find((entry) => entry.username === adminSelectedUsername);
      const currentRoleIndex =
        selectedUser ? adminRoles.findIndex((entry) => entry.name === selectedUser.role) : -1;
      adminRoleIndex = currentRoleIndex >= 0 ? currentRoleIndex : 0;
      const first = adminRoles[0];
      if (first && adminRoles[adminRoleIndex]) {
        deps.announceMenuEntry('Roles', adminRoles[adminRoleIndex].name);
      } else {
        deps.updateStatus('No roles available.');
        deps.sfxUiCancel();
        deps.state.mode = 'normal';
        adminPendingUserAction = null;
        adminSelectedUsername = '';
      }
      return;
    }
    deps.state.mode = 'adminRoleList';
    adminRoleIndex = 0;
    const first = adminRoles[0];
    if (first) {
      deps.announceMenuEntry('Roles', `${first.name}, ${first.userCount}`);
    } else {
      deps.updateStatus('No roles found.');
      deps.sfxUiCancel();
    }
  }

  function handleAdminUsersList(message: Extract<IncomingMessage, { type: 'admin_users_list' }>): void {
    adminUsers = [...message.users].sort((a, b) => a.username.localeCompare(b.username, undefined, { sensitivity: 'base' }));
    if (adminUsers.length === 0) {
      deps.updateStatus('No users available.');
      deps.sfxUiCancel();
      deps.state.mode = 'normal';
      adminPendingUserAction = null;
      return;
    }
    deps.state.mode = 'adminUserList';
    adminUserIndex = 0;
    const first = adminUsers[0];
    deps.announceMenuEntry('Users', userListLabel(first));
  }

  function handleAdminPlatformOverview(message: Extract<IncomingMessage, { type: 'admin_platform_overview' }>): void {
    if (message.scope === 'owned_content') {
      const ownedSummary =
        message.links.length > 0
          ? message.links
              .slice(0, 8)
              .map((entry) => `${entry.title}, ${entry.kind}, ${entry.locationId} at ${entry.x}, ${entry.y}`)
              .join('; ')
          : 'No owned content found.';
      deps.updateStatus(
        `Owned content monitor. ${message.ownedContentCount ?? message.links.length} owned items. ${ownedSummary}`,
      );
      deps.sfxUiBlip();
      return;
    }
    const linkSummary =
      message.links.length > 0
        ? message.links
            .slice(0, 6)
            .map((entry) => {
              const author = entry.author ? ` by ${entry.author}` : '';
              const status = entry.verificationStatus ? `, ${entry.verificationStatus.replaceAll('_', ' ')}` : '';
              return `${entry.title}${author}${status} in ${entry.locationId} at ${entry.x}, ${entry.y}`;
            })
            .join('; ')
        : 'No platform links seeded.';
    const revision = message.expectedClientRevision ? ` Client ${message.expectedClientRevision}.` : '';
    deps.updateStatus(
      `Platform overview. Server ${message.serverVersion}.${revision} ${message.connectedUsers} connected. ${message.itemCount} items, ${message.serviceLinkCount} platform links. ${linkSummary}`,
    );
    deps.sfxUiBlip();
  }

  function handleAdminNotificationsList(message: Extract<IncomingMessage, { type: 'admin_notifications_list' }>): void {
    notifications = [...message.notifications];
    notificationScope = message.scope === 'admin' ? 'admin' : 'own';
    notificationIndex = setListIndex(notificationIndex, notifications.length);
    deps.state.mode = 'notifications';
    const scopeLabel = notificationScopeLabel(notificationScope);
    const selected = notifications[notificationIndex];
    if (selected) {
      deps.updateStatus(`${scopeLabel}. ${message.unreadCount} unread. ${notificationDetail(selected)} Use arrows to move, Space for details, R to refresh, Enter to mark selected read, A to mark all visible read.`);
    } else {
      deps.updateStatus(`${scopeLabel}. No notifications. Press R or Enter to refresh, Escape to close.`);
    }
    deps.sfxUiBlip();
  }

  function openNotifications(): void {
    notificationScope = 'own';
    notificationIndex = 0;
    notificationReturnMode = 'normal';
    deps.state.mode = 'notifications';
    deps.signalingSend({ type: 'admin_notifications_list', scope: 'own' });
    deps.updateStatus('Loading notifications...');
  }

  function handleNotificationsModeInput(code: string, key: string): void {
    if (code === 'Escape') {
      deps.state.mode = notificationReturnMode;
      deps.updateStatus(notificationReturnMode === 'adminMenu' ? 'Admin menu.' : 'Closed notifications.');
      deps.sfxUiCancel();
      return;
    }
    if (code === 'KeyM' && key.toLowerCase() === 'm') {
      notificationScope = 'own';
      notificationIndex = 0;
      deps.signalingSend({ type: 'admin_notifications_list', scope: 'own' });
      deps.updateStatus('Loading my notifications...');
      return;
    }
    if (code === 'KeyG' && key.toLowerCase() === 'g') {
      notificationScope = 'admin';
      notificationIndex = 0;
      deps.signalingSend({ type: 'admin_notifications_list', scope: 'admin' });
      deps.updateStatus('Loading admin notifications...');
      return;
    }
    if (code === 'KeyR' && key.toLowerCase() === 'r') {
      deps.signalingSend({ type: 'admin_notifications_list', scope: notificationScope });
      deps.updateStatus('Refreshing notifications...');
      return;
    }
    if (notifications.length === 0) {
      if (code === 'Enter' || code === 'Space') {
        deps.signalingSend({ type: 'admin_notifications_list', scope: notificationScope });
        deps.updateStatus('Refreshing notifications...');
      }
      return;
    }
    if (code === 'Home') {
      notificationIndex = 0;
      announceSelectedNotification();
      deps.sfxUiBlip();
      return;
    }
    if (code === 'End') {
      notificationIndex = notifications.length - 1;
      announceSelectedNotification();
      deps.sfxUiBlip();
      return;
    }
    if (code === 'PageDown' || code === 'PageUp') {
      const delta = code === 'PageDown' ? 5 : -5;
      notificationIndex = setListIndex(notificationIndex + delta, notifications.length);
      announceSelectedNotification();
      deps.sfxUiBlip();
      return;
    }
    const delta = code === 'ArrowDown' || key === 'j' ? 1 : code === 'ArrowUp' || key === 'k' ? -1 : 0;
    if (delta) {
      notificationIndex = (notificationIndex + delta + notifications.length) % notifications.length;
      announceSelectedNotification();
      deps.sfxUiBlip();
      return;
    }
    if (code === 'Space') {
      const selected = notifications[notificationIndex];
      if (selected) deps.updateStatus(notificationDetail(selected));
      deps.sfxUiBlip();
      return;
    }
    if (code === 'Enter') {
      const selected = notifications[notificationIndex];
      deps.signalingSend({ type: 'admin_notification_mark_read', scope: notificationScope, notificationId: selected?.id });
      deps.updateStatus(selected ? 'Marking notification read...' : 'Marking notifications read...');
      return;
    }
    if (code === 'KeyA' && key.toLowerCase() === 'a') {
      deps.signalingSend({ type: 'admin_notification_mark_read', scope: notificationScope });
      deps.updateStatus('Marking all visible notifications read...');
    }
  }

  function ambienceLocationLabel(entry: AdminAmbienceLocation): string {
    return `${entry.name}, current ${entry.currentSoundLabel || 'not assigned'}`;
  }

  function handleAdminAmbienceCatalog(message: Extract<IncomingMessage, { type: 'admin_ambience_catalog' }>): void {
    adminAmbienceLocations = [...message.locations];
    adminAmbienceSounds = [...message.sounds].sort((a, b) =>
      a.category.localeCompare(b.category) || a.label.localeCompare(b.label));
    adminAmbienceLocationIndex = 0;
    deps.state.mode = 'adminAmbienceLocationList';
    if (adminAmbienceLocations[0]) deps.announceMenuEntry('Location ambience', ambienceLocationLabel(adminAmbienceLocations[0]));
    else deps.updateStatus('No world locations available.');
  }

  function handleAdminActionResult(message: Extract<IncomingMessage, { type: 'admin_action_result' }>): void {
    if (message.action === 'location_ambience_set') {
      if (message.ok && adminPendingAmbience) {
        const location = adminAmbienceLocations.find((entry) => entry.id === adminPendingAmbience?.locationId);
        const sound = adminAmbienceSounds.find((entry) => entry.id === adminPendingAmbience?.soundId);
        if (location && sound) {
          location.currentSoundId = sound.id;
          location.currentSoundLabel = sound.label;
        }
        deps.state.mode = 'adminAmbienceLocationList';
      }
      adminPendingAmbience = null;
      deps.updateStatus(message.message);
      message.ok ? deps.sfxUiBlip() : deps.sfxUiCancel();
      return;
    }
    if (message.action === 'notifications_mark_read') {
      deps.signalingSend({ type: 'admin_notifications_list', scope: notificationScope });
      deps.updateStatus(message.message);
      return;
    }
    if (message.action === 'role_update_permissions') {
      return;
    }
    const suppressStatusMessage =
      message.ok && message.action === 'user_set_role' && adminPendingUserMutation?.action === 'set_role';
    if (!suppressStatusMessage) {
      deps.updateStatus(message.message);
    }
    if (!message.ok) {
      adminPendingUserMutation = null;
      deps.sfxUiCancel();
      return;
    }

    if (adminPendingUserMutation) {
      if (adminPendingUserMutation.action === 'set_role') {
        const target = adminUsers.find((entry) => entry.username === adminPendingUserMutation.username);
        if (target) {
          target.role = adminPendingUserMutation.role;
        }
        if (deps.state.mode === 'adminUserRoleSelect') {
          deps.state.mode = 'adminUserList';
          adminPendingUserAction = 'set_role';
          const userIndex = adminUsers.findIndex((entry) => entry.username === adminPendingUserMutation.username);
          if (userIndex >= 0) {
            adminUserIndex = userIndex;
            const selected = adminUsers[adminUserIndex];
            deps.updateStatus(userDetail(selected));
          }
        }
      } else if (adminPendingUserMutation.action === 'ban') {
        adminUsers = adminUsers.filter((entry) => entry.username !== adminPendingUserMutation.username);
        if (deps.state.mode === 'adminUserList' && adminPendingUserAction === 'ban') {
          if (adminUsers.length > 0) {
            adminUserIndex = Math.max(0, Math.min(adminUserIndex, adminUsers.length - 1));
          } else {
            deps.state.mode = 'adminMenu';
            adminPendingUserAction = null;
          }
        }
      } else if (adminPendingUserMutation.action === 'unban') {
        adminUsers = adminUsers.filter((entry) => entry.username !== adminPendingUserMutation.username);
        if (deps.state.mode === 'adminUserList' && adminPendingUserAction === 'unban') {
          if (adminUsers.length > 0) {
            adminUserIndex = Math.max(0, Math.min(adminUserIndex, adminUsers.length - 1));
          } else {
            deps.state.mode = 'adminMenu';
            adminPendingUserAction = null;
          }
        }
      } else if (adminPendingUserMutation.action === 'delete_account') {
        adminUsers = adminUsers.filter((entry) => entry.username !== adminPendingUserMutation.username);
        if (deps.state.mode === 'adminUserList' && adminPendingUserAction === 'delete_account') {
          if (adminUsers.length > 0) {
            adminUserIndex = Math.max(0, Math.min(adminUserIndex, adminUsers.length - 1));
          } else {
            deps.state.mode = 'adminMenu';
            adminPendingUserAction = null;
          }
        }
      }
      adminPendingUserMutation = null;
    }

    if (message.action === 'role_create' && message.role) {
      adminRoles.push({
        id: message.role.id,
        name: message.role.name,
        isSystem: message.role.isSystem,
        userCount: message.role.userCount,
        permissions: [...message.role.permissions],
      });
      adminRoles.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
    }
    if (message.action === 'role_delete' && message.roleName) {
      adminRoles = adminRoles.filter((entry) => entry.name !== message.roleName);
      if (deps.state.mode === 'adminRoleList') {
        adminRoleIndex = Math.max(0, Math.min(adminRoleIndex, Math.max(0, adminRoles.length)));
      }
    }
  }

  function handleAdminMenuModeInput(code: string, key: string): void {
    if (adminMenuActions.length === 0) {
      deps.state.mode = 'normal';
      return;
    }
    const control = handleListControlKey(code, key, adminMenuActions, adminMenuIndex, (entry) => entry.label);
    if (control.type === 'move') {
      adminMenuIndex = control.index;
      deps.updateStatus(adminMenuActions[adminMenuIndex].label);
      deps.sfxUiBlip();
      return;
    }
    if (code === 'Space') {
      deps.updateStatus(adminMenuActions[adminMenuIndex]?.tooltip ?? 'No tooltip available.');
      deps.sfxUiBlip();
      return;
    }
    if (control.type === 'select') {
      const selected = adminMenuActions[adminMenuIndex];
      if (!selected) return;
      if (selected.id === 'platform_overview') {
        deps.signalingSend({ type: 'admin_platform_overview', scope: 'platform' });
        deps.updateStatus('Loading platform overview...');
        return;
      }
      if (selected.id === 'location_ambience') {
        deps.signalingSend({ type: 'admin_ambience_catalog' });
        deps.updateStatus('Loading location ambience library...');
        return;
      }
      if (selected.id === 'owned_content') {
        deps.signalingSend({ type: 'admin_platform_overview', scope: 'owned_content' });
        deps.updateStatus('Loading owned content...');
        return;
      }
      if (selected.id === 'blindsoftware_admin_sync') {
        deps.signalingSend({ type: 'admin_blindsoftware_sync' });
        deps.updateStatus('Running BlindSoftware admin sync...');
        return;
      }
      if (selected.id === 'my_notifications') {
        notificationScope = 'own';
        notificationIndex = 0;
        notificationReturnMode = 'adminMenu';
        deps.signalingSend({ type: 'admin_notifications_list', scope: 'own' });
        deps.updateStatus('Loading notifications...');
        return;
      }
      if (selected.id === 'mark_my_notifications_read') {
        notificationScope = 'own';
        deps.signalingSend({ type: 'admin_notification_mark_read', scope: 'own' });
        deps.updateStatus('Marking notifications read...');
        return;
      }
      if (selected.id === 'admin_notifications') {
        notificationScope = 'admin';
        notificationIndex = 0;
        notificationReturnMode = 'adminMenu';
        deps.signalingSend({ type: 'admin_notifications_list', scope: 'admin' });
        deps.updateStatus('Loading admin notifications...');
        return;
      }
      if (selected.id === 'mark_all_notifications_read') {
        notificationScope = 'admin';
        deps.signalingSend({ type: 'admin_notification_mark_read', scope: 'admin' });
        deps.updateStatus('Marking admin notifications read...');
        return;
      }
      if (selected.id === 'manage_roles') {
        deps.signalingSend({ type: 'admin_roles_list' });
        deps.updateStatus('Loading roles...');
        return;
      }
      if (selected.id === 'change_user_role') {
        adminPendingUserAction = 'set_role';
        deps.signalingSend({ type: 'admin_users_list', action: 'set_role' });
        deps.updateStatus('Loading users...');
        return;
      }
      if (selected.id === 'ban_user') {
        adminPendingUserAction = 'ban';
        deps.signalingSend({ type: 'admin_users_list', action: 'ban' });
        deps.updateStatus('Loading users...');
        return;
      }
      if (selected.id === 'unban_user') {
        adminPendingUserAction = 'unban';
        deps.signalingSend({ type: 'admin_users_list', action: 'unban' });
        deps.updateStatus('Loading users...');
        return;
      }
      if (selected.id === 'delete_account') {
        adminPendingUserAction = 'delete_account';
        deps.signalingSend({ type: 'admin_users_list', action: 'delete_account' });
        deps.updateStatus('Loading users...');
      }
      return;
    }
    if (control.type === 'cancel') {
      deps.state.mode = 'normal';
      deps.updateStatus('Cancelled.');
      deps.sfxUiCancel();
    }
  }

  function handleAdminRoleListModeInput(code: string, key: string): void {
    const entries: Array<{ label: string; role?: AdminRoleSummary }> = [
      ...adminRoles.map((role) => ({ label: `${role.name}, ${role.userCount}`, role })),
      { label: 'Add role' },
    ];
    const control = handleListControlKey(code, key, entries, adminRoleIndex, (entry) => entry.label);
    if (control.type === 'move') {
      adminRoleIndex = control.index;
      deps.updateStatus(entries[adminRoleIndex]?.label || '');
      deps.sfxUiBlip();
      return;
    }
    if (control.type === 'select') {
      const selected = entries[adminRoleIndex];
      if (!selected) return;
      if (!selected.role) {
        deps.state.mode = 'adminRoleNameEdit';
        deps.state.nicknameInput = '';
        deps.state.cursorPos = 0;
        deps.setReplaceTextOnNextType(false);
        deps.updateStatus('New role name.');
        deps.sfxUiBlip();
        return;
      }
      adminSelectedRoleName = selected.role.name;
      adminRolePermissionIndex = 0;
      deps.state.mode = 'adminRolePermissionList';
      deps.updateStatus(`${adminSelectedRoleName} permissions.`);
      deps.sfxUiBlip();
      return;
    }
    if (control.type === 'cancel') {
      deps.state.mode = 'normal';
      deps.updateStatus('Cancelled.');
      deps.sfxUiCancel();
    }
  }

  function handleAdminRolePermissionListModeInput(code: string, key: string): void {
    const role = adminRoles.find((entry) => entry.name === adminSelectedRoleName);
    if (!role) {
      deps.state.mode = 'adminRoleList';
      return;
    }
    const entries = [...adminPermissionKeys, '__delete_role__'];
    const control = handleListControlKey(code, key, entries, adminRolePermissionIndex, (entry) =>
      entry === '__delete_role__' ? `Delete role ${role.name}` : `${entry}: ${role.permissions.includes(entry) ? 'on' : 'off'}`,
    );
    if (control.type === 'move') {
      adminRolePermissionIndex = control.index;
      const value = entries[adminRolePermissionIndex];
      if (value === '__delete_role__') {
        deps.updateStatus(`Delete role ${role.name}.`);
      } else {
        deps.updateStatus(`${value}: ${role.permissions.includes(value) ? 'on' : 'off'}`);
      }
      deps.sfxUiBlip();
      return;
    }
    if (code === 'Space') {
      const value = entries[adminRolePermissionIndex];
      if (value === '__delete_role__') {
        deps.updateStatus('Delete the current role and reassign affected users.');
      } else {
        deps.updateStatus(adminPermissionTooltips[value] || 'No tooltip available.');
      }
      deps.sfxUiBlip();
      return;
    }
    if (control.type === 'select') {
      const value = entries[adminRolePermissionIndex];
      if (value === '__delete_role__') {
        if (role.name === 'admin' || role.name === 'user') {
          deps.updateStatus('Admin and user roles cannot be deleted.');
          deps.sfxUiCancel();
          return;
        }
        const replacementCandidates = adminRoles.filter((entry) => entry.name !== role.name);
        if (replacementCandidates.length === 0) {
          deps.updateStatus('No replacement role available.');
          deps.sfxUiCancel();
          return;
        }
        adminRoleDeleteReplacementIndex = 0;
        deps.state.mode = 'adminRoleDeleteReplacement';
        deps.updateStatus(`Replacement role: ${replacementCandidates[0].name}.`);
        deps.sfxUiBlip();
        return;
      }
      const nextPermissions = new Set(role.permissions);
      if (nextPermissions.has(value)) {
        nextPermissions.delete(value);
      } else {
        nextPermissions.add(value);
      }
      role.permissions = [...nextPermissions].sort((a, b) => a.localeCompare(b));
      deps.signalingSend({ type: 'admin_role_update_permissions', role: role.name, permissions: role.permissions });
      deps.updateStatus(`${value}: ${role.permissions.includes(value) ? 'on' : 'off'}`);
      deps.sfxUiBlip();
      return;
    }
    if (control.type === 'cancel') {
      deps.state.mode = 'adminRoleList';
      deps.updateStatus('Roles.');
      deps.sfxUiCancel();
    }
  }

  function handleAdminRoleDeleteReplacementModeInput(code: string, key: string): void {
    const candidates = adminRoles.filter((entry) => entry.name !== adminSelectedRoleName);
    if (candidates.length === 0) {
      deps.state.mode = 'adminRolePermissionList';
      return;
    }
    const control = handleListControlKey(code, key, candidates, adminRoleDeleteReplacementIndex, (entry) => entry.name);
    if (control.type === 'move') {
      adminRoleDeleteReplacementIndex = control.index;
      deps.updateStatus(candidates[adminRoleDeleteReplacementIndex].name);
      deps.sfxUiBlip();
      return;
    }
    if (control.type === 'select') {
      const replacement = candidates[adminRoleDeleteReplacementIndex];
      deps.signalingSend({
        type: 'admin_role_delete',
        role: adminSelectedRoleName,
        replacementRole: replacement.name,
      });
      deps.state.mode = 'adminRoleList';
      deps.updateStatus(`Deleting ${adminSelectedRoleName}...`);
      return;
    }
    if (control.type === 'cancel') {
      deps.state.mode = 'adminRolePermissionList';
      deps.updateStatus(`${adminSelectedRoleName} permissions.`);
      deps.sfxUiCancel();
    }
  }

  function handleAdminUserListModeInput(code: string, key: string): void {
    if (adminUsers.length === 0) {
      deps.state.mode = 'normal';
      adminPendingUserAction = null;
      return;
    }
    if (code === 'Home') {
      adminUserIndex = 0;
      deps.updateStatus(userDetail(adminUsers[adminUserIndex]));
      deps.sfxUiBlip();
      return;
    }
    if (code === 'End') {
      adminUserIndex = adminUsers.length - 1;
      deps.updateStatus(userDetail(adminUsers[adminUserIndex]));
      deps.sfxUiBlip();
      return;
    }
    if (code === 'PageDown' || code === 'PageUp') {
      const delta = code === 'PageDown' ? 5 : -5;
      adminUserIndex = setListIndex(adminUserIndex + delta, adminUsers.length);
      deps.updateStatus(userDetail(adminUsers[adminUserIndex]));
      deps.sfxUiBlip();
      return;
    }
    if (code === 'Space') {
      deps.updateStatus(userDetail(adminUsers[adminUserIndex]));
      deps.sfxUiBlip();
      return;
    }
    const control = handleListControlKey(code, key, adminUsers, adminUserIndex, userListLabel);
    if (control.type === 'move') {
      adminUserIndex = control.index;
      const selected = adminUsers[adminUserIndex];
      deps.updateStatus(userDetail(selected));
      deps.sfxUiBlip();
      return;
    }
    if (control.type === 'select') {
      const selected = adminUsers[adminUserIndex];
      if (!selected) return;
      adminSelectedUsername = selected.username;
      if (adminPendingUserAction === 'set_role') {
        deps.signalingSend({ type: 'admin_roles_list' });
        deps.updateStatus(`Select new role for ${selected.username}.`);
        return;
      }
      if (adminPendingUserAction === 'ban') {
        adminPendingUserMutation = { action: 'ban', username: selected.username };
        deps.signalingSend({ type: 'admin_user_ban', username: selected.username });
        adminPendingUserAction = 'ban';
        deps.updateStatus(`Disabling account ${selected.username}...`);
        return;
      }
      if (adminPendingUserAction === 'unban') {
        adminPendingUserMutation = { action: 'unban', username: selected.username };
        deps.signalingSend({ type: 'admin_user_unban', username: selected.username });
        adminPendingUserAction = 'unban';
        deps.updateStatus(`Enabling account ${selected.username}...`);
        return;
      }
      if (adminPendingUserAction === 'delete_account') {
        adminDeleteConfirmIndex = 0;
        deps.state.mode = 'adminUserDeleteConfirm';
        deps.announceMenuEntry(`Delete account ${selected.username}?`, YES_NO_OPTIONS[adminDeleteConfirmIndex].label);
        return;
      }
      return;
    }
    if (control.type === 'cancel') {
      deps.state.mode = 'adminMenu';
      adminPendingUserAction = null;
      deps.updateStatus('Admin menu.');
      deps.sfxUiCancel();
    }
  }

  function handleAdminUserRoleSelectModeInput(code: string, key: string): void {
    if (adminRoles.length === 0) {
      deps.state.mode = 'normal';
      adminPendingUserAction = null;
      return;
    }
    const control = handleListControlKey(code, key, adminRoles, adminRoleIndex, (entry) => entry.name);
    if (control.type === 'move') {
      adminRoleIndex = control.index;
      deps.updateStatus(adminRoles[adminRoleIndex].name);
      deps.sfxUiBlip();
      return;
    }
    if (control.type === 'select') {
      const selectedRole = adminRoles[adminRoleIndex];
      adminPendingUserMutation = { action: 'set_role', username: adminSelectedUsername, role: selectedRole.name };
      deps.signalingSend({ type: 'admin_user_set_role', username: adminSelectedUsername, role: selectedRole.name });
      return;
    }
    if (control.type === 'cancel') {
      deps.state.mode = 'adminUserList';
      deps.updateStatus('Select user.');
      deps.sfxUiCancel();
    }
  }

  function handleAdminUserDeleteConfirmModeInput(code: string, key: string): void {
    if (!adminSelectedUsername || adminPendingUserAction !== 'delete_account') {
      deps.state.mode = 'adminUserList';
      return;
    }
    const control = handleYesNoMenuInput(code, key, adminDeleteConfirmIndex);
    if (control.type === 'move') {
      adminDeleteConfirmIndex = control.index;
      deps.updateStatus(YES_NO_OPTIONS[adminDeleteConfirmIndex].label);
      deps.sfxUiBlip();
      return;
    }
    if (control.type === 'cancel') {
      deps.state.mode = 'adminUserList';
      const selected = adminUsers[adminUserIndex];
      if (selected) {
        deps.updateStatus(userDetail(selected));
      } else {
        deps.updateStatus('Select user.');
      }
      deps.sfxUiCancel();
      return;
    }
    if (control.type === 'select') {
      const choice = YES_NO_OPTIONS[adminDeleteConfirmIndex];
      if (choice.id === 'no') {
        deps.state.mode = 'adminUserList';
        const selected = adminUsers[adminUserIndex];
        if (selected) {
          deps.updateStatus(userDetail(selected));
        } else {
          deps.updateStatus('Select user.');
        }
        deps.sfxUiCancel();
        return;
      }
      deps.state.mode = 'adminUserList';
      deps.updateStatus(`Deleting account ${adminSelectedUsername}...`);
      adminPendingUserMutation = { action: 'delete_account', username: adminSelectedUsername };
      deps.signalingSend({ type: 'admin_user_delete', username: adminSelectedUsername });
    }
  }

  function handleAdminRoleNameEditModeInput(code: string, key: string, ctrlKey: boolean): void {
    const editAction = getEditSessionAction(code);
    if (editAction === 'submit') {
      const name = deps.state.nicknameInput.trim().toLowerCase();
      if (!name) {
        deps.updateStatus('Role name required.');
        deps.sfxUiCancel();
        return;
      }
      deps.signalingSend({ type: 'admin_role_create', name });
      deps.state.mode = 'adminRoleList';
      deps.state.nicknameInput = '';
      deps.state.cursorPos = 0;
      deps.setReplaceTextOnNextType(false);
      deps.updateStatus(`Creating role ${name}...`);
      return;
    }
    if (editAction === 'cancel') {
      deps.state.mode = 'adminRoleList';
      deps.state.nicknameInput = '';
      deps.state.cursorPos = 0;
      deps.setReplaceTextOnNextType(false);
      deps.updateStatus('Cancelled.');
      deps.sfxUiCancel();
      return;
    }
    deps.applyTextInputEdit(code, key, 32, ctrlKey, true);
  }


  function handleAdminAmbienceLocationListModeInput(code: string, key: string): void {
    const control = handleListControlKey(code, key, adminAmbienceLocations, adminAmbienceLocationIndex, ambienceLocationLabel);
    if (control.type === 'move') {
      adminAmbienceLocationIndex = control.index;
      deps.updateStatus(ambienceLocationLabel(adminAmbienceLocations[adminAmbienceLocationIndex]));
      deps.sfxUiBlip(); return;
    }
    if (control.type === 'select') {
      const location = adminAmbienceLocations[adminAmbienceLocationIndex];
      const currentIndex = adminAmbienceSounds.findIndex((entry) => entry.id === location.currentSoundId);
      adminAmbienceSoundIndex = currentIndex >= 0 ? currentIndex : 0;
      deps.state.mode = 'adminAmbienceSoundList';
      if (adminAmbienceSounds[adminAmbienceSoundIndex]) {
        deps.announceMenuEntry(`Ambience for ${location.name}`, adminAmbienceSounds[adminAmbienceSoundIndex].label);
      } else deps.updateStatus('No ambience sounds available.');
      return;
    }
    if (control.type === 'cancel') { deps.state.mode = 'adminMenu'; deps.updateStatus('Admin menu.'); deps.sfxUiCancel(); }
  }

  function handleAdminAmbienceSoundListModeInput(code: string, key: string): void {
    const control = handleListControlKey(code, key, adminAmbienceSounds, adminAmbienceSoundIndex, (entry) => entry.label);
    if (control.type === 'move') {
      adminAmbienceSoundIndex = control.index;
      deps.updateStatus(adminAmbienceSounds[adminAmbienceSoundIndex].label);
      deps.sfxUiBlip(); return;
    }
    const sound = adminAmbienceSounds[adminAmbienceSoundIndex];
    const location = adminAmbienceLocations[adminAmbienceLocationIndex];
    if (code === 'Space' && sound) {
      deps.updateStatus(`${sound.label}. Source ${sound.sourceFilename}. ${sound.durationSeconds.toFixed(1)} seconds, seamless ${sound.seamCrossfadeSeconds.toFixed(1)} second boundary crossfade, loop ${sound.loopStartSeconds.toFixed(1)} to ${sound.loopEndSeconds.toFixed(1)} seconds.`);
      deps.sfxUiBlip(); return;
    }
    if (control.type === 'select' && sound && location) {
      adminPendingAmbience = { locationId: location.id, soundId: sound.id };
      deps.signalingSend({ type: 'admin_location_ambience_set', locationId: location.id, soundId: sound.id });
      deps.updateStatus(`Assigning ${sound.label} to ${location.name}...`); return;
    }
    if (control.type === 'cancel') { deps.state.mode = 'adminAmbienceLocationList'; deps.updateStatus(ambienceLocationLabel(location)); deps.sfxUiCancel(); }
  }

  return {
    setServerAdminMenuActions,
    getAvailableAdminActions,
    openAdminMenu,
    handleAdminRolesList,
    handleAdminUsersList,
    handleAdminPlatformOverview,
    handleAdminNotificationsList,
    openNotifications,
    handleNotificationsModeInput,
    handleAdminAmbienceCatalog,
    handleAdminActionResult,
    handleAdminMenuModeInput,
    handleAdminRoleListModeInput,
    handleAdminRolePermissionListModeInput,
    handleAdminRoleDeleteReplacementModeInput,
    handleAdminUserListModeInput,
    handleAdminUserRoleSelectModeInput,
    handleAdminUserDeleteConfirmModeInput,
    handleAdminRoleNameEditModeInput,
    handleAdminAmbienceLocationListModeInput,
    handleAdminAmbienceSoundListModeInput,
  };
}
