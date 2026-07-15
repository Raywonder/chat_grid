"""Server-owned UI metadata for menus and server-backed command surfaces."""

from __future__ import annotations

from typing import TypedDict


class AdminMenuActionDefinition(TypedDict):
    """Server-authored metadata for one admin root action."""

    id: str
    label: str
    tooltip: str
    permission: str


class ItemManagementActionDefinition(TypedDict):
    """Server-authored metadata for one item-management action."""

    id: str
    label: str
    tooltip: str
    anyPermission: str
    ownPermission: str


class MainModeServerCommandDefinition(TypedDict):
    """Server-authored metadata for one server-backed main-mode command."""

    id: str
    label: str
    tooltip: str


ADMIN_MENU_ACTION_DEFINITIONS: tuple[AdminMenuActionDefinition, ...] = (
    {
        "id": "platform_overview",
        "label": "Platform overview",
        "tooltip": "Speak server, user, item, and BlindSoftware platform link status.",
        "permission": "server.manage_settings",
    },
    {
        "id": "blindsoftware_admin_sync",
        "label": "BlindSoftware admin sync",
        "tooltip": "Refresh BlindSoftware-related Chat Grid admin integrations, including public billboards.",
        "permission": "server.manage_settings",
    },
    {
        "id": "owned_content",
        "label": "Owned content",
        "tooltip": "List content you own and where it sits on the grid.",
        "permission": "item.edit.own",
    },
    {
        "id": "my_notifications",
        "label": "My notifications",
        "tooltip": "Read notifications for your logged-in account.",
        "permission": "chat.send",
    },
    {
        "id": "mark_my_notifications_read",
        "label": "Mark my notifications read",
        "tooltip": "Mark your visible notifications as read.",
        "permission": "chat.send",
    },
    {
        "id": "admin_notifications",
        "label": "Admin notifications",
        "tooltip": "Read the admin-wide notification log.",
        "permission": "notifications.read.any",
    },
    {
        "id": "mark_all_notifications_read",
        "label": "Mark all notifications read",
        "tooltip": "Mark admin-visible notifications as read for your account.",
        "permission": "notifications.read.any",
    },
    {
        "id": "manage_roles",
        "label": "Role management",
        "tooltip": "Manage roles and their permission sets.",
        "permission": "role.manage",
    },
    {
        "id": "change_user_role",
        "label": "Change user role",
        "tooltip": "Change a user's assigned role.",
        "permission": "user.change_role",
    },
    {
        "id": "ban_user",
        "label": "Ban user",
        "tooltip": "Disable a user account.",
        "permission": "user.ban_unban",
    },
    {
        "id": "unban_user",
        "label": "Unban user",
        "tooltip": "Re-enable a disabled user account.",
        "permission": "user.ban_unban",
    },
    {
        "id": "delete_account",
        "label": "Delete account",
        "tooltip": "Delete a user account permanently.",
        "permission": "account.delete.any",
    },
)

ITEM_MANAGEMENT_ACTION_DEFINITIONS: tuple[ItemManagementActionDefinition, ...] = (
    {
        "id": "transfer",
        "label": "Transfer item",
        "tooltip": "Transfer this item to another user.",
        "anyPermission": "item.transfer.any",
        "ownPermission": "item.transfer.own",
    },
    {
        "id": "delete",
        "label": "Delete item",
        "tooltip": "Delete this item from the world.",
        "anyPermission": "item.delete.any",
        "ownPermission": "item.delete.own",
    },
)

MAIN_MODE_SERVER_COMMAND_DEFINITIONS: tuple[MainModeServerCommandDefinition, ...] = (
    {"id": "addItem", "label": "Add item", "tooltip": "Open the add-item menu."},
    {
        "id": "useItem",
        "label": "Use item",
        "tooltip": "Use the carried item or a usable item on your current square.",
    },
    {
        "id": "secondaryUseItem",
        "label": "Secondary item action",
        "tooltip": "Run the secondary action for the carried item or a usable item on your current square.",
    },
    {
        "id": "pickupDropItem",
        "label": "Pick up or drop item",
        "tooltip": "Pick up an item, place a carried small item on the focused open surface, or drop it on the floor.",
    },
    {
        "id": "openItemManagement",
        "label": "Item management",
        "tooltip": "Open item management actions for items on your square.",
    },
    {
        "id": "editItem",
        "label": "Edit item properties",
        "tooltip": "Edit the carried item or an item on your current square.",
    },
    {
        "id": "inspectItem",
        "label": "Inspect item properties",
        "tooltip": "Inspect all properties for the carried item or an item on your current square.",
    },
)
