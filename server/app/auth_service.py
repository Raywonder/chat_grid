"""Account, role, permission, and session persistence service for websocket authentication."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import hashlib
import hmac
import logging
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


SESSION_TTL_MS = 14 * 24 * 60 * 60 * 1000
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 1
ARGON2_HASH_LEN = 32
ARGON2_SALT_LEN = 16
USERNAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")
ROLE_NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")
EXTERNAL_PROVIDER_PATTERN = re.compile(r"^[a-z0-9_.:-]+$")
LOGGER = logging.getLogger("chgrid.server.auth")

PERMISSIONS: tuple[str, ...] = (
    "item.create",
    "item.edit.own",
    "item.edit.any",
    "item.delete.own",
    "item.delete.any",
    "item.use",
    "item.pickup_drop.own",
    "item.pickup_drop.any",
    "item.transfer.own",
    "item.transfer.any",
    "chat.send",
    "voice.send",
    "profile.update_nickname",
    "account.delete.any",
    "user.ban_unban",
    "user.change_role",
    "role.manage",
    "server.manage_settings",
    "server.allow_reboot",
    "notifications.read.any",
)

PERMISSION_DESCRIPTIONS: dict[str, str] = {
    "item.create": "Allow creating new items.",
    "item.edit.own": "Allow editing items created by this user.",
    "item.edit.any": "Allow editing any item.",
    "item.delete.own": "Allow deleting items created by this user.",
    "item.delete.any": "Allow deleting any item.",
    "item.use": "Allow using item primary and secondary actions.",
    "item.pickup_drop.own": "Allow picking up and dropping items created by this user.",
    "item.pickup_drop.any": "Allow picking up and dropping any item.",
    "item.transfer.own": "Allow transferring items created by this user to another user.",
    "item.transfer.any": "Allow transferring any item to another user.",
    "chat.send": "Allow sending chat messages.",
    "voice.send": "Allow transmitting microphone audio.",
    "profile.update_nickname": "Allow changing nickname.",
    "account.delete.any": "Allow deleting other user accounts.",
    "user.ban_unban": "Allow banning and unbanning users.",
    "user.change_role": "Allow assigning user roles.",
    "role.manage": "Allow creating, editing, and deleting roles.",
    "server.manage_settings": "Allow changing server settings.",
    "server.allow_reboot": "Allow scheduling a server reboot from chat command.",
    "notifications.read.any": "Allow reading and managing admin-wide notifications.",
}

DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": set(PERMISSIONS),
    "editor": {
        "item.create",
        "item.edit.own",
        "item.edit.any",
        "item.delete.own",
        "item.delete.any",
        "item.use",
        "item.pickup_drop.own",
        "item.pickup_drop.any",
        "item.transfer.own",
        "item.transfer.any",
        "chat.send",
        "voice.send",
        "profile.update_nickname",
    },
    "user": {
        "item.create",
        "item.edit.own",
        "item.delete.own",
        "item.use",
        "item.pickup_drop.own",
        "item.transfer.own",
        "chat.send",
        "voice.send",
        "profile.update_nickname",
    },
    "guest": {
        "item.use",
        "chat.send",
        "voice.send",
        "profile.update_nickname",
    },
}
DEFAULT_ROLE_ORDER: tuple[str, ...] = ("admin", "editor", "user", "guest")


def _build_dummy_password_hash(password_hasher: PasswordHasher) -> str:
    """Build one deterministic Argon2id hash used to equalize login miss timing."""

    return password_hasher.hash("chgrid_dummy_password")


@dataclass(frozen=True)
class AuthUser:
    """Authenticated account identity details."""

    id: str
    username: str
    role: str
    permissions: tuple[str, ...]
    status: str
    email: str | None
    last_nickname: str | None
    last_x: int | None
    last_y: int | None
    last_location_id: str | None


@dataclass(frozen=True)
class AuthSession:
    """Session validation result with user identity."""

    session_id: str
    token: str
    user: AuthUser


@dataclass(frozen=True)
class EcryptoAccountSummary:
    """Per-user eCrypto account summary linked to an Endiginous auth user."""

    account_id: str
    user_id: str
    username: str
    test_balance: int
    wallet_count: int
    real_wallet_count: int
    test_wallet_count: int
    external_identity_count: int = 0


@dataclass(frozen=True)
class EcryptoWalletSummary:
    """Connected blockchain wallet metadata for one eCrypto account."""

    id: str
    account_id: str
    chain: str
    address: str
    network_mode: str
    label: str | None
    source_label: str | None
    verified_at_ms: int | None
    created_at_ms: int


class AuthError(ValueError):
    """Raised when authentication input or policy checks fail."""


class AuthService:
    """Manages account registration, roles/permissions, and rolling session validation."""

    def __init__(
        self,
        db_path: Path,
        token_hash_secret: str,
        password_min_length: int,
        password_max_length: int,
        username_min_length: int,
        username_max_length: int,
    ):
        """Initialize auth database connection and schema."""

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.password_min_length = max(1, int(password_min_length))
        self.password_max_length = max(
            self.password_min_length, int(password_max_length)
        )
        self.username_min_length = max(1, int(username_min_length))
        self.username_max_length = max(
            self.username_min_length, int(username_max_length)
        )
        secret = token_hash_secret.strip()
        if not secret:
            raise AuthError("CHGRID_AUTH_SECRET is required when auth is enabled.")
        self._token_secret = secret.encode("utf-8")
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn_lock = threading.RLock()
        self._password_hasher = PasswordHasher(
            time_cost=ARGON2_TIME_COST,
            memory_cost=ARGON2_MEMORY_COST,
            parallelism=ARGON2_PARALLELISM,
            hash_len=ARGON2_HASH_LEN,
            salt_len=ARGON2_SALT_LEN,
        )
        self._dummy_password_hash = _build_dummy_password_hash(self._password_hasher)
        self._ensure_schema()

    def close(self) -> None:
        """Close the underlying SQLite connection."""

        with self._conn_lock:
            self._conn.close()

    def bootstrap_admin(
        self, username: str, password: str, email: str | None = None
    ) -> AuthUser:
        """Create the first admin account, or fail if one already exists."""

        if self.has_admin():
            raise AuthError("An admin account already exists.")
        created = self.register(username, password, email=email, role="admin")
        return created.user

    def has_admin(self) -> bool:
        """Return True when at least one active admin account exists."""

        existing = self._db_fetchone(
            """
            SELECT 1
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE r.name = 'admin' AND u.status = 'active'
            LIMIT 1
            """
        )
        return existing is not None

    def list_all_permissions(self) -> list[str]:
        """Return canonical sorted permission key list."""

        return list(PERMISSIONS)

    def list_all_permission_descriptions(self) -> dict[str, str]:
        """Return canonical permission tooltip text keyed by permission id."""

        return {key: PERMISSION_DESCRIPTIONS.get(key, key) for key in PERMISSIONS}

    def get_user_permissions(self, user_id: str) -> set[str]:
        """Return current permission set for one user id."""

        try:
            user_id_value = int(user_id)
        except (TypeError, ValueError):
            return set()
        rows = self._db_fetchall(
            """
            SELECT rp.permission_key
            FROM users u
            JOIN role_permissions rp ON rp.role_id = u.role_id
            WHERE u.id = ?
            """,
            (user_id_value,),
        )
        return {str(row["permission_key"]) for row in rows}

    def has_permission(self, user_id: str, permission_key: str) -> bool:
        """Return whether one user currently has a specific permission key."""

        return permission_key in self.get_user_permissions(user_id)

    def get_username_by_id(self, user_id: str) -> str | None:
        """Return username for one numeric user id, or None when not found."""

        try:
            user_id_value = int(user_id)
        except (TypeError, ValueError):
            return None
        row = self._db_fetchone(
            "SELECT username FROM users WHERE id = ?", (user_id_value,)
        )
        if row is None:
            return None
        return str(row["username"])

    def list_roles_with_counts(self) -> list[dict[str, object]]:
        """Return all roles with permission sets and assigned-user counts."""

        rows = self._db_fetchall(
            """
            SELECT
                r.id,
                r.name,
                r.is_system,
                COUNT(u.id) AS user_count
            FROM roles r
            LEFT JOIN users u ON u.role_id = r.id
            GROUP BY r.id
            ORDER BY r.name ASC
            """
        )
        permissions_by_role = self._permissions_by_role_id()
        return [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "isSystem": bool(int(row["is_system"])),
                "userCount": int(row["user_count"]),
                "permissions": sorted(
                    list(permissions_by_role.get(int(row["id"]), set()))
                ),
            }
            for row in rows
        ]

    def create_role(self, name: str) -> dict[str, object]:
        """Create one custom role with no permissions."""

        normalized = self._normalize_role_name(name)
        self._validate_role_name(normalized)
        now_ms = self.now_ms()
        try:
            self._db_execute(
                "INSERT INTO roles (name, is_system, created_at_ms, updated_at_ms) VALUES (?, 0, ?, ?)",
                (normalized, now_ms, now_ms),
            )
            self._db_commit()
        except sqlite3.IntegrityError as exc:
            raise AuthError("Role already exists.") from exc
        role = self.get_role_by_name(normalized)
        if role is None:
            raise AuthError("Failed to create role.")
        return role

    def get_role_by_name(self, role_name: str) -> dict[str, object] | None:
        """Return one role metadata row by normalized role name."""

        normalized = self._normalize_role_name(role_name)
        row = self._db_fetchone(
            "SELECT id, name, is_system FROM roles WHERE name = ?", (normalized,)
        )
        if row is None:
            return None
        permissions = self._permissions_by_role_id().get(int(row["id"]), set())
        return {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "isSystem": bool(int(row["is_system"])),
            "permissions": sorted(list(permissions)),
        }

    def update_role_permissions(
        self, role_name: str, permission_keys: list[str]
    ) -> set[str]:
        """Replace one role's permission assignment with validated keys."""

        normalized_role = self._normalize_role_name(role_name)
        if normalized_role == "admin":
            raise AuthError("Admin role permissions are locked on.")
        role_row = self._db_fetchone(
            "SELECT id, name FROM roles WHERE name = ?", (normalized_role,)
        )
        if role_row is None:
            raise AuthError("Role not found.")

        validated = self._validate_permission_keys(permission_keys)
        role_id = int(role_row["id"])
        now_ms = self.now_ms()

        self._db_execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        for key in sorted(validated):
            self._db_execute(
                "INSERT INTO role_permissions (role_id, permission_key) VALUES (?, ?)",
                (role_id, key),
            )
        self._db_execute(
            "UPDATE roles SET updated_at_ms = ? WHERE id = ?", (now_ms, role_id)
        )
        self._db_commit()
        return validated

    def delete_role(
        self, role_name: str, replacement_role_name: str
    ) -> tuple[list[str], str]:
        """Delete one role, reassigning users to a replacement role."""

        normalized_role = self._normalize_role_name(role_name)
        normalized_replacement = self._normalize_role_name(replacement_role_name)
        if normalized_role in {"admin", "user"}:
            raise AuthError("Admin and user roles cannot be deleted.")
        if normalized_role == normalized_replacement:
            raise AuthError("Replacement role must differ from deleted role.")

        role_row = self._db_fetchone(
            "SELECT id FROM roles WHERE name = ?", (normalized_role,)
        )
        replacement_row = self._db_fetchone(
            "SELECT id FROM roles WHERE name = ?", (normalized_replacement,)
        )
        if role_row is None:
            raise AuthError("Role not found.")
        if replacement_row is None:
            raise AuthError("Replacement role not found.")

        role_id = int(role_row["id"])
        replacement_id = int(replacement_row["id"])
        affected_rows = self._db_fetchall(
            "SELECT username FROM users WHERE role_id = ?", (role_id,)
        )
        affected_usernames = [str(row["username"]) for row in affected_rows]

        self._db_execute(
            "UPDATE users SET role_id = ?, updated_at_ms = ? WHERE role_id = ?",
            (replacement_id, self.now_ms(), role_id),
        )
        self._db_execute("DELETE FROM roles WHERE id = ?", (role_id,))
        self._db_commit()
        return affected_usernames, normalized_replacement

    def list_users_for_admin(self) -> list[dict[str, str]]:
        """Return users ordered alphabetically with role + status for admin menus."""

        rows = self._db_fetchall(
            """
            SELECT u.id, u.username, r.name AS role_name, u.status
            FROM users u
            JOIN roles r ON r.id = u.role_id
            ORDER BY u.username COLLATE NOCASE ASC
            """
        )
        return [
            {
                "id": str(row["id"]),
                "username": str(row["username"]),
                "role": str(row["role_name"]),
                "status": str(row["status"]),
            }
            for row in rows
        ]

    def set_user_role(
        self, target_username: str, role_name: str, *, actor_user_id: str | None = None
    ) -> str:
        """Assign one user's role by normalized role name."""

        normalized_username = self._normalize_username(target_username)
        normalized_role = self._normalize_role_name(role_name)
        role_row = self._db_fetchone(
            "SELECT id FROM roles WHERE name = ?", (normalized_role,)
        )
        if role_row is None:
            raise AuthError("Role not found.")
        user_row = self._db_fetchone(
            """
            SELECT u.id, u.status, r.name AS role_name
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE u.username = ?
            """,
            (normalized_username,),
        )
        if user_row is None:
            raise AuthError("User not found.")

        current_role = str(user_row["role_name"])
        if (
            current_role == "admin"
            and normalized_role != "admin"
            and self._active_admin_count() <= 1
        ):
            raise AuthError("Cannot change role for the last active admin.")
        if actor_user_id is not None and str(user_row["id"]) == str(actor_user_id):
            if (
                current_role == "admin"
                and normalized_role != "admin"
                and self._active_admin_count() <= 1
            ):
                raise AuthError("Cannot self-demote the last active admin.")

        self._db_execute(
            "UPDATE users SET role_id = ?, updated_at_ms = ? WHERE id = ?",
            (int(role_row["id"]), self.now_ms(), int(user_row["id"])),
        )
        self._db_commit()
        return normalized_username

    def set_user_status(self, target_username: str, status: str) -> str:
        """Set one account status to active/disabled."""

        normalized_username = self._normalize_username(target_username)
        normalized_status = status.strip().lower()
        if normalized_status not in {"active", "disabled"}:
            raise AuthError("Invalid status.")
        user_row = self._db_fetchone(
            """
            SELECT u.id, u.status, r.name AS role_name
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE u.username = ?
            """,
            (normalized_username,),
        )
        if user_row is None:
            raise AuthError("User not found.")
        current_status = str(user_row["status"])
        current_role = str(user_row["role_name"])
        if (
            current_role == "admin"
            and current_status == "active"
            and normalized_status != "active"
            and self._active_admin_count() <= 1
        ):
            raise AuthError("Cannot disable the last active admin.")
        self._db_execute(
            "UPDATE users SET status = ?, updated_at_ms = ? WHERE id = ?",
            (normalized_status, self.now_ms(), int(user_row["id"])),
        )
        self._db_commit()
        return normalized_username

    def delete_user(
        self, target_username: str, *, actor_user_id: str | None = None
    ) -> str:
        """Delete one account and related session/state rows."""

        normalized_username = self._normalize_username(target_username)
        user_row = self._db_fetchone(
            """
            SELECT u.id, u.status, r.name AS role_name
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE u.username = ?
            """,
            (normalized_username,),
        )
        if user_row is None:
            raise AuthError("User not found.")
        user_id = int(user_row["id"])
        current_status = str(user_row["status"])
        current_role = str(user_row["role_name"])
        if (
            current_role == "admin"
            and current_status == "active"
            and self._active_admin_count() <= 1
        ):
            raise AuthError("Cannot delete the last active admin.")
        if actor_user_id is not None and str(user_id) == str(actor_user_id):
            if (
                current_role == "admin"
                and current_status == "active"
                and self._active_admin_count() <= 1
            ):
                raise AuthError(
                    "Cannot delete your own account while you are the last active admin."
                )
        self._db_execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        self._db_execute("DELETE FROM user_state WHERE user_id = ?", (user_id,))
        self._db_execute("DELETE FROM users WHERE id = ?", (user_id,))
        self._db_commit()
        return normalized_username

    def get_user_by_id(self, user_id: str) -> AuthUser | None:
        """Return one user by id with current role and permissions."""

        try:
            user_id_value = int(user_id)
        except (TypeError, ValueError):
            return None
        row = self._db_fetchone(
            """
            SELECT
                u.id,
                u.username,
                r.name AS role_name,
                u.status,
                u.email,
                us.last_nickname,
                us.last_x,
                us.last_y,
                us.last_location_id
            FROM users u
            JOIN roles r ON r.id = u.role_id
            LEFT JOIN user_state us ON us.user_id = u.id
            WHERE u.id = ?
            """,
            (user_id_value,),
        )
        if row is None:
            return None
        return self._row_to_user(row)

    def list_connected_user_ids_for_role(self, role_name: str) -> list[str]:
        """Return user id strings currently assigned to one role name."""

        normalized = self._normalize_role_name(role_name)
        rows = self._db_fetchall(
            """
            SELECT u.id
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE r.name = ?
            """,
            (normalized,),
        )
        return [str(row["id"]) for row in rows]

    def get_user_id_by_username(self, username: str) -> str | None:
        """Return user id for one username, or None when missing."""

        normalized = self._normalize_username(username)
        row = self._db_fetchone(
            "SELECT id FROM users WHERE username = ?", (normalized,)
        )
        if row is None:
            return None
        return str(row["id"])

    def ensure_ecrypto_account(self, user_id: str) -> EcryptoAccountSummary:
        """Create and return the eCrypto account auto-linked to one auth user."""

        user = self.get_user_by_id(user_id)
        if user is None:
            raise AuthError("User not found.")
        user_id_value = int(user.id)
        now_ms = self.now_ms()
        self._db_execute(
            """
            INSERT OR IGNORE INTO ecrypto_accounts
                (user_id, account_status, created_at_ms, updated_at_ms)
            VALUES (?, 'active', ?, ?)
            """,
            (user_id_value, now_ms, now_ms),
        )
        self._db_commit()
        return self.get_ecrypto_account_summary(user.id)

    def get_ecrypto_account_summary(self, user_id: str) -> EcryptoAccountSummary:
        """Return one user's eCrypto account, creating it when needed."""

        user = self.get_user_by_id(user_id)
        if user is None:
            raise AuthError("User not found.")
        row = self._db_fetchone(
            "SELECT id FROM ecrypto_accounts WHERE user_id = ?", (int(user.id),)
        )
        if row is None:
            return self.ensure_ecrypto_account(user.id)
        account_id = int(row["id"])
        balance = self._ecrypto_test_balance_for_account(account_id)
        wallets = self.list_ecrypto_wallets(user.id)
        return EcryptoAccountSummary(
            account_id=str(account_id),
            user_id=user.id,
            username=user.username,
            test_balance=balance,
            wallet_count=len(wallets),
            real_wallet_count=sum(
                1 for wallet in wallets if wallet.network_mode == "real"
            ),
            test_wallet_count=sum(
                1 for wallet in wallets if wallet.network_mode == "test"
            ),
            external_identity_count=self._external_identity_count_for_user(int(user.id)),
        )

    def list_ecrypto_wallets(self, user_id: str) -> list[EcryptoWalletSummary]:
        """Return blockchain wallets connected to one user's eCrypto account."""

        user = self.get_user_by_id(user_id)
        if user is None:
            raise AuthError("User not found.")
        account_row = self._db_fetchone(
            "SELECT id FROM ecrypto_accounts WHERE user_id = ?", (int(user.id),)
        )
        if account_row is None:
            self.ensure_ecrypto_account(user.id)
            account_row = self._db_fetchone(
                "SELECT id FROM ecrypto_accounts WHERE user_id = ?", (int(user.id),)
            )
        if account_row is None:
            raise AuthError("eCrypto account unavailable.")
        rows = self._db_fetchall(
            """
            SELECT id, account_id, chain, address, network_mode, label, source_label, verified_at_ms, created_at_ms
            FROM ecrypto_wallets
            WHERE account_id = ?
            ORDER BY network_mode ASC, chain ASC, created_at_ms ASC
            """,
            (int(account_row["id"]),),
        )
        return [
            EcryptoWalletSummary(
                id=str(row["id"]),
                account_id=str(row["account_id"]),
                chain=str(row["chain"]),
                address=str(row["address"]),
                network_mode=str(row["network_mode"]),
                label=str(row["label"]) if row["label"] is not None else None,
                source_label=(
                    str(row["source_label"])
                    if "source_label" in row.keys() and row["source_label"] is not None
                    else None
                ),
                verified_at_ms=(
                    int(row["verified_at_ms"])
                    if row["verified_at_ms"] is not None
                    else None
                ),
                created_at_ms=int(row["created_at_ms"]),
            )
            for row in rows
        ]

    def connect_ecrypto_wallet(
        self,
        user_id: str,
        *,
        chain: str,
        address: str,
        network_mode: str,
        label: str | None = None,
        source_label: str | None = None,
        verified: bool = False,
    ) -> EcryptoWalletSummary:
        """Attach or update a wallet link for one eCrypto account."""

        summary = self.ensure_ecrypto_account(user_id)
        normalized_chain = self._normalize_ecrypto_token(chain, field_name="chain")
        normalized_address = self._normalize_wallet_address(address)
        normalized_mode = network_mode.strip().casefold()
        if normalized_mode not in {"test", "real"}:
            raise AuthError("Network mode must be test or real.")
        clean_label = str(label or "").strip()[:80] or None
        clean_source = self._normalize_wallet_source_label(source_label)
        now_ms = self.now_ms()
        verified_at_ms = now_ms if verified else None
        self._db_execute(
            """
            INSERT INTO ecrypto_wallets
                (account_id, chain, address, network_mode, label, source_label, verified_at_ms, created_at_ms, updated_at_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, chain, address, network_mode)
            DO UPDATE SET
                label = excluded.label,
                source_label = COALESCE(excluded.source_label, ecrypto_wallets.source_label),
                verified_at_ms = COALESCE(excluded.verified_at_ms, ecrypto_wallets.verified_at_ms),
                updated_at_ms = excluded.updated_at_ms
            """,
            (
                int(summary.account_id),
                normalized_chain,
                normalized_address,
                normalized_mode,
                clean_label,
                clean_source,
                verified_at_ms,
                now_ms,
                now_ms,
            ),
        )
        self._db_commit()
        row = self._db_fetchone(
            """
            SELECT id, account_id, chain, address, network_mode, label, source_label, verified_at_ms, created_at_ms
            FROM ecrypto_wallets
            WHERE account_id = ? AND chain = ? AND address = ? AND network_mode = ?
            """,
            (
                int(summary.account_id),
                normalized_chain,
                normalized_address,
                normalized_mode,
            ),
        )
        if row is None:
            raise AuthError("Wallet link was not saved.")
        return EcryptoWalletSummary(
            id=str(row["id"]),
            account_id=str(row["account_id"]),
            chain=str(row["chain"]),
            address=str(row["address"]),
            network_mode=str(row["network_mode"]),
            label=str(row["label"]) if row["label"] is not None else None,
            source_label=(
                str(row["source_label"])
                if "source_label" in row.keys() and row["source_label"] is not None
                else None
            ),
            verified_at_ms=(
                int(row["verified_at_ms"]) if row["verified_at_ms"] is not None else None
            ),
            created_at_ms=int(row["created_at_ms"]),
        )

    def list_ecrypto_account_summaries(self) -> list[EcryptoAccountSummary]:
        """Return safe per-user eCrypto summaries for admin/agent inventory views."""

        rows = self._db_fetchall(
            """
            SELECT u.id
            FROM users u
            WHERE u.status = 'active'
            ORDER BY u.username COLLATE NOCASE ASC
            """
        )
        return [self.get_ecrypto_account_summary(str(row["id"])) for row in rows]

    def ecrypto_test_deposit(
        self, user_id: str, amount: int, *, memo: str = "test deposit"
    ) -> EcryptoAccountSummary:
        """Credit one user's test-chain eCrypto balance."""

        if amount <= 0:
            raise AuthError("Amount must be positive.")
        if amount > 1_000_000:
            raise AuthError("Amount is too large for one test deposit.")
        summary = self.ensure_ecrypto_account(user_id)
        now_ms = self.now_ms()
        self._insert_ecrypto_ledger_entry(
            account_id=int(summary.account_id),
            direction="credit",
            amount=amount,
            network_mode="test",
            chain="ecrypto-test",
            memo=memo[:200],
            counterparty_account_id=None,
            tx_ref=f"test-faucet-{now_ms}",
            now_ms=now_ms,
        )
        self._db_commit()
        return self.get_ecrypto_account_summary(user_id)

    def ecrypto_test_transfer(
        self,
        from_user_id: str,
        to_user_id: str,
        amount: int,
        *,
        memo: str = "",
    ) -> tuple[EcryptoAccountSummary, EcryptoAccountSummary]:
        """Move test-chain eCrypto between two linked Endiginous accounts."""

        if amount <= 0:
            raise AuthError("Amount must be positive.")
        if amount > 1_000_000:
            raise AuthError("Amount is too large for one test transfer.")
        sender = self.ensure_ecrypto_account(from_user_id)
        recipient = self.ensure_ecrypto_account(to_user_id)
        if sender.account_id == recipient.account_id:
            raise AuthError("Choose another user for a transfer.")
        if sender.test_balance < amount:
            raise AuthError("Insufficient test eCrypto balance.")
        now_ms = self.now_ms()
        tx_ref = f"test-transfer-{now_ms}-{sender.account_id}-{recipient.account_id}"
        clean_memo = str(memo or "").strip()[:200]
        self._insert_ecrypto_ledger_entry(
            account_id=int(sender.account_id),
            direction="debit",
            amount=amount,
            network_mode="test",
            chain="ecrypto-test",
            memo=clean_memo,
            counterparty_account_id=int(recipient.account_id),
            tx_ref=tx_ref,
            now_ms=now_ms,
        )
        self._insert_ecrypto_ledger_entry(
            account_id=int(recipient.account_id),
            direction="credit",
            amount=amount,
            network_mode="test",
            chain="ecrypto-test",
            memo=clean_memo,
            counterparty_account_id=int(sender.account_id),
            tx_ref=tx_ref,
            now_ms=now_ms,
        )
        self._db_commit()
        return (
            self.get_ecrypto_account_summary(from_user_id),
            self.get_ecrypto_account_summary(to_user_id),
        )

    def register(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
        role: str = "user",
    ) -> AuthSession:
        """Register an account and issue a session token."""

        normalized_username = self._normalize_username(username)
        normalized_role = self._normalize_role_name(role)
        try:
            self._validate_username(normalized_username)
            self._validate_password(password)
            self._validate_role_name(normalized_role)
            normalized_email = self._normalize_email(email)
            role_row = self._db_fetchone(
                "SELECT id FROM roles WHERE name = ?", (normalized_role,)
            )
            if role_row is None:
                raise AuthError("Role not found.")
            now_ms = self.now_ms()
            password_hash = self._hash_password(password)
            self._db_execute(
                """
                INSERT INTO users (
                    username, password_hash, email, role_id, status, created_at_ms, updated_at_ms, last_login_at_ms
                ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    normalized_username,
                    password_hash,
                    normalized_email,
                    int(role_row["id"]),
                    now_ms,
                    now_ms,
                    now_ms,
                ),
            )
            self._db_commit()
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "users.username" in message:
                LOGGER.warning(
                    "register rejected username_taken username=%s", normalized_username
                )
                raise AuthError("Username is already taken.") from exc
            if "users.email" in message:
                LOGGER.warning(
                    "register rejected email_taken username=%s", normalized_username
                )
                raise AuthError("Email is already in use.") from exc
            LOGGER.exception(
                "register sqlite integrity failure username=%s", normalized_username
            )
            raise AuthError(
                "Registration failed due to a database constraint."
            ) from exc
        except AuthError as exc:
            LOGGER.warning(
                "register rejected username=%s reason=%s", normalized_username, str(exc)
            )
            raise
        except Exception as exc:
            LOGGER.exception(
                "register unexpected failure username=%s", normalized_username
            )
            raise AuthError("Registration failed due to a server error.") from exc

        user = self._get_user_by_username(normalized_username)
        if user is None:
            LOGGER.error(
                "register created user missing username=%s", normalized_username
            )
            raise AuthError("Failed to load newly created user.")
        self._db_execute(
            """
            INSERT OR IGNORE INTO user_state (user_id, last_nickname, last_x, last_y, last_location_id, updated_at_ms)
            VALUES (?, ?, NULL, NULL, 'city', ?)
            """,
            (int(user.id), user.username, self.now_ms()),
        )
        self._db_commit()
        user = AuthUser(
            id=user.id,
            username=user.username,
            role=user.role,
            permissions=user.permissions,
            status=user.status,
            email=user.email,
            last_nickname=user.username,
            last_x=user.last_x,
            last_y=user.last_y,
            last_location_id=user.last_location_id,
        )
        return self._create_session(user)

    def login(self, username: str, password: str) -> AuthSession:
        """Authenticate credentials and issue a fresh session."""

        normalized_username = self._normalize_username(username)
        user_row = self._db_fetchone(
            """
            SELECT
                u.id,
                u.username,
                u.password_hash,
                u.email,
                r.name AS role_name,
                u.status,
                us.last_nickname,
                us.last_x,
                us.last_y,
                us.last_location_id
            FROM users u
            JOIN roles r ON r.id = u.role_id
            LEFT JOIN user_state us ON us.user_id = u.id
            WHERE u.username = ?
            """,
            (normalized_username,),
        )
        if user_row is None:
            self._verify_password(password, self._dummy_password_hash)
            raise AuthError("Invalid username or password.")
        if user_row["status"] != "active":
            raise AuthError("Account is disabled.")
        if not self._verify_password(password, user_row["password_hash"]):
            raise AuthError("Invalid username or password.")
        if self._password_hasher.check_needs_rehash(user_row["password_hash"]):
            self._db_execute(
                "UPDATE users SET password_hash = ?, updated_at_ms = ? WHERE id = ?",
                (self._hash_password(password), self.now_ms(), user_row["id"]),
            )
        user = self._row_to_user(user_row)
        if not user.last_nickname:
            self.set_last_nickname(user.id, user.username)
            user = AuthUser(
                id=user.id,
                username=user.username,
                role=user.role,
                permissions=user.permissions,
                status=user.status,
                email=user.email,
                last_nickname=user.username,
                last_x=user.last_x,
                last_y=user.last_y,
                last_location_id=user.last_location_id,
            )
        now_ms = self.now_ms()
        self._db_execute(
            "UPDATE users SET last_login_at_ms = ?, updated_at_ms = ? WHERE id = ?",
            (now_ms, now_ms, user.id),
        )
        self._db_commit()
        return self._create_session(user)

    def login_external(
        self,
        *,
        provider: str,
        subject: str,
        username: str,
        email: str | None = None,
        role: str = "user",
        display_name: str | None = None,
    ) -> AuthSession:
        """Authenticate a verified external identity and issue an Endiginous session."""

        normalized_provider = self._normalize_external_provider(provider)
        normalized_subject = subject.strip()
        if not normalized_subject:
            raise AuthError("External account is missing an identity subject.")
        normalized_email = self._normalize_email(email)
        normalized_role = self._external_role_name(role)

        with self._conn_lock:
            identity_row = self._conn.execute(
                """
                SELECT user_id
                FROM external_identities
                WHERE provider = ? AND subject = ?
                """,
                (normalized_provider, normalized_subject),
            ).fetchone()
            if identity_row is not None:
                user_id = int(identity_row["user_id"])
                self._sync_external_user_profile(
                    user_id=user_id,
                    email=normalized_email,
                    role=normalized_role,
                    display_name=display_name,
                )
                self._conn.commit()
                user = self.get_user_by_id(str(user_id))
                if user is None:
                    raise AuthError("Linked Endiginous account was not found.")
                return self._create_session(user)

            user_id = self._find_existing_external_user_id(
                normalized_email, self._normalize_username(username)
            )
            if user_id is None:
                user_id = self._create_external_user(
                    username=username,
                    email=normalized_email,
                    role=normalized_role,
                    display_name=display_name,
                )
            else:
                self._sync_external_user_profile(
                    user_id=user_id,
                    email=normalized_email,
                    role=normalized_role,
                    display_name=display_name,
                )

            now_ms = self.now_ms()
            self._conn.execute(
                """
                INSERT INTO external_identities (
                    provider, subject, user_id, created_at_ms, last_login_at_ms
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(provider, subject) DO UPDATE SET
                    user_id = excluded.user_id,
                    last_login_at_ms = excluded.last_login_at_ms
                """,
                (normalized_provider, normalized_subject, user_id, now_ms, now_ms),
            )
            self._conn.commit()

        user = self.get_user_by_id(str(user_id))
        if user is None:
            raise AuthError("Failed to load external Endiginous account.")
        return self._create_session(user)

    def login_external_assertion(
        self, assertion: str, *, signing_secret: str, expected_audience: str = "chatgrid"
    ) -> AuthSession:
        """Validate a signed external-login assertion and issue a session."""

        payload = self._verify_external_assertion(
            assertion, signing_secret=signing_secret, expected_audience=expected_audience
        )
        nonce = str(payload.get("nonce", "")).strip()
        if not nonce:
            raise AuthError("External sign-in token is missing a nonce.")
        exp = int(payload.get("exp", 0))
        self._consume_external_nonce(nonce, exp)

        provider = str(payload.get("provider") or payload.get("iss") or "external")
        subject = str(payload.get("sub") or "")
        if subject.startswith(f"{provider}:"):
            subject = subject[len(provider) + 1 :]
        return self.login_external(
            provider=provider,
            subject=subject,
            username=str(payload.get("username") or ""),
            email=str(payload.get("email") or "") or None,
            role=str(payload.get("role") or "user"),
            display_name=str(payload.get("displayName") or "") or None,
        )

    def resume(self, token: str) -> AuthSession:
        """Validate a session token and apply rolling expiry."""

        cleaned = token.strip()
        if not cleaned:
            raise AuthError("Missing session token.")
        token_hash = self._hash_token(cleaned)
        row = self._db_fetchone(
            """
            SELECT s.id AS session_id, s.user_id, s.expires_at_ms, s.revoked_at_ms,
                   u.username, r.name AS role_name, u.status, u.email, us.last_nickname, us.last_x, us.last_y, us.last_location_id
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            JOIN roles r ON r.id = u.role_id
            LEFT JOIN user_state us ON us.user_id = u.id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        )
        if row is None:
            raise AuthError("Invalid session.")
        if row["revoked_at_ms"] is not None:
            raise AuthError("Session has been revoked.")
        now_ms = self.now_ms()
        if int(row["expires_at_ms"]) <= now_ms:
            self._db_execute(
                "UPDATE sessions SET revoked_at_ms = ? WHERE id = ?",
                (now_ms, row["session_id"]),
            )
            self._db_commit()
            raise AuthError("Session has expired.")
        if row["status"] != "active":
            raise AuthError("Account is disabled.")
        new_expiry = now_ms + SESSION_TTL_MS
        self._db_execute(
            "UPDATE sessions SET last_seen_at_ms = ?, expires_at_ms = ? WHERE id = ?",
            (now_ms, new_expiry, row["session_id"]),
        )
        self._db_commit()
        user = AuthUser(
            id=str(row["user_id"]),
            username=row["username"],
            role=row["role_name"],
            permissions=tuple(sorted(self.get_user_permissions(str(row["user_id"])))),
            status=row["status"],
            email=row["email"],
            last_nickname=row["last_nickname"],
            last_x=row["last_x"] if "last_x" in row.keys() else None,
            last_y=row["last_y"] if "last_y" in row.keys() else None,
            last_location_id=row["last_location_id"] if "last_location_id" in row.keys() else None,
        )
        if not user.last_nickname:
            self.set_last_nickname(user.id, user.username)
            user = AuthUser(
                id=user.id,
                username=user.username,
                role=user.role,
                permissions=user.permissions,
                status=user.status,
                email=user.email,
                last_nickname=user.username,
                last_x=user.last_x,
                last_y=user.last_y,
                last_location_id=user.last_location_id,
            )
        return AuthSession(session_id=str(row["session_id"]), token=cleaned, user=user)

    def revoke(self, token: str) -> None:
        """Revoke a session token if it exists."""

        cleaned = token.strip()
        if not cleaned:
            return
        token_hash = self._hash_token(cleaned)
        self._db_execute(
            "UPDATE sessions SET revoked_at_ms = ? WHERE token_hash = ? AND revoked_at_ms IS NULL",
            (self.now_ms(), token_hash),
        )
        self._db_commit()

    def set_last_nickname(self, user_id: str, nickname: str) -> None:
        """Persist the most recent nickname for one user."""

        cleaned = nickname.strip()
        if not cleaned:
            return
        try:
            user_id_value = int(user_id)
        except (TypeError, ValueError):
            return
        try:
            self._db_execute(
                """
                INSERT INTO user_state (user_id, last_nickname, last_x, last_y, last_location_id, updated_at_ms)
                VALUES (?, ?, NULL, NULL, COALESCE((SELECT last_location_id FROM user_state WHERE user_id = ?), 'city'), ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_nickname = excluded.last_nickname,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (user_id_value, cleaned, user_id_value, self.now_ms()),
            )
            self._db_commit()
        except sqlite3.IntegrityError:
            self._db_rollback()

    def set_last_position(
        self, user_id: str, x: int, y: int, location_id: str = "city"
    ) -> None:
        """Persist last known world position for one user."""

        try:
            user_id_value = int(user_id)
        except (TypeError, ValueError):
            return
        try:
            self._db_execute(
                """
                INSERT INTO user_state (user_id, last_nickname, last_x, last_y, last_location_id, updated_at_ms)
                VALUES (?, NULL, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_x = excluded.last_x,
                    last_y = excluded.last_y,
                    last_location_id = excluded.last_location_id,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (user_id_value, int(x), int(y), location_id.strip() or "city", self.now_ms()),
            )
            self._db_commit()
        except sqlite3.IntegrityError:
            self._db_rollback()

    def get_ntfy_preferences(self, user_id: str) -> dict[str, object]:
        """Return persisted ntfy delivery preferences for one identity."""

        try:
            user_id_value = int(user_id)
        except (TypeError, ValueError):
            return {"enabled": False, "topic": ""}
        row = self._db_fetchone(
            "SELECT ntfy_enabled, ntfy_topic FROM users WHERE id = ?", (user_id_value,)
        )
        if row is None:
            return {"enabled": False, "topic": ""}
        return {"enabled": bool(row["ntfy_enabled"]), "topic": str(row["ntfy_topic"] or "")}

    def update_ntfy_preferences(
        self, user_id: str, *, enabled: bool, rotate_topic: bool = False
    ) -> dict[str, object]:
        """Persist opt-in state and lazily create or rotate a private topic."""

        current = self.get_ntfy_preferences(user_id)
        topic = str(current["topic"])
        if enabled and (not topic or rotate_topic):
            topic = f"chatgrid-user-{secrets.token_hex(16)}"
        self._db_execute(
            "UPDATE users SET ntfy_enabled = ?, ntfy_topic = ?, updated_at_ms = ? WHERE id = ?",
            (1 if enabled else 0, topic, self.now_ms(), int(user_id)),
        )
        self._db_commit()
        return {"enabled": bool(enabled), "topic": topic}

    def get_flexpbx_dialing_preferences(self, user_id: str) -> dict[str, object]:
        """Return persisted outbound convenience settings for one user."""

        try:
            row = self._db_fetchone(
                "SELECT outbound_enabled, dial_prefixes FROM flexpbx_dialing_settings WHERE user_id = ?",
                (int(user_id),),
            )
        except sqlite3.OperationalError:
            row = None
        if row is None:
            return {"enabled": False, "prefixes": ["9"]}
        try:
            prefixes = json.loads(str(row["dial_prefixes"] or "[\"9\"]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            prefixes = ["9"]
        if not isinstance(prefixes, list):
            prefixes = ["9"]
        return {"enabled": bool(row["outbound_enabled"]), "prefixes": [str(item) for item in prefixes]}

    def update_flexpbx_dialing_preferences(
        self, user_id: str, *, enabled: bool, prefixes: list[str]
    ) -> dict[str, object]:
        """Persist only user convenience settings; PBX eligibility stays server-owned."""

        normalized = sorted({str(prefix).strip() for prefix in prefixes if str(prefix).strip().isdigit()})[:8]
        if not normalized:
            normalized = ["9"]
        self._db_execute(
            """
            INSERT INTO flexpbx_dialing_settings (user_id, outbound_enabled, dial_prefixes, updated_at_ms)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                outbound_enabled = excluded.outbound_enabled,
                dial_prefixes = excluded.dial_prefixes,
                updated_at_ms = excluded.updated_at_ms
            """,
            (int(user_id), 1 if enabled else 0, json.dumps(normalized), self.now_ms()),
        )
        self._db_commit()
        return {"enabled": bool(enabled), "prefixes": normalized}

    @staticmethod
    def now_ms() -> int:
        """Return unix epoch timestamp in milliseconds."""

        return int(time.time() * 1000)

    def _ensure_schema(self) -> None:
        """Create required auth tables and indexes when missing."""

        self._db_execute("PRAGMA foreign_keys = ON")

        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_system INTEGER NOT NULL DEFAULT 0,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL
            )
            """
        )
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS permissions (
                key TEXT PRIMARY KEY,
                description TEXT NOT NULL
            )
            """
        )
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER NOT NULL,
                permission_key TEXT NOT NULL,
                PRIMARY KEY(role_id, permission_key),
                FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE,
                FOREIGN KEY(permission_key) REFERENCES permissions(key) ON DELETE CASCADE
            )
            """
        )

        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT UNIQUE,
                role_id INTEGER,
                status TEXT NOT NULL CHECK(status IN ('active', 'disabled')) DEFAULT 'active',
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                last_login_at_ms INTEGER,
                FOREIGN KEY(role_id) REFERENCES roles(id)
            )
            """
        )

        user_cols = {
            str(row["name"]) for row in self._db_fetchall("PRAGMA table_info(users)")
        }
        if "role_id" not in user_cols:
            self._db_execute("ALTER TABLE users ADD COLUMN role_id INTEGER")
            user_cols.add("role_id")
        if "status" not in user_cols:
            self._db_execute(
                "ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )
        if "created_at_ms" not in user_cols:
            self._db_execute(
                "ALTER TABLE users ADD COLUMN created_at_ms INTEGER NOT NULL DEFAULT 0"
            )
        if "updated_at_ms" not in user_cols:
            self._db_execute(
                "ALTER TABLE users ADD COLUMN updated_at_ms INTEGER NOT NULL DEFAULT 0"
            )
        if "last_login_at_ms" not in user_cols:
            self._db_execute("ALTER TABLE users ADD COLUMN last_login_at_ms INTEGER")
        if "email" not in user_cols:
            self._db_execute("ALTER TABLE users ADD COLUMN email TEXT")
        if "ntfy_enabled" not in user_cols:
            self._db_execute(
                "ALTER TABLE users ADD COLUMN ntfy_enabled INTEGER NOT NULL DEFAULT 0"
            )
        if "ntfy_topic" not in user_cols:
            self._db_execute(
                "ALTER TABLE users ADD COLUMN ntfy_topic TEXT NOT NULL DEFAULT ''"
            )

        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at_ms INTEGER NOT NULL,
                last_seen_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER NOT NULL,
                revoked_at_ms INTEGER,
                ip TEXT,
                user_agent TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS user_state (
                user_id INTEGER PRIMARY KEY,
                last_nickname TEXT,
                last_x INTEGER,
                last_y INTEGER,
                last_location_id TEXT,
                updated_at_ms INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        user_state_cols = {
            str(row["name"])
            for row in self._db_fetchall("PRAGMA table_info(user_state)")
        }
        if "last_location_id" not in user_state_cols:
            self._db_execute("ALTER TABLE user_state ADD COLUMN last_location_id TEXT")
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS external_identities (
                provider TEXT NOT NULL,
                subject TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                created_at_ms INTEGER NOT NULL,
                last_login_at_ms INTEGER NOT NULL,
                PRIMARY KEY(provider, subject),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS flexpbx_dialing_settings (
                user_id INTEGER PRIMARY KEY,
                outbound_enabled INTEGER NOT NULL DEFAULT 0,
                dial_prefixes TEXT NOT NULL DEFAULT '[\"9\"]',
                updated_at_ms INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS external_auth_nonces (
                nonce TEXT PRIMARY KEY,
                expires_at_ms INTEGER NOT NULL,
                used_at_ms INTEGER NOT NULL
            )
            """
        )
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS ecrypto_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                account_status TEXT NOT NULL CHECK(account_status IN ('active', 'disabled')) DEFAULT 'active',
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS ecrypto_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                chain TEXT NOT NULL,
                address TEXT NOT NULL,
                network_mode TEXT NOT NULL CHECK(network_mode IN ('test', 'real')),
                label TEXT,
                source_label TEXT,
                verified_at_ms INTEGER,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                UNIQUE(account_id, chain, address, network_mode),
                FOREIGN KEY(account_id) REFERENCES ecrypto_accounts(id) ON DELETE CASCADE
            )
            """
        )
        ecrypto_wallet_cols = {
            str(row["name"])
            for row in self._db_fetchall("PRAGMA table_info(ecrypto_wallets)")
        }
        if "source_label" not in ecrypto_wallet_cols:
            self._db_execute("ALTER TABLE ecrypto_wallets ADD COLUMN source_label TEXT")
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS ecrypto_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('credit', 'debit')),
                amount INTEGER NOT NULL CHECK(amount > 0),
                network_mode TEXT NOT NULL CHECK(network_mode IN ('test', 'real')),
                chain TEXT NOT NULL,
                memo TEXT,
                counterparty_account_id INTEGER,
                tx_ref TEXT,
                created_at_ms INTEGER NOT NULL,
                FOREIGN KEY(account_id) REFERENCES ecrypto_accounts(id) ON DELETE CASCADE,
                FOREIGN KEY(counterparty_account_id) REFERENCES ecrypto_accounts(id) ON DELETE SET NULL
            )
            """
        )

        self._seed_permissions_and_roles()
        self._backfill_user_roles()

        self._db_execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )
        self._db_execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at_ms)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_user_state_updated ON user_state(updated_at_ms)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_external_identities_user_id ON external_identities(user_id)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_external_auth_nonces_expires ON external_auth_nonces(expires_at_ms)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_ecrypto_accounts_user_id ON ecrypto_accounts(user_id)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_ecrypto_wallets_account_id ON ecrypto_wallets(account_id)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_ecrypto_ledger_account_id ON ecrypto_ledger(account_id)"
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_ecrypto_ledger_created ON ecrypto_ledger(created_at_ms)"
        )
        self._db_commit()

    def _seed_permissions_and_roles(self) -> None:
        """Insert canonical permissions and default roles when missing."""

        now_ms = self.now_ms()
        for key in PERMISSIONS:
            description = PERMISSION_DESCRIPTIONS.get(key, key)
            self._db_execute(
                "INSERT OR IGNORE INTO permissions (key, description) VALUES (?, ?)",
                (key, description),
            )

        for role_name in DEFAULT_ROLE_ORDER:
            self._db_execute(
                """
                INSERT OR IGNORE INTO roles (name, is_system, created_at_ms, updated_at_ms)
                VALUES (?, 1, ?, ?)
                """,
                (role_name, now_ms, now_ms),
            )

        role_id_by_name = self._role_id_by_name()
        for role_name in DEFAULT_ROLE_ORDER:
            role_id = role_id_by_name.get(role_name)
            if role_id is None:
                continue
            if role_name == "admin":
                # Keep admin as superuser role: always full permission set.
                self._db_execute(
                    "DELETE FROM role_permissions WHERE role_id = ?", (role_id,)
                )
                allowed = set(PERMISSIONS)
            else:
                existing = self._db_fetchall(
                    "SELECT permission_key FROM role_permissions WHERE role_id = ?",
                    (role_id,),
                )
                if existing:
                    # Preserve existing customizations for non-admin defaults.
                    continue
                allowed = DEFAULT_ROLE_PERMISSIONS.get(role_name, set())
            for key in sorted(allowed):
                self._db_execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_key) VALUES (?, ?)",
                    (role_id, key),
                )

    def _backfill_user_roles(self) -> None:
        """Backfill users.role_id defaults for any null role assignment."""

        role_id_by_name = self._role_id_by_name()
        default_user_role_id = role_id_by_name.get("user")
        if default_user_role_id is None:
            raise AuthError("Default user role missing.")
        self._db_execute(
            "UPDATE users SET role_id = ?, updated_at_ms = ? WHERE role_id IS NULL",
            (default_user_role_id, self.now_ms()),
        )

    def _role_id_by_name(self) -> dict[str, int]:
        """Return mapping of role name to role id."""

        rows = self._db_fetchall("SELECT id, name FROM roles")
        return {str(row["name"]): int(row["id"]) for row in rows}

    def _permissions_by_role_id(self) -> dict[int, set[str]]:
        """Return mapping from role id to assigned permission keys."""

        rows = self._db_fetchall("SELECT role_id, permission_key FROM role_permissions")
        permissions_by_role: dict[int, set[str]] = {}
        for row in rows:
            role_id = int(row["role_id"])
            permissions_by_role.setdefault(role_id, set()).add(
                str(row["permission_key"])
            )
        return permissions_by_role

    def _active_admin_count(self) -> int:
        """Return count of active users currently assigned admin role."""

        row = self._db_fetchone(
            """
            SELECT COUNT(*) AS c
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE r.name = 'admin' AND u.status = 'active'
            """
        )
        return int(row["c"]) if row is not None else 0

    def _create_session(self, user: AuthUser) -> AuthSession:
        """Issue and persist a new session token for a user."""

        token = secrets.token_urlsafe(48)
        token_hash = self._hash_token(token)
        now_ms = self.now_ms()
        expires_at_ms = now_ms + SESSION_TTL_MS
        self._db_execute(
            """
            INSERT INTO sessions (user_id, token_hash, created_at_ms, last_seen_at_ms, expires_at_ms, revoked_at_ms, ip, user_agent)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL)
            """,
            (user.id, token_hash, now_ms, now_ms, expires_at_ms),
        )
        row = self._db_fetchone("SELECT last_insert_rowid() AS id")
        if row is None:
            raise AuthError("Failed to create session.")
        session_id = str(row["id"])
        self._db_commit()
        return AuthSession(session_id=session_id, token=token, user=user)

    def _find_existing_external_user_id(
        self, email: str | None, preferred_username: str
    ) -> int | None:
        """Find an existing local account that can safely receive an external link."""

        if email:
            row = self._conn.execute(
                "SELECT id FROM users WHERE lower(email) = ?",
                (email.lower(),),
            ).fetchone()
            if row is not None:
                return int(row["id"])
        if preferred_username:
            row = self._conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (preferred_username,),
            ).fetchone()
            if row is not None:
                return int(row["id"])
        return None

    def _create_external_user(
        self,
        *,
        username: str,
        email: str | None,
        role: str,
        display_name: str | None,
    ) -> int:
        """Create a local Endiginous account for a verified external identity."""

        normalized_username = self._unique_external_username(username, email)
        role_row = self._conn.execute(
            "SELECT id FROM roles WHERE name = ?", (role,)
        ).fetchone()
        if role_row is None:
            raise AuthError("Role not found.")
        now_ms = self.now_ms()
        random_password_hash = self._hash_password(secrets.token_urlsafe(48))
        self._conn.execute(
            """
            INSERT INTO users (
                username, password_hash, email, role_id, status, created_at_ms, updated_at_ms, last_login_at_ms
            ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                normalized_username,
                random_password_hash,
                email,
                int(role_row["id"]),
                now_ms,
                now_ms,
                now_ms,
            ),
        )
        row = self._conn.execute("SELECT last_insert_rowid() AS id").fetchone()
        if row is None:
            raise AuthError("Failed to create external account.")
        user_id = int(row["id"])
        nickname = self._display_name_to_nickname(display_name) or normalized_username
        self._conn.execute(
            """
            INSERT OR IGNORE INTO user_state (user_id, last_nickname, last_x, last_y, last_location_id, updated_at_ms)
            VALUES (?, ?, NULL, NULL, 'city', ?)
            """,
            (user_id, nickname, now_ms),
        )
        return user_id

    def _sync_external_user_profile(
        self,
        *,
        user_id: int,
        email: str | None,
        role: str,
        display_name: str | None,
    ) -> None:
        """Refresh safe local account fields from a verified external account."""

        user_row = self._conn.execute(
            """
            SELECT u.email, r.name AS role_name
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()
        if user_row is None:
            raise AuthError("User not found.")
        role_name = str(user_row["role_name"])
        target_role = role_name if role_name == "admin" and role != "admin" else role
        role_row = self._conn.execute(
            "SELECT id FROM roles WHERE name = ?", (target_role,)
        ).fetchone()
        if role_row is None:
            raise AuthError("Role not found.")

        now_ms = self.now_ms()
        update_email = email if not user_row["email"] else user_row["email"]
        self._conn.execute(
            """
            UPDATE users
            SET email = ?, role_id = ?, status = 'active', last_login_at_ms = ?, updated_at_ms = ?
            WHERE id = ?
            """,
            (update_email, int(role_row["id"]), now_ms, now_ms, user_id),
        )
        nickname = self._display_name_to_nickname(display_name)
        if nickname:
            self._conn.execute(
                """
                INSERT INTO user_state (user_id, last_nickname, last_x, last_y, last_location_id, updated_at_ms)
                VALUES (?, ?, NULL, NULL, COALESCE((SELECT last_location_id FROM user_state WHERE user_id = ?), 'city'), ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_nickname = COALESCE(user_state.last_nickname, excluded.last_nickname),
                    updated_at_ms = excluded.updated_at_ms
                """,
                (user_id, nickname, user_id, now_ms),
            )

    def _unique_external_username(self, username: str, email: str | None) -> str:
        """Return a valid unique username derived from external account fields."""

        candidate = self._normalize_username(username)
        if not candidate and email and "@" in email:
            candidate = self._normalize_username(email.split("@", 1)[0])
        candidate = re.sub(r"[^a-z0-9_-]+", "-", candidate)
        candidate = candidate.strip("-_") or "blind-user"
        max_base_length = max(self.username_min_length, min(self.username_max_length, 24))
        candidate = candidate[:max_base_length].strip("-_") or "blind-user"
        if len(candidate) < self.username_min_length:
            candidate = (candidate + "-user")[: self.username_max_length]

        base = candidate[: self.username_max_length]
        for suffix_index in range(0, 10_000):
            if suffix_index == 0:
                attempt = base
            else:
                suffix = f"-{suffix_index}"
                attempt = f"{base[: self.username_max_length - len(suffix)]}{suffix}"
            if len(attempt) < self.username_min_length:
                continue
            row = self._conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (attempt,)
            ).fetchone()
            if row is None:
                return attempt
        raise AuthError("Could not allocate an Endiginous username.")

    def _consume_external_nonce(self, nonce: str, exp_seconds: int) -> None:
        """Store a one-use external assertion nonce or reject a replay."""

        now_ms = self.now_ms()
        expires_at_ms = int(exp_seconds) * 1000
        self._db_execute(
            "DELETE FROM external_auth_nonces WHERE expires_at_ms < ?",
            (now_ms,),
        )
        try:
            self._db_execute(
                """
                INSERT INTO external_auth_nonces (nonce, expires_at_ms, used_at_ms)
                VALUES (?, ?, ?)
                """,
                (nonce, expires_at_ms, now_ms),
            )
            self._db_commit()
        except sqlite3.IntegrityError as exc:
            self._db_rollback()
            raise AuthError("External sign-in token was already used.") from exc

    def _get_user_by_username(self, username: str) -> AuthUser | None:
        """Fetch one user by normalized username."""

        row = self._db_fetchone(
            """
            SELECT
                u.id,
                u.username,
                r.name AS role_name,
                u.status,
                u.email,
                us.last_nickname,
                us.last_x,
                us.last_y,
                us.last_location_id
            FROM users u
            JOIN roles r ON r.id = u.role_id
            LEFT JOIN user_state us ON us.user_id = u.id
            WHERE u.username = ?
            """,
            (username,),
        )
        if row is None:
            return None
        return self._row_to_user(row)

    def _db_execute(self, sql: str, params: tuple | None = None) -> sqlite3.Cursor:
        """Run one SQL statement with a thread-safe connection lock."""

        with self._conn_lock:
            return self._conn.execute(sql, params or ())

    def _db_fetchone(self, sql: str, params: tuple | None = None) -> sqlite3.Row | None:
        """Run one query and fetch a single row with connection locking."""

        with self._conn_lock:
            return self._conn.execute(sql, params or ()).fetchone()

    def _db_fetchall(self, sql: str, params: tuple | None = None) -> list[sqlite3.Row]:
        """Run one query and fetch all rows with connection locking."""

        with self._conn_lock:
            return self._conn.execute(sql, params or ()).fetchall()

    def _db_commit(self) -> None:
        """Commit pending DB writes with connection locking."""

        with self._conn_lock:
            self._conn.commit()

    def _db_rollback(self) -> None:
        """Rollback pending DB writes with connection locking."""

        with self._conn_lock:
            self._conn.rollback()

    @staticmethod
    def _normalize_ecrypto_token(value: str, *, field_name: str) -> str:
        """Normalize one eCrypto chain/token identifier."""

        token = str(value or "").strip().casefold()
        if not token:
            raise AuthError(f"{field_name} is required.")
        if len(token) > 48:
            raise AuthError(f"{field_name} is too long.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]*", token):
            raise AuthError(
                f"{field_name} can use letters, numbers, underscore, dash, dot, or colon."
            )
        return token

    @staticmethod
    def _normalize_wallet_address(value: str) -> str:
        """Normalize and lightly validate a connected wallet address."""

        address = str(value or "").strip()
        if not address:
            raise AuthError("Wallet address is required.")
        if len(address) > 160:
            raise AuthError("Wallet address is too long.")
        if any(char.isspace() for char in address):
            raise AuthError("Wallet address cannot contain spaces.")
        if not re.fullmatch(r"[A-Za-z0-9:_./=+-]+", address):
            raise AuthError("Wallet address contains unsupported characters.")
        return address

    @staticmethod
    def _normalize_wallet_source_label(value: str | None) -> str | None:
        """Normalize a safe source note for where a wallet reference came from."""

        source = str(value or "").strip()
        if not source:
            return None
        if len(source) > 80:
            raise AuthError("Wallet source label is too long.")
        if any(char in source for char in "\r\n\t"):
            raise AuthError("Wallet source label cannot contain control whitespace.")
        return source

    def _external_identity_count_for_user(self, user_id: int) -> int:
        """Return count of verified external identities tied to one user."""

        row = self._db_fetchone(
            "SELECT COUNT(*) AS c FROM external_identities WHERE user_id = ?",
            (user_id,),
        )
        return int(row["c"]) if row is not None else 0

    def _ecrypto_test_balance_for_account(self, account_id: int) -> int:
        """Return signed test-chain balance for one eCrypto account."""

        row = self._db_fetchone(
            """
            SELECT
                COALESCE(SUM(
                    CASE direction
                        WHEN 'credit' THEN amount
                        WHEN 'debit' THEN -amount
                        ELSE 0
                    END
                ), 0) AS balance
            FROM ecrypto_ledger
            WHERE account_id = ? AND network_mode = 'test'
            """,
            (account_id,),
        )
        if row is None:
            return 0
        return int(row["balance"])

    def _insert_ecrypto_ledger_entry(
        self,
        *,
        account_id: int,
        direction: str,
        amount: int,
        network_mode: str,
        chain: str,
        memo: str,
        counterparty_account_id: int | None,
        tx_ref: str,
        now_ms: int,
    ) -> None:
        """Insert one normalized eCrypto ledger entry without committing."""

        self._db_execute(
            """
            INSERT INTO ecrypto_ledger
                (account_id, direction, amount, network_mode, chain, memo, counterparty_account_id, tx_ref, created_at_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                direction,
                amount,
                network_mode,
                chain,
                memo,
                counterparty_account_id,
                tx_ref,
                now_ms,
            ),
        )

    def _row_to_user(self, row: sqlite3.Row) -> AuthUser:
        """Convert a DB row into AuthUser."""

        user_id = str(row["id"])
        return AuthUser(
            id=user_id,
            username=str(row["username"]),
            role=str(row["role_name"]),
            permissions=tuple(sorted(self.get_user_permissions(user_id))),
            status=str(row["status"]),
            email=row["email"],
            last_nickname=row["last_nickname"]
            if "last_nickname" in row.keys()
            else None,
            last_x=row["last_x"] if "last_x" in row.keys() else None,
            last_y=row["last_y"] if "last_y" in row.keys() else None,
            last_location_id=row["last_location_id"] if "last_location_id" in row.keys() else None,
        )

    @staticmethod
    def _normalize_username(username: str) -> str:
        """Normalize username into canonical stored form."""

        return username.strip().lower()

    @staticmethod
    def _normalize_role_name(role_name: str) -> str:
        """Normalize role names to canonical lowercase identifiers."""

        return role_name.strip().lower()

    @staticmethod
    def _normalize_external_provider(provider: str) -> str:
        """Normalize external identity provider names."""

        normalized = provider.strip().lower()
        if not normalized or len(normalized) > 64:
            raise AuthError("Invalid external sign-in provider.")
        if EXTERNAL_PROVIDER_PATTERN.fullmatch(normalized) is None:
            raise AuthError("Invalid external sign-in provider.")
        return normalized

    @staticmethod
    def _external_role_name(role_name: str) -> str:
        """Map external site roles into Endiginous roles."""

        normalized = role_name.strip().lower()
        if normalized == "admin":
            return "admin"
        if normalized in {"moderator", "editor"}:
            return "editor"
        return "user"

    @staticmethod
    def _display_name_to_nickname(display_name: str | None) -> str:
        """Convert an external display name into a safe initial nickname."""

        cleaned = re.sub(r"\s+", " ", str(display_name or "").strip())
        return cleaned[:32]

    @staticmethod
    def _normalize_email(email: str | None) -> str | None:
        """Normalize optional email and collapse blanks to None."""

        if email is None:
            return None
        cleaned = email.strip().lower()
        return cleaned or None

    def _validate_username(self, username: str) -> None:
        """Validate username against length and character policy."""

        if not (self.username_min_length <= len(username) <= self.username_max_length):
            raise AuthError(
                f"Username must be between {self.username_min_length} and {self.username_max_length} characters."
            )
        if USERNAME_PATTERN.fullmatch(username) is None:
            raise AuthError(
                "Username may include lowercase letters, numbers, underscores, and dashes only."
            )

    @staticmethod
    def _validate_role_name(role_name: str) -> None:
        """Validate role name syntax and max length for custom-role creation."""

        if not role_name:
            raise AuthError("Role name is required.")
        if len(role_name) > 32:
            raise AuthError("Role name must be 32 characters or fewer.")
        if ROLE_NAME_PATTERN.fullmatch(role_name) is None:
            raise AuthError(
                "Role name may include lowercase letters, numbers, underscores, and dashes only."
            )

    @staticmethod
    def _validate_permission_keys(permission_keys: list[str]) -> set[str]:
        """Validate and normalize permission key sets for role updates."""

        validated: set[str] = set()
        for raw in permission_keys:
            key = str(raw).strip()
            if not key:
                continue
            if key not in PERMISSIONS:
                raise AuthError(f"Unknown permission: {key}")
            validated.add(key)
        return validated

    def _validate_password(self, password: str) -> None:
        """Validate password length policy."""

        if not (self.password_min_length <= len(password) <= self.password_max_length):
            raise AuthError(
                f"Password must be between {self.password_min_length} and {self.password_max_length} characters."
            )

    def _hash_password(self, password: str) -> str:
        """Hash a password using Argon2id."""

        return self._password_hasher.hash(password)

    def _verify_password(self, password: str, stored: str) -> bool:
        """Verify plaintext password against stored Argon2id hash."""

        try:
            return bool(self._password_hasher.verify(stored, password))
        except (VerifyMismatchError, InvalidHashError, VerificationError):
            return False

    def _hash_token(self, token: str) -> str:
        """Hash a session token with server secret before persistence."""

        return hmac.new(
            self._token_secret, token.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def _base64url_decode(value: str) -> bytes:
        """Decode unpadded base64url text."""

        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))

    @classmethod
    def _verify_external_assertion(
        cls, assertion: str, *, signing_secret: str, expected_audience: str
    ) -> dict[str, object]:
        """Verify one HMAC-signed external-login assertion payload."""

        secret = signing_secret.strip()
        if not secret:
            raise AuthError("External sign-in is not configured.")
        parts = assertion.strip().split(".")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise AuthError("Invalid external sign-in token.")
        payload_part, signature_part = parts
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            payload_part.encode("ascii"),
            hashlib.sha256,
        ).digest()
        try:
            provided_signature = cls._base64url_decode(signature_part)
        except Exception as exc:
            raise AuthError("Invalid external sign-in token.") from exc
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise AuthError("Invalid external sign-in token.")

        try:
            payload = json.loads(cls._base64url_decode(payload_part))
        except Exception as exc:
            raise AuthError("Invalid external sign-in token.") from exc
        if not isinstance(payload, dict):
            raise AuthError("Invalid external sign-in token.")
        aud = str(payload.get("aud", ""))
        if aud != expected_audience:
            raise AuthError("External sign-in token was issued for a different app.")
        now_seconds = int(time.time())
        exp = int(payload.get("exp", 0))
        iat = int(payload.get("iat", 0))
        if exp <= now_seconds:
            raise AuthError("External sign-in token has expired.")
        if iat > now_seconds + 60:
            raise AuthError("External sign-in token is not valid yet.")
        if exp - now_seconds > 300:
            raise AuthError("External sign-in token expiry is too long.")
        return payload
