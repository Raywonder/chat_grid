import { describe, expect, it } from 'vitest';
import { createAdminController } from './adminController';
import type { OutgoingMessage } from '../network/protocol';
import { createInitialState } from '../state/gameState';

function createHarness() {
  const state = createInitialState();
  const sent: OutgoingMessage[] = [];
  const statuses: string[] = [];
  const announcements: Array<{ title: string; firstOption: string }> = [];
  let blips = 0;
  let cancels = 0;
  const controller = createAdminController({
    state,
    signalingSend: (message) => sent.push(message),
    announceMenuEntry: (title, firstOption) => announcements.push({ title, firstOption }),
    updateStatus: (message) => statuses.push(message),
    sfxUiBlip: () => {
      blips += 1;
    },
    sfxUiCancel: () => {
      cancels += 1;
    },
    applyTextInputEdit: () => undefined,
    setReplaceTextOnNextType: () => undefined,
  });
  return {
    state,
    sent,
    statuses,
    announcements,
    get blips() {
      return blips;
    },
    get cancels() {
      return cancels;
    },
    controller,
  };
}

describe('admin controller', () => {
  it('opens notifications from Shift Z admin mode and returns to the admin menu', () => {
    const harness = createHarness();
    harness.controller.setServerAdminMenuActions([
      { id: 'my_notifications', label: 'My notifications', tooltip: 'Read your notifications.' },
    ]);

    harness.controller.openAdminMenu();
    harness.controller.handleAdminMenuModeInput('Enter', 'Enter');

    expect(harness.state.mode).toBe('adminMenu');
    expect(harness.sent).toContainEqual({ type: 'admin_notifications_list', scope: 'own' });

    harness.controller.handleAdminNotificationsList({
      type: 'admin_notifications_list',
      scope: 'own',
      unreadCount: 1,
      notifications: [
        {
          id: 'n1',
          createdAt: 1_720_000_000_000,
          kind: 'account',
          title: 'Welcome',
          message: 'Your account is ready.',
          read: false,
        },
      ],
    });

    expect(harness.state.mode).toBe('notifications');
    expect(harness.statuses.at(-1)).toContain('Use arrows to move');

    harness.controller.handleNotificationsModeInput('Escape', 'Escape');

    expect(harness.state.mode).toBe('adminMenu');
    expect(harness.statuses.at(-1)).toBe('Admin menu.');
  });

  it('supports accessible notification reading, refresh, scope switching, and mark-read actions', () => {
    const harness = createHarness();
    harness.controller.openNotifications();
    harness.controller.handleAdminNotificationsList({
      type: 'admin_notifications_list',
      scope: 'own',
      unreadCount: 2,
      notifications: [
        {
          id: 'n1',
          createdAt: 1_720_000_000_000,
          kind: 'account',
          title: 'First',
          message: 'First message.',
          read: false,
        },
        {
          id: 'n2',
          createdAt: 1_720_000_500_000,
          kind: 'admin',
          title: 'Second',
          message: 'Second message.',
          read: true,
        },
      ],
    });

    harness.controller.handleNotificationsModeInput('ArrowDown', 'ArrowDown');
    expect(harness.statuses.at(-1)).toContain('read notification 2 of 2. Second.');

    harness.controller.handleNotificationsModeInput('Space', ' ');
    expect(harness.statuses.at(-1)).toContain('Second message.');

    harness.controller.handleNotificationsModeInput('Enter', 'Enter');
    expect(harness.sent.at(-1)).toEqual({
      type: 'admin_notification_mark_read',
      scope: 'own',
      notificationId: 'n2',
    });

    harness.controller.handleNotificationsModeInput('KeyA', 'a');
    expect(harness.sent.at(-1)).toEqual({ type: 'admin_notification_mark_read', scope: 'own' });

    harness.controller.handleNotificationsModeInput('KeyR', 'r');
    expect(harness.sent.at(-1)).toEqual({ type: 'admin_notifications_list', scope: 'own' });

    harness.controller.handleNotificationsModeInput('KeyG', 'g');
    expect(harness.sent.at(-1)).toEqual({ type: 'admin_notifications_list', scope: 'admin' });
  });

  it('speaks richer user-list detail before admin user actions', () => {
    const harness = createHarness();
    harness.controller.setServerAdminMenuActions([{ id: 'ban_user', label: 'Disable user' }]);
    harness.controller.openAdminMenu();
    harness.controller.handleAdminMenuModeInput('Enter', 'Enter');
    harness.controller.handleAdminUsersList({
      type: 'admin_users_list',
      users: [
        { id: '1', username: 'alice', role: 'user', status: 'active' },
        { id: '2', username: 'bob', role: 'editor', status: 'active' },
      ],
    });

    harness.controller.handleAdminUserListModeInput('Space', ' ');
    expect(harness.statuses.at(-1)).toContain('User 1 of 2. alice. Role user. Status active.');
    expect(harness.statuses.at(-1)).toContain('Press Enter to disable this account.');

    harness.controller.handleAdminUserListModeInput('End', 'End');
    expect(harness.statuses.at(-1)).toContain('User 2 of 2. bob.');
  });
});
