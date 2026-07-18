"""Websocket signaling server for chat, presence, and item interactions."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from collections import deque
from contextlib import suppress
from datetime import datetime, timezone
from getpass import getpass
import ipaddress
import json
import logging
import os
import random
import re
import signal
import ssl
import time
import uuid
from pathlib import Path
from typing import Any, Literal, TypeAlias, TypedDict, cast
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from pydantic import ValidationError, TypeAdapter
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request as HttpRequest, Response as HttpResponse
from websockets.typing import Origin

from .auth_service import AuthError, AuthService
from .blind_productions_billboards import (
    fetch_public_messages as fetch_blind_productions_messages,
    upsert_blind_productions_billboards,
)
from .world_cup_live import (
    fetch_world_cup_status,
    upsert_world_cup_cafe_status,
)
from .client import ClientConnection
from .config import load_config
from .item_catalog import (
    CLOCK_DEFAULT_TIME_ZONE,
    CLOCK_TIME_ZONE_OPTIONS,
    ITEM_TYPE_EDITABLE_PROPERTIES,
    ITEM_TYPE_LABELS,
    ITEM_TYPE_PROPERTY_METADATA,
    ITEM_TYPE_SEQUENCE,
    ITEM_TYPE_TOOLTIPS,
    get_item_definition,
    get_item_global_properties,
    get_item_use_cooldown_ms,
    is_known_item_type,
)
from .item_type_handlers import get_item_type_handler
from .item_service import ItemService
from .items.types.clock.time_format import parse_alarm_time_flexible
from .items.types.house_alarm.actions import evaluate_access as evaluate_house_alarm_access
from .items.types.house_alarm.actions import use_with_credential as use_house_alarm_with_credential
from .items.types.radio_station.aaastreamer import resolve_aaastreamer_playback
from .items.types.service_link.portal_state import effective_portal_state
from .models import (
    AuthExternalPacket,
    AuthLoginPacket,
    AuthLogoutPacket,
    AuthPermissionsPacket,
    AuthRegisterPacket,
    AuthRequiredPacket,
    AuthResultPacket,
    AuthResumePacket,
    NtfyPreferencesGetPacket,
    NtfyPreferencesResultPacket,
    NtfyPreferencesUpdatePacket,
    AdminActionResultPacket,
    AdminAmbienceCatalogPacket,
    AdminAmbienceCatalogResultPacket,
    AdminAmbienceLocationSummary,
    AdminAmbienceSoundSummary,
    AdminLocationAmbienceSetPacket,
    AdminRoleCreatePacket,
    AdminRoleDeletePacket,
    AdminRoleSummary,
    AdminRoleUpdatePermissionsPacket,
    AdminRolesListPacket,
    AdminRolesListResultPacket,
    AdminPlatformLinkSummary,
    AdminPlatformOverviewPacket,
    AdminPlatformOverviewResultPacket,
    AdminBlindSoftwareSyncPacket,
    AdminNotificationMarkReadPacket,
    AdminNotificationSummary,
    AdminNotificationsListPacket,
    AdminNotificationsListResultPacket,
    AdminUserBanPacket,
    AdminUserDeletePacket,
    AdminUserSetRolePacket,
    AdminUserUnbanPacket,
    AdminUserSummary,
    AdminUsersListPacket,
    AdminUsersListResultPacket,
    AgentVoicePacket,
    BroadcastChatMessagePacket,
    BroadcastNicknamePacket,
    BroadcastPositionPacket,
    BroadcastTeleportCompletePacket,
    ChatMessagePacket,
    ChangeLocationPacket,
    ClientPacket,
    DirectMessageBroadcastPacket,
    DirectMessagePacket,
    ForwardSignalPacket,
    ItemActionResultPacket,
    ItemAddPacket,
    ItemClockAnnouncePacket,
    ItemDeletePacket,
    ItemDropPacket,
    ItemGameLaunchPacket,
    ItemInteractPacket,
    ItemPianoNoteBroadcastPacket,
    ItemPianoNotePacket,
    ItemPianoRecordingPacket,
    ItemPianoStatusPacket,
    ItemPickupPacket,
    ItemRemoteControlPacket,
    ItemRemovePacket,
    ItemSecondaryUsePacket,
    ItemTransferPacket,
    ItemTransferTargetSummary,
    ItemTransferTargetsPacket,
    ItemTransferTargetsResultPacket,
    ItemUpdatePacket,
    ItemUpsertPacket,
    ItemUsePacket,
    ItemUseSoundPacket,
    LocationChangedPacket,
    MediaCastPacket,
    MediaCastStatePacket,
    NicknameResultPacket,
    PingPacket,
    PongPacket,
    RemoteUser,
    SignalPacket,
    SocialActionPacket,
    SpeakPacket,
    TeleportCompletePacket,
    UpdateNicknamePacket,
    UpdatePositionPacket,
    UserActionPacket,
    UserActionResultPacket,
    UserLeftPacket,
    WelcomeReadyPacket,
    WelcomePacket,
    WorldConfigUpdatePacket,
    WorldItem,
)
from .network_security import normalize_origin, open_validated_public_url
from .voice_service import VOICE_URL_PREFIX, voice_file_path
from .notification_service import NotificationRecord, NotificationService
from .ntfy_publisher import NtfyPublisher
from .ui_metadata import (
    ADMIN_MENU_ACTION_DEFINITIONS,
    ITEM_MANAGEMENT_ACTION_DEFINITIONS,
    MAIN_MODE_SERVER_COMMAND_DEFINITIONS,
)
from .version import format_server_version
from .world import (
    DEFAULT_LOCATION_ID,
    WORLD_LOCATION_BY_ID,
    WORLD_LOCATIONS,
    WorldLocation,
    get_location,
    location_options_text,
    normalize_location_id,
)

LOGGER = logging.getLogger("chgrid.server")
PACKET_LOGGER = logging.getLogger("chgrid.server.packet")
CLIENT_PACKET_ADAPTER: TypeAdapter[ClientPacket] = TypeAdapter(ClientPacket)
SYSTEM_RANDOM = random.SystemRandom()
MAX_ACTIVE_PIANO_KEYS_PER_CLIENT = 12
MAX_CARRIED_ITEMS_PER_CLIENT = 4
ITEM_AUTO_VERIFY_DELAY_MS = 5 * 60 * 1000
RANDOM_PORTAL_LOCATION_IDS = {
    "city",
    "forest",
    "town",
    "arcade",
    "offices",
    "houses",
}
PLACE_TARGET_ITEM_TYPES = {"cabin", "house", "room", "shack", "shed"}
COMMUNITY_AUTOFIX_INTERVAL_S = 60.0
RAYWONDER_ENTRY_LOCATION_ID = "raywonder_house_entry"
RAYWONDER_STUDIO_LOCATION_ID = "raywonder_house_studio"
RAYWONDER_HOUSE_LOCATION_PREFIX = "raywonder_house_"
STUDIO_ENTRY_INVITE_TTL_S = 120.0
PIANO_RECORDING_MAX_MS = 30_000
PIANO_RECORDING_MAX_EVENTS = 4096
MOVEMENT_TICK_MS = 200
MOVEMENT_MAX_STEPS_PER_TICK = 1
POSITION_PERSIST_DEBOUNCE_MS = 5_000
AUTH_HASH_MAX_CONCURRENCY = 8
AUTH_RATE_LIMIT_WINDOW_S = 30.0
AUTH_RATE_LIMIT_PER_IP = 20
AUTH_RATE_LIMIT_PER_IDENTITY = 8
AUTH_FAILURE_JITTER_MIN_MS = 0.02
AUTH_FAILURE_JITTER_MAX_MS = 0.08
RADIO_METADATA_POLL_INTERVAL_S = 10.0
RADIO_METADATA_TIMEOUT_S = 6.0
CLOCK_ANNOUNCE_POLL_INTERVAL_S = 1.0
HOUSE_KEEPER_AUTO_CHECK_POLL_INTERVAL_S = 30.0
AUTH_SESSION_COOKIE_NAME = "chgrid_session_token"
AUTH_SESSION_COOKIE_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
AUTH_SESSION_COOKIE_SET_PATH = "auth/session/set"
AUTH_SESSION_COOKIE_CLEAR_PATH = "auth/session/clear"
AUTH_SESSION_COOKIE_CHECK_PATH = "auth/session/check"
WEBSOCKET_PATH = "ws"
AUTH_SESSION_COOKIE_CLIENT_HEADER = "X-Chgrid-Auth-Client"
AUTH_LOGIN_FAILURE_MESSAGE = "We couldn't log you in. Check your details and try again."
AUTH_RESUME_FAILURE_MESSAGE = "We couldn't restore your session. Please log in again."
AUTH_EXTERNAL_FAILURE_MESSAGE = "We couldn't complete the blind.software sign-in. Please try again."


def _reaction_sound(action_id: str) -> str:
    """Return the packaged spatial cue for a social action id."""

    sound_aliases = {
        "cuddle": "hug",
        "kiss": "hug",
        "handshake": "tap",
        "hold_hands": "user",
        "blush": "self",
        "cry": "comfort",
        "yawn": "sigh",
        "apologize": "self",
        "forgive": "heart",
    }
    return f"/sounds/reactions/{sound_aliases.get(action_id, action_id)}.mp3"


SOCIAL_ACTIONS: dict[str, dict[str, Any]] = {
    "hug": {
        "aliases": {"hug", "hugs"},
        "sound": "/sounds/reactions/hug.mp3",
        "template": "{actor} hugs {target}.",
        "self_template": "{actor} gives herself a hug.",
        "requires_target": False,
    },
    "cuddle": {
        "aliases": {"cuddle", "cuddles", "snuggle", "snuggles"},
        "sound": "/sounds/reactions/hug.mp3",
        "template": "{actor} cuddles close with {target}.",
        "self_template": "{actor} curls up for a cuddle.",
        "requires_target": False,
    },
    "kiss": {
        "aliases": {"kiss", "kisses", "smooch"},
        "sound": "/sounds/reactions/hug.mp3",
        "template": "{actor} gives {target} an affectionate kiss.",
        "self_template": "{actor} blows a kiss.",
        "requires_target": False,
    },
    "tap": {
        "aliases": {"tap", "taps"},
        "sound": "/sounds/reactions/tap.mp3",
        "template": "{actor} taps {target}.",
        "requires_target": True,
    },
    "hi": {
        "aliases": {"hi", "hello", "wave", "sayhi", "say-hi"},
        "sound": "/sounds/reactions/wave_hi.mp3",
        "template": "{actor} says hi to {target}.",
        "self_template": "{actor} says hi.",
        "requires_target": False,
    },
    "chat": {
        "aliases": {"chat", "startchat", "start-chat"},
        "sound": "/sounds/reactions/chat.mp3",
        "template": "{actor} starts a chat with {target}.",
        "requires_target": True,
    },
    "self": {
        "aliases": {"self", "me"},
        "sound": "/sounds/reactions/self.mp3",
        "self_template": "{actor} reacts to herself.",
        "requires_target": False,
    },
    "user": {
        "aliases": {"user", "notice", "nudge"},
        "sound": "/sounds/reactions/user.mp3",
        "template": "{actor} nudges {target}.",
        "self_template": "{actor} sends a user nudge.",
        "requires_target": False,
    },
    "high_five": {
        "aliases": {"highfive", "high-five", "five"},
        "sound": "/sounds/reactions/tap.mp3",
        "template": "{actor} high-fives {target}.",
        "self_template": "{actor} raises a hand for a high-five.",
        "requires_target": False,
    },
    "fist_bump": {
        "aliases": {"fistbump", "fist-bump", "bump"},
        "sound": "/sounds/reactions/tap.mp3",
        "template": "{actor} fist-bumps {target}.",
        "self_template": "{actor} offers a fist bump.",
        "requires_target": False,
    },
    "handshake": {
        "aliases": {"handshake", "shake-hands", "shakehands"},
        "sound": "/sounds/reactions/tap.mp3",
        "template": "{actor} offers {target} a friendly handshake.",
        "self_template": "{actor} offers a friendly handshake.",
        "requires_target": False,
    },
    "hold_hands": {
        "aliases": {"holdhands", "hold-hands", "handhold"},
        "sound": "/sounds/reactions/user.mp3",
        "template": "{actor} offers to hold {target}'s hand.",
        "self_template": "{actor} holds her hands together.",
        "requires_target": False,
    },
    "cheer": {
        "aliases": {"cheer", "woo", "yay"},
        "sound": "/sounds/reactions/wave_hi.mp3",
        "template": "{actor} cheers for {target}.",
        "self_template": "{actor} cheers.",
        "requires_target": False,
    },
    "clap": {
        "aliases": {"clap", "applaud", "applause"},
        "sound": "/sounds/reactions/tap.mp3",
        "template": "{actor} applauds {target}.",
        "self_template": "{actor} applauds.",
        "requires_target": False,
    },
    "laugh": {
        "aliases": {"laugh", "lol"},
        "sound": "/sounds/reactions/chat.mp3",
        "template": "{actor} laughs with {target}.",
        "self_template": "{actor} laughs.",
        "requires_target": False,
    },
    "smile": {
        "aliases": {"smile", "grin"},
        "sound": "/sounds/reactions/self.mp3",
        "template": "{actor} smiles at {target}.",
        "self_template": "{actor} smiles.",
        "requires_target": False,
    },
    "wink": {
        "aliases": {"wink"},
        "sound": "/sounds/reactions/self.mp3",
        "template": "{actor} winks at {target}.",
        "self_template": "{actor} winks.",
        "requires_target": False,
    },
    "nod": {
        "aliases": {"nod", "agree"},
        "sound": "/sounds/reactions/user.mp3",
        "template": "{actor} nods to {target}.",
        "self_template": "{actor} nods.",
        "requires_target": False,
    },
    "shake_head": {
        "aliases": {"shakehead", "shake-head", "nope"},
        "sound": "/sounds/reactions/user.mp3",
        "template": "{actor} shakes her head at {target}.",
        "self_template": "{actor} shakes her head.",
        "requires_target": False,
    },
    "bow": {
        "aliases": {"bow"},
        "sound": "/sounds/reactions/self.mp3",
        "template": "{actor} bows to {target}.",
        "self_template": "{actor} bows.",
        "requires_target": False,
    },
    "dance": {
        "aliases": {"dance", "groove"},
        "sound": "/sounds/reactions/wave_hi.mp3",
        "template": "{actor} dances near {target}.",
        "self_template": "{actor} dances.",
        "requires_target": False,
    },
    "blush": {
        "aliases": {"blush", "shy"},
        "sound": "/sounds/reactions/self.mp3",
        "template": "{actor} blushes at {target}.",
        "self_template": "{actor} blushes.",
        "requires_target": False,
    },
    "cry": {
        "aliases": {"cry", "cries", "weep"},
        "sound": "/sounds/reactions/comfort.mp3",
        "template": "{actor} cries softly near {target}.",
        "self_template": "{actor} cries softly.",
        "requires_target": False,
    },
    "yawn": {
        "aliases": {"yawn", "sleepy"},
        "sound": "/sounds/reactions/sigh.mp3",
        "template": "{actor} yawns near {target}.",
        "self_template": "{actor} yawns.",
        "requires_target": False,
    },
    "apologize": {
        "aliases": {"apologize", "apology", "sorry"},
        "sound": "/sounds/reactions/self.mp3",
        "template": "{actor} apologizes to {target}.",
        "self_template": "{actor} apologizes.",
        "requires_target": False,
    },
    "forgive": {
        "aliases": {"forgive", "forgives"},
        "sound": "/sounds/reactions/heart.mp3",
        "template": "{actor} forgives {target}.",
        "self_template": "{actor} chooses forgiveness.",
        "requires_target": False,
    },
    "comfort": {
        "aliases": {"comfort", "soothe"},
        "sound": "/sounds/reactions/hug.mp3",
        "template": "{actor} offers comfort to {target}.",
        "self_template": "{actor} takes a steady breath.",
        "requires_target": False,
    },
    "pat_back": {
        "aliases": {"pat", "patback", "pat-back"},
        "sound": "/sounds/reactions/tap.mp3",
        "template": "{actor} pats {target} on the back.",
        "requires_target": True,
    },
    "poke": {
        "aliases": {"poke"},
        "sound": "/sounds/reactions/tap.mp3",
        "template": "{actor} pokes {target}.",
        "requires_target": True,
    },
    "boop": {
        "aliases": {"boop"},
        "sound": "/sounds/reactions/tap.mp3",
        "template": "{actor} boops {target}.",
        "requires_target": True,
    },
    "salute": {
        "aliases": {"salute"},
        "sound": "/sounds/reactions/user.mp3",
        "template": "{actor} salutes {target}.",
        "self_template": "{actor} salutes.",
        "requires_target": False,
    },
    "thumbs_up": {
        "aliases": {"thumbsup", "thumbs-up", "approve"},
        "sound": "/sounds/reactions/user.mp3",
        "template": "{actor} gives {target} a thumbs-up.",
        "self_template": "{actor} gives a thumbs-up.",
        "requires_target": False,
    },
    "heart": {
        "aliases": {"heart", "love"},
        "sound": "/sounds/reactions/hug.mp3",
        "template": "{actor} sends {target} a heart.",
        "self_template": "{actor} sends a heart.",
        "requires_target": False,
    },
    "sparkle": {
        "aliases": {"sparkle", "shine"},
        "sound": "/sounds/reactions/wave_hi.mp3",
        "template": "{actor} sparkles at {target}.",
        "self_template": "{actor} sparkles.",
        "requires_target": False,
    },
    "celebrate": {
        "aliases": {"celebrate", "party"},
        "sound": "/sounds/reactions/wave_hi.mp3",
        "template": "{actor} celebrates with {target}.",
        "self_template": "{actor} celebrates.",
        "requires_target": False,
    },
    "tease": {
        "aliases": {"tease", "sass"},
        "sound": "/sounds/reactions/chat.mp3",
        "template": "{actor} teases {target} playfully.",
        "requires_target": True,
    },
    "playful_smack": {
        "aliases": {"smack", "playful-smack"},
        "sound": "/sounds/reactions/tap.mp3",
        "template": "{actor} gives {target} a playful smack.",
        "requires_target": True,
    },
    "whisper": {
        "aliases": {"whisper"},
        "sound": "/sounds/reactions/chat.mp3",
        "template": "{actor} leans in to whisper to {target}.",
        "requires_target": True,
    },
    "listen": {
        "aliases": {"listen"},
        "sound": "/sounds/reactions/user.mp3",
        "template": "{actor} listens closely to {target}.",
        "self_template": "{actor} listens closely.",
        "requires_target": False,
    },
}
for _action_id, _definition in SOCIAL_ACTIONS.items():
    _definition["sound"] = _reaction_sound(_action_id)
SOCIAL_ACTION_ALIASES = {
    alias: action_id
    for action_id, definition in SOCIAL_ACTIONS.items()
    for alias in definition["aliases"]
}

AdminActionName: TypeAlias = Literal[
    "platform_overview",
    "role_create",
    "role_update_permissions",
    "role_delete",
    "user_set_role",
    "user_ban",
    "user_unban",
    "user_delete",
    "notifications_mark_read",
    "blindsoftware_admin_sync",
    "location_ambience_set",
]


class PianoRecordingEvent(TypedDict):
    t: int
    keyId: str
    midi: int
    on: bool
    instrument: str
    voiceMode: str
    attack: int
    decay: int
    release: int
    brightness: int
    emitRange: int


class PianoRecordingSession(TypedDict, total=False):
    ownerClientId: str
    elapsedMs: int
    paused: bool
    lastResumeMonotonic: float
    events: list[PianoRecordingEvent]
    autoStopTask: asyncio.Task[None]


class SignalingServer:
    """Coordinates websocket clients, signaling, and authoritative item actions."""

    def __init__(
        self,
        host: str,
        port: int,
        ssl_cert: str | None,
        ssl_key: str | None,
        auth_db_path: Path | None = None,
        auth_token_hash_secret: str | None = None,
        password_min_length: int = 8,
        password_max_length: int = 32,
        username_min_length: int = 2,
        username_max_length: int = 32,
        max_message_size: int = 2_000_000,
        state_file: Path | None = None,
        grid_size: int = 41,
        state_save_debounce_ms: int = 200,
        state_save_max_delay_ms: int = 1000,
        host_origin: str | None = None,
        base_path: str = "/",
        grid_name: str = "Chat Grid",
        welcome_message: str = (
            "Welcome to the Chat Grid, your immersive audio playground. "
            "Configure your audio, then Log in or register to join the grid."
        ),
    ):
        """Initialize runtime state, TLS context, and item service."""

        self.host = host
        self.port = port
        self.max_message_size = max_message_size
        self._ssl_context = self._build_ssl_context(ssl_cert, ssl_key)
        self.clients: dict[ServerConnection, ClientConnection] = {}
        resolved_auth_db_path = auth_db_path or Path.cwd() / "runtime" / "chatgrid.db"
        auth_secret = (
            auth_token_hash_secret.strip()
            if auth_token_hash_secret is not None
            else os.getenv("CHGRID_AUTH_SECRET", "").strip()
        )
        if not auth_secret:
            raise ValueError("CHGRID_AUTH_SECRET is required.")
        self.external_auth_secret = os.getenv(
            "CHGRID_EXTERNAL_AUTH_SECRET", auth_secret
        ).strip()
        self.auth_service = AuthService(
            db_path=resolved_auth_db_path,
            token_hash_secret=auth_secret,
            password_min_length=password_min_length,
            password_max_length=password_max_length,
            username_min_length=username_min_length,
            username_max_length=username_max_length,
        )
        self.item_service = ItemService(state_file=state_file, seed_builtin_items=True)
        self.notification_service = NotificationService()
        self.ntfy_publisher = NtfyPublisher(
            base_url=os.getenv("CHGRID_NTFY_BASE_URL", "").strip(),
            username=os.getenv("CHGRID_NTFY_USERNAME", "").strip(),
            password=os.getenv("CHGRID_NTFY_PASSWORD", "").strip(),
        )
        self.item_last_use_ms: dict[str, int] = {}
        self.active_piano_keys_by_client: dict[str, set[str]] = {}
        self.piano_recording_state_by_item: dict[str, PianoRecordingSession] = {}
        self.piano_playback_tasks_by_item: dict[str, asyncio.Task[None]] = {}
        self.grid_size = max(1, grid_size)
        self.movement_tick_ms = MOVEMENT_TICK_MS
        self.movement_max_steps_per_tick = MOVEMENT_MAX_STEPS_PER_TICK
        self.instance_id = str(uuid.uuid4())
        self.release_version, self.expected_client_revision = (
            self._resolve_client_version_metadata()
        )
        self.server_version = self._resolve_server_version(self.release_version)
        self.host_origin = (
            normalize_origin(host_origin, field_name="host origin")
            if host_origin
            else None
        )
        self.base_path = self._normalize_base_path(base_path)
        self.grid_name = str(grid_name).strip() or "Chat Grid"
        self.welcome_message = (
            str(welcome_message).strip()
            or "Welcome to the Chat Grid, your immersive audio playground. Configure your audio, then Log in or register to join the grid."
        )
        self.auth_session_cookie_name = self._session_cookie_name_for_base_path(
            self.base_path
        )
        self.websocket_path = self._base_path_join(WEBSOCKET_PATH)
        self.auth_session_cookie_set_path = self._base_path_join(
            AUTH_SESSION_COOKIE_SET_PATH
        )
        self.auth_session_cookie_clear_path = self._base_path_join(
            AUTH_SESSION_COOKIE_CLEAR_PATH
        )
        self.auth_session_cookie_check_path = self._base_path_join(
            AUTH_SESSION_COOKIE_CHECK_PATH
        )
        self.state_save_debounce_ms = max(1, int(state_save_debounce_ms))
        self.state_save_max_delay_ms = max(
            self.state_save_debounce_ms, int(state_save_max_delay_ms)
        )
        self._pending_state_save_handle: asyncio.TimerHandle | None = None
        self._pending_state_save_started_at: float | None = None
        self._last_position_persist_ms_by_user: dict[str, int] = {}
        self._live_presence_path = Path(__file__).resolve().parents[1] / "runtime" / "live_presence.json"
        self._last_live_presence_write_monotonic = 0.0
        self._live_presence_task: asyncio.Task[None] | None = None
        self._auth_hash_semaphore = asyncio.Semaphore(AUTH_HASH_MAX_CONCURRENCY)
        self._auth_failures_by_ip: dict[str, deque[float]] = {}
        self._auth_failures_by_identity: dict[str, deque[float]] = {}
        self._radio_metadata_task: asyncio.Task[None] | None = None
        self._clock_announce_task: asyncio.Task[None] | None = None
        self._blind_productions_billboard_task: asyncio.Task[None] | None = None
        self._world_cup_cafe_task: asyncio.Task[None] | None = None
        self._community_autofix_task: asyncio.Task[None] | None = None
        self._house_keeper_task: asyncio.Task[None] | None = None
        self._community_locations: dict[str, WorldLocation] = {}
        self._location_dimension_overrides: dict[str, tuple[int, int]] = {}
        self._clock_top_of_hour_markers: dict[str, str] = {}
        self._clock_alarm_markers: dict[str, str] = {}
        self._started_at_monotonic = time.monotonic()
        self._pending_reboot_task: asyncio.Task[None] | None = None
        self._studio_entry_invites: dict[str, float] = {}
        self._house_entry_invites: dict[tuple[str, str], float] = {}
        self._telepad_drift_task: asyncio.Task[None] | None = None
        # Active casts are room state, not one-shot chat events. Keep them long
        # enough to replay to a client that joins after the cast began.
        self._active_media_casts: dict[str, dict[str, MediaCastStatePacket]] = {}

    @staticmethod
    def _resolve_server_version(release_version: str) -> str:
        """Resolve server diagnostics version text."""

        env_override = os.getenv("CHGRID_SERVER_VERSION", "").strip()
        if env_override:
            return env_override

        return format_server_version(release_version)

    @staticmethod
    def _resolve_client_version_metadata() -> tuple[str, str]:
        """Resolve shared release version and expected client revision from version.js."""

        try:
            version_file = (
                Path(__file__).resolve().parents[2] / "client" / "public" / "version.js"
            )
            text = version_file.read_text(encoding="utf-8")
            return SignalingServer._client_version_metadata_from_web_version_text(text)
        except OSError:
            return "", ""

    def _current_expected_client_revision(self) -> str:
        """Read the published source revision without requiring a server restart.

        Client-only deployments update ``client/public/version.js`` while the
        signaling service remains online. Reading the revision at handshake
        time prevents the server from repeatedly redirecting a newer browser
        back toward the revision cached when this process started.
        """

        _release_version, revision = self._resolve_client_version_metadata()
        return revision or self.expected_client_revision

    @staticmethod
    def _client_version_metadata_from_web_version_text(text: str) -> tuple[str, str]:
        """Parse release/client revision metadata from one client version.js file."""

        release_match = re.search(r'CHGRID_RELEASE_VERSION\s*=\s*"([^"]+)"', text)
        revision_match = re.search(r'CHGRID_CLIENT_REVISION\s*=\s*"([^"]+)"', text)
        return (
            release_match.group(1).strip() if release_match else "",
            revision_match.group(1).strip() if revision_match else "",
        )

    @property
    def items(self) -> dict[str, WorldItem]:
        """Expose current item map owned by the item service."""

        return self.item_service.items

    @staticmethod
    def _location_token(value: object) -> str:
        """Return a stable location-id token from free text."""

        token = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold())
        return token.strip("_")

    def _location_exists(self, location_id: str) -> bool:
        """Return whether a built-in or community-generated location exists."""

        return (
            location_id in WORLD_LOCATION_BY_ID
            or location_id in self._community_locations
        )

    def _normalize_world_location_id(self, value: object) -> str:
        """Resolve a location id/name against built-in and generated locations."""

        candidate = str(value or "").strip().casefold()
        if candidate in self._community_locations:
            return candidate
        for location_id, location in self._community_locations.items():
            if candidate == location.name.casefold():
                return location_id
        return normalize_location_id(value)

    def _get_world_location(self, value: object) -> WorldLocation:
        """Resolve a built-in or generated world location."""

        location_id = self._normalize_world_location_id(value)
        location = self._community_locations.get(location_id) or get_location(location_id)
        dimensions = self._location_dimension_overrides.get(location_id)
        if dimensions:
            return replace(location, width=dimensions[0], height=dimensions[1])
        return location

    def _world_locations_for_client(self) -> list[dict[str, str | int]]:
        """Return only configured public travel destinations for client menus.

        Private house interiors, individual rooms, and generated place rooms are
        entered through their doors/portals and must not leak into the global
        Locations list.
        """

        return [
            entry.as_dict()
            for entry in WORLD_LOCATIONS
            if entry.kind not in {"house", "room"}
        ]

    def _generated_place_location_id(self, item: WorldItem) -> str:
        """Return the deterministic generated interior id for one place item."""

        base = self._location_token(
            item.params.get("placeName") or item.params.get("houseName") or item.title
        )
        if not base:
            base = item.type
        suffix = self._location_token(item.id)[:12] or "place"
        return f"community_{item.type}_{base}_{suffix}"[:64].rstrip("_")

    def _place_target_needs_generated_location(self, item: WorldItem) -> bool:
        """Return whether a place item lacks a specific usable interior target."""

        target = str(item.params.get("targetLocation") or "").strip().casefold()
        if not target:
            return True
        if target == DEFAULT_LOCATION_ID and item.locationId != DEFAULT_LOCATION_ID:
            return True
        return False

    def _community_location_for_place(
        self, item: WorldItem, location_id: str
    ) -> WorldLocation:
        """Build generated metadata for one user/community place interior."""

        place_name = str(
            item.params.get("placeName")
            or item.params.get("houseName")
            or item.title
            or item.type
        ).strip()
        if not place_name:
            place_name = item.type.replace("_", " ").title()
        description = str(item.params.get("description") or "").strip()
        if not description:
            description = f"Inside {place_name}."
        ambience_key_by_type = {
            "cabin": "living_room_warmth",
            "house": "front_entry",
            "room": "front_entry",
            "shack": "neighborhood_evening",
            "shed": "neighborhood_evening",
        }
        ambience_name_by_type = {
            "cabin": "Cabin warmth",
            "house": "House entry",
            "room": "Room tone",
            "shack": "Shack exterior",
            "shed": "Shed exterior",
        }
        return WorldLocation(
            id=location_id,
            name=place_name,
            kind=item.type,
            description=description,
            spawn_x=20,
            spawn_y=20,
            ambience_key=ambience_key_by_type.get(item.type, "front_entry"),
            ambience_name=ambience_name_by_type.get(item.type, "Room tone"),
            width=max(1, min(41, int(item.params.get("widthSquares", 41) or 41))),
            height=max(1, min(41, int(item.params.get("depthSquares", 41) or 41))),
        )

    def _return_door_id_for_location(self, location_id: str) -> str:
        """Return the deterministic system id for a generated-location exit door."""

        return f"community-exit-{location_id}"

    @staticmethod
    def _generated_companion_item_id(location_id: str, role: str) -> str:
        """Return a deterministic id for a generated place companion item."""

        token = re.sub(r"[^a-z0-9]+", "-", role.strip().casefold()).strip("-")
        return f"community-{token}-{location_id}"

    def _has_return_door(self, location_id: str, target_location_id: str) -> bool:
        """Return whether a generated location already has a usable way back out."""

        for item in self.items.values():
            if item.locationId != location_id or item.carrierId is not None:
                continue
            if item.type not in PLACE_TARGET_ITEM_TYPES and item.type != "service_link":
                continue
            target = str(item.params.get("targetLocation") or "").strip().casefold()
            if target == target_location_id:
                return True
        return False

    def _ensure_return_door_for_place(
        self, place_item: WorldItem, location_id: str, now_ms: int
    ) -> WorldItem | None:
        """Ensure generated interiors have a simple door back to their parent location."""

        parent_location_id = self._normalize_world_location_id(place_item.locationId)
        if self._has_return_door(location_id, parent_location_id):
            return None
        item_id = self._return_door_id_for_location(location_id)
        existing = self.items.get(item_id)
        door_def = get_item_definition("service_link")
        exit_name = str(
            place_item.params.get("placeName")
            or place_item.params.get("houseName")
            or place_item.title
            or "place"
        ).strip()
        title = f"Exit {exit_name}"
        params = {
            **door_def.default_params,
            "serviceKind": "door",
            "targetLocation": parent_location_id,
            "doorState": "unlocked",
            "description": f"Door back to {self._get_world_location(parent_location_id).name}.",
            "launchMessage": "Leaving this place.",
            "enabled": True,
            "useSound": "sounds/doors/door-open.mp3?v=20260714-real-door",
            "emitSound": "sounds/door_soft_loop.ogg",
            "emitRange": 7,
            "emitVolume": 28,
        }
        params = get_item_type_handler("service_link").validate_update(
            existing
            or WorldItem(
                id=item_id,
                type="service_link",
                title=title,
                locationId=location_id,
                x=20,
                y=21,
                createdBy="system",
                createdByName="community watcher",
                updatedBy="system",
                updatedByName="community watcher",
                createdAt=now_ms,
                updatedAt=now_ms,
                version=1,
                capabilities=list(door_def.capabilities),
                useSound=door_def.use_sound,
                emitSound=door_def.emit_sound,
                params=dict(door_def.default_params),
            ),
            params,
        )
        if existing is not None:
            existing.params = params
            existing.updatedAt = now_ms
            existing.updatedBy = "system"
            existing.updatedByName = "community watcher"
            existing.version += 1
            return existing
        door = WorldItem(
            id=item_id,
            type="service_link",
            title=title,
            locationId=location_id,
            x=20,
            y=21,
            createdBy="system",
            createdByName="community watcher",
            updatedBy="system",
            updatedByName="community watcher",
            createdAt=now_ms,
            updatedAt=now_ms,
            version=1,
            capabilities=list(door_def.capabilities),
            useSound=door_def.use_sound,
            emitSound=door_def.emit_sound,
            params=params,
            carrierId=None,
        )
        self.item_service.add_item(door)
        return door

    def _upsert_generated_service_link(
        self,
        *,
        item_id: str,
        title: str,
        location_id: str,
        x: int,
        y: int,
        target_location_id: str,
        description: str,
        launch_message: str,
        now_ms: int,
    ) -> WorldItem | None:
        """Create or refresh one generated doorway/link inside a community place."""

        existing = self.items.get(item_id)
        item_def = get_item_definition("service_link")
        params = {
            **item_def.default_params,
            "serviceKind": "door",
            "targetLocation": target_location_id,
            "doorState": "unlocked",
            "description": description,
            "launchMessage": launch_message,
            "enabled": True,
            "useSound": "sounds/doors/door-open.mp3?v=20260714-real-door",
            "emitSound": "sounds/door_soft_loop.ogg",
            "emitRange": 7,
            "emitVolume": 28,
        }
        basis = existing or WorldItem(
            id=item_id,
            type="service_link",
            title=title,
            locationId=location_id,
            x=x,
            y=y,
            createdBy="system",
            createdByName="community watcher",
            updatedBy="system",
            updatedByName="community watcher",
            createdAt=now_ms,
            updatedAt=now_ms,
            version=1,
            capabilities=list(item_def.capabilities),
            useSound=item_def.use_sound,
            emitSound=item_def.emit_sound,
            params=dict(item_def.default_params),
        )
        normalized = get_item_type_handler("service_link").validate_update(basis, params)
        if existing is not None:
            changed = (
                existing.title != title
                or existing.locationId != location_id
                or existing.x != x
                or existing.y != y
                or existing.params != normalized
            )
            if not changed:
                return None
            existing.title = title
            existing.locationId = location_id
            existing.x = x
            existing.y = y
            existing.params = normalized
            existing.updatedAt = now_ms
            existing.updatedBy = "system"
            existing.updatedByName = "community watcher"
            existing.version += 1
            return existing
        item = WorldItem(
            id=item_id,
            type="service_link",
            title=title,
            locationId=location_id,
            x=x,
            y=y,
            createdBy="system",
            createdByName="community watcher",
            updatedBy="system",
            updatedByName="community watcher",
            createdAt=now_ms,
            updatedAt=now_ms,
            version=1,
            capabilities=list(item_def.capabilities),
            useSound=item_def.use_sound,
            emitSound=item_def.emit_sound,
            params=normalized,
            carrierId=None,
        )
        self.item_service.add_item(item)
        return item

    def _upsert_generated_house_object(
        self,
        *,
        item_id: str,
        title: str,
        location_id: str,
        x: int,
        y: int,
        params: dict[str, object],
        now_ms: int,
    ) -> WorldItem | None:
        """Create or refresh one generated fixture/device in a community place."""

        existing = self.items.get(item_id)
        item_def = get_item_definition("house_object")
        merged_params = {**item_def.default_params, **params}
        basis = existing or WorldItem(
            id=item_id,
            type="house_object",
            title=title,
            locationId=location_id,
            x=x,
            y=y,
            createdBy="system",
            createdByName="community watcher",
            updatedBy="system",
            updatedByName="community watcher",
            createdAt=now_ms,
            updatedAt=now_ms,
            version=1,
            capabilities=list(item_def.capabilities),
            useSound=item_def.use_sound,
            emitSound=item_def.emit_sound,
            params=dict(item_def.default_params),
        )
        normalized = get_item_type_handler("house_object").validate_update(
            basis, merged_params
        )
        if existing is not None:
            changed = (
                existing.title != title
                or existing.locationId != location_id
                or existing.x != x
                or existing.y != y
                or existing.params != normalized
            )
            if not changed:
                return None
            existing.title = title
            existing.locationId = location_id
            existing.x = x
            existing.y = y
            existing.params = normalized
            existing.updatedAt = now_ms
            existing.updatedBy = "system"
            existing.updatedByName = "community watcher"
            existing.version += 1
            return existing
        item = WorldItem(
            id=item_id,
            type="house_object",
            title=title,
            locationId=location_id,
            x=x,
            y=y,
            createdBy="system",
            createdByName="community watcher",
            updatedBy="system",
            updatedByName="community watcher",
            createdAt=now_ms,
            updatedAt=now_ms,
            version=1,
            capabilities=list(item_def.capabilities),
            useSound=item_def.use_sound,
            emitSound=item_def.emit_sound,
            params=normalized,
            carrierId=None,
        )
        self.item_service.add_item(item)
        return item

    def _upsert_generated_room_marker(
        self,
        *,
        item_id: str,
        title: str,
        location_id: str,
        x: int,
        y: int,
        target_location_id: str,
        params: dict[str, object],
        now_ms: int,
    ) -> WorldItem | None:
        """Create or refresh one generated room/space marker in a community place."""

        existing = self.items.get(item_id)
        item_def = get_item_definition("room")
        merged_params = {
            **item_def.default_params,
            **params,
            "targetLocation": target_location_id,
        }
        basis = existing or WorldItem(
            id=item_id,
            type="room",
            title=title,
            locationId=location_id,
            x=x,
            y=y,
            createdBy="system",
            createdByName="community watcher",
            updatedBy="system",
            updatedByName="community watcher",
            createdAt=now_ms,
            updatedAt=now_ms,
            version=1,
            capabilities=list(item_def.capabilities),
            useSound=item_def.use_sound,
            emitSound=item_def.emit_sound,
            params=dict(item_def.default_params),
        )
        normalized = get_item_type_handler("room").validate_update(basis, merged_params)
        if existing is not None:
            changed = (
                existing.title != title
                or existing.locationId != location_id
                or existing.x != x
                or existing.y != y
                or existing.params != normalized
            )
            if not changed:
                return None
            existing.title = title
            existing.locationId = location_id
            existing.x = x
            existing.y = y
            existing.params = normalized
            existing.updatedAt = now_ms
            existing.updatedBy = "system"
            existing.updatedByName = "community watcher"
            existing.version += 1
            return existing
        item = WorldItem(
            id=item_id,
            type="room",
            title=title,
            locationId=location_id,
            x=x,
            y=y,
            createdBy="system",
            createdByName="community watcher",
            updatedBy="system",
            updatedByName="community watcher",
            createdAt=now_ms,
            updatedAt=now_ms,
            version=1,
            capabilities=list(item_def.capabilities),
            useSound=item_def.use_sound,
            emitSound=item_def.emit_sound,
            params=normalized,
            carrierId=None,
        )
        self.item_service.add_item(item)
        return item

    def _ensure_generated_place_companions(
        self, place_item: WorldItem, location_id: str, now_ms: int
    ) -> list[WorldItem]:
        """Add the practical doors, spaces, windows, and devices a new place needs."""

        changed: list[WorldItem] = []
        parent_location_id = self._normalize_world_location_id(place_item.locationId)
        place_name = str(
            place_item.params.get("placeName")
            or place_item.params.get("houseName")
            or place_item.title
            or place_item.type
        ).strip()
        if not place_name:
            place_name = place_item.type.replace("_", " ").title()
        if place_item.type == "house":
            outside = self._upsert_generated_service_link(
                item_id=self._generated_companion_item_id(location_id, "outside-door"),
                title="Outside entrance",
                location_id=location_id,
                x=19,
                y=21,
                target_location_id=parent_location_id,
                description=(
                    "An outside doorway back to "
                    f"{self._get_world_location(parent_location_id).name}."
                ),
                launch_message="Stepping outside.",
                now_ms=now_ms,
            )
            if outside is not None:
                changed.append(outside)
            balcony_target_id = f"{location_id}_balcony"[:64].rstrip("_")
            balcony = self._upsert_generated_room_marker(
                item_id=self._generated_companion_item_id(location_id, "balcony-room"),
                title="Balcony",
                location_id=location_id,
                x=22,
                y=20,
                target_location_id=balcony_target_id,
                params={
                    "placeName": f"{place_name} Balcony",
                    "ownerName": place_item.params.get("ownerName", ""),
                    "roomLayout": "custom",
                    "doorState": "unlocked",
                    "description": "An outside balcony connected to the house.",
                    "zoneNotes": "balcony door, rail, outside air, view back toward the house",
                    "welcomeMessage": "You step out onto the balcony.",
                },
                now_ms=now_ms,
            )
            if balcony is not None:
                changed.append(balcony)
            built_in_rooms = (
                ("living-room", "Living room", "raywonder_house_living_room", 30, 26),
                ("studio-room", "Studio", "raywonder_house_studio", 34, 30),
                ("kitchen-room", "Kitchen", "raywonder_house_kitchen", 26, 24),
                ("bedroom-room", "Bedroom", "raywonder_house_bedroom", 28, 26),
                ("relaxation-room", "Relaxation room", "raywonder_house_relaxation_room", 30, 26),
            )
            for role, room_title, target_id, width, height in built_in_rooms:
                marker_id = self._generated_companion_item_id(location_id, role)
                if marker_id in self.items:
                    continue
                marker = self._upsert_generated_room_marker(
                    item_id=marker_id,
                    title=room_title,
                    location_id=location_id,
                    x=20,
                    y=20,
                    target_location_id=target_id,
                    params={
                        "placeName": f"Raywonder {room_title}",
                        "ownerName": place_item.params.get("ownerName", ""),
                        "roomLayout": (
                            room_title.casefold().replace(" ", "_")
                            if room_title.casefold().replace(" ", "_")
                            in {"living_room"}
                            else "custom"
                        ),
                        "widthSquares": width,
                        "depthSquares": height,
                        "description": f"The editable {room_title.casefold()} room.",
                        "zoneNotes": "room entrance, furniture, clear walking space",
                    },
                    now_ms=now_ms,
                )
                if marker is not None:
                    changed.append(marker)
        fixtures: tuple[tuple[str, str, int, int, dict[str, object]], ...] = (
            (
                "front-window",
                "Front window",
                18,
                20,
                {
                    "objectKind": "window",
                    "placement": "wall",
                    "material": "glass",
                    "fragility": "delicate",
                    "windowState": "closed",
                    "description": (
                        "A window facing outside so outdoor ambience can carry in "
                        "when opened."
                    ),
                    "replacementHint": "A matching window pane can be repaired or replaced.",
                    "repairCost": 20,
                    "purchaseCost": 45,
                },
            ),
            (
                "lamp-device",
                "Entry lamp",
                20,
                19,
                {
                    "objectKind": "lamp",
                    "placement": "fixture",
                    "material": "mixed",
                    "fragility": "normal",
                    "description": "A practical light fixture for the entry space.",
                    "replacementHint": "A similar fixture belongs by the doorway.",
                    "repairCost": 10,
                    "purchaseCost": 24,
                },
            ),
            (
                "keys-device",
                "House keys",
                21,
                20,
                {
                    "objectKind": "keys",
                    "placement": "fixture",
                    "material": "metal",
                    "fragility": "sturdy",
                    "keyId": f"{location_id}-key"[:80],
                    "keyFor": place_name,
                    "description": "A practical key set for the generated place.",
                    "replacementHint": "If it goes missing, check the entrance first.",
                    "repairCost": 0,
                    "purchaseCost": 12,
                },
            ),
        )
        for role, title, x, y, params in fixtures:
            fixture = self._upsert_generated_house_object(
                item_id=self._generated_companion_item_id(location_id, role),
                title=title,
                location_id=location_id,
                x=x,
                y=y,
                params=params,
                now_ms=now_ms,
            )
            if fixture is not None:
                changed.append(fixture)
        return changed

    async def _repair_community_locations(self, *, broadcast: bool) -> list[str]:
        """Autofix user/community place targets and generated interior exits."""

        changed_items: list[WorldItem] = []
        notes: list[str] = []
        now_ms = self.item_service.now_ms()
        for item in sorted(self.items.values(), key=lambda entry: (entry.type, entry.id)):
            if item.type not in PLACE_TARGET_ITEM_TYPES:
                continue
            raw_target = str(item.params.get("targetLocation") or "").strip().casefold()
            target_location_id = (
                self._generated_place_location_id(item)
                if self._place_target_needs_generated_location(item)
                else self._location_token(raw_target)
            )
            if not target_location_id:
                continue
            if item.params.get("targetLocation") != target_location_id:
                item.params = {**item.params, "targetLocation": target_location_id}
                item.updatedAt = now_ms
                item.updatedBy = "system"
                item.updatedByName = "community watcher"
                item.version += 1
                changed_items.append(item)
                notes.append(f"{item.title} target")
            if target_location_id not in WORLD_LOCATION_BY_ID:
                location = self._community_location_for_place(item, target_location_id)
                existing_location = self._community_locations.get(target_location_id)
                if existing_location != location:
                    self._community_locations[target_location_id] = location
                    notes.append(f"{location.name} location")
            if item.type == "room":
                location = self._get_world_location(target_location_id)
                dimensions = (
                    max(1, min(self.grid_size, int(item.params.get("widthSquares", location.width) or location.width))),
                    max(1, min(self.grid_size, int(item.params.get("depthSquares", location.height) or location.height))),
                )
                if self._location_dimension_overrides.get(target_location_id) != dimensions:
                    self._location_dimension_overrides[target_location_id] = dimensions
                    notes.append(f"{location.name} dimensions")
            if target_location_id in self._community_locations:
                return_door = self._ensure_return_door_for_place(
                    item, target_location_id, now_ms
                )
                if return_door is not None:
                    changed_items.append(return_door)
                    notes.append(f"{return_door.title} return door")
                companion_items = self._ensure_generated_place_companions(
                    item, target_location_id, now_ms
                )
                for companion in companion_items:
                    changed_items.append(companion)
                    notes.append(f"{companion.title} companion")
        if changed_items:
            self._request_state_save()
            if broadcast:
                for item in changed_items:
                    await self._broadcast_item(item)
        return notes

    async def _run_community_autofix_loop(self) -> None:
        """Let free community watchers periodically repair broken place interiors."""

        while True:
            try:
                await self._repair_community_locations(broadcast=True)
            except Exception as exc:
                LOGGER.warning("community location autofix failed: %s", exc)
            await asyncio.sleep(COMMUNITY_AUTOFIX_INTERVAL_S)

    def _nickname_key(self, nickname: str) -> str:
        """Normalize nickname for case-insensitive comparisons."""

        return nickname.casefold()

    def _persist_client_position(
        self, client: ClientConnection, *, force: bool = False
    ) -> None:
        """Persist one authenticated client's last known position with debounce."""

        if not client.user_id:
            return
        self._write_live_presence(force=force)
        now_ms = self.item_service.now_ms()
        if not force:
            last_saved_ms = self._last_position_persist_ms_by_user.get(
                client.user_id, 0
            )
            if now_ms - last_saved_ms < POSITION_PERSIST_DEBOUNCE_MS:
                return
        self.auth_service.set_last_position(
            client.user_id, client.x, client.y, client.location_id
        )
        self._last_position_persist_ms_by_user[client.user_id] = now_ms

    def _write_live_presence(self, *, force: bool = False) -> None:
        """Publish a private, local registry of currently connected user presence."""

        now = time.monotonic()
        if not force and now - self._last_live_presence_write_monotonic < 0.2:
            return
        entries = []
        for client in self.clients.values():
            if not client.authenticated or not client.user_id:
                continue
            entries.append(
                {
                    "userId": client.user_id,
                    "username": client.username or "",
                    "nickname": client.nickname,
                    "locationId": client.location_id,
                    "x": client.x,
                    "y": client.y,
                    "posture": client.posture if client.seated_item_id else "standing",
                    "seatedItemId": client.seated_item_id,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }
            )
        entries.sort(key=lambda item: (item["username"].casefold(), item["userId"]))
        self._live_presence_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._live_presence_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps({"updatedAt": datetime.now(timezone.utc).isoformat(), "users": entries}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self._live_presence_path)
        os.chmod(self._live_presence_path, 0o600)
        self._last_live_presence_write_monotonic = now

    async def _run_live_presence_loop(self) -> None:
        """Keep the private connected-user registry fresh while the server runs."""

        while True:
            self._write_live_presence(force=True)
            await asyncio.sleep(5)

    def _clients_in_location(
        self, location_id: str, *, exclude: ServerConnection | None = None
    ) -> list[ServerConnection]:
        """Return active websocket recipients currently in one world location."""

        return [
            websocket
            for websocket, client in self.clients.items()
            if websocket is not exclude and client.location_id == location_id
        ]

    async def _broadcast_location(
        self,
        location_id: str,
        packet: object,
        *,
        exclude: ServerConnection | None = None,
    ) -> None:
        """Broadcast one packet only to clients inside the selected location."""

        recipients = self._clients_in_location(location_id, exclude=exclude)
        if not recipients:
            return
        await asyncio.gather(
            *(self._send(websocket, packet) for websocket in recipients)
        )

    def _auth_policy(self) -> dict[str, int]:
        """Return server-auth policy limits advertised to clients."""

        return {
            "usernameMinLength": self.auth_service.username_min_length,
            "usernameMaxLength": self.auth_service.username_max_length,
            "passwordMinLength": self.auth_service.password_min_length,
            "passwordMaxLength": self.auth_service.password_max_length,
        }

    @staticmethod
    def _normalize_base_path(value: str) -> str:
        """Normalize one instance base path to leading/trailing slash form."""

        text = str(value).strip()
        if not text or text == "/":
            return "/"
        return f"/{text.strip('/')}/"

    def _base_path_join(self, suffix: str) -> str:
        """Join one instance-relative route suffix to the configured base path."""

        token = suffix.lstrip("/")
        if self.base_path == "/":
            return f"/{token}"
        return f"{self.base_path}{token}"

    @staticmethod
    def _session_cookie_name_for_base_path(base_path: str) -> str:
        """Return one deterministic session cookie name for the configured instance path."""

        if base_path == "/":
            return AUTH_SESSION_COOKIE_NAME
        suffix = re.sub(r"[^a-z0-9]+", "_", base_path.strip("/").casefold()).strip("_")
        if not suffix:
            return AUTH_SESSION_COOKIE_NAME
        return f"chgrid_session_{suffix}"

    def _session_cookie_secure(self, request: HttpRequest | None = None) -> bool:
        """Return True when session cookies should be marked Secure."""

        if self._ssl_context is not None:
            return True
        if request is None:
            return False
        forwarded = (
            str(request.headers.get("X-Forwarded-Proto", ""))
            .split(",", 1)[0]
            .strip()
            .lower()
        )
        return forwarded == "https"

    def _session_cookie_header(
        self, token: str, *, request: HttpRequest | None = None
    ) -> str:
        """Build Set-Cookie header value for a valid session token."""

        secure = "; Secure" if self._session_cookie_secure(request) else ""
        return (
            f"{self.auth_session_cookie_name}={token}; Path={self.base_path}; HttpOnly; SameSite=Lax; "
            f"Max-Age={AUTH_SESSION_COOKIE_MAX_AGE_SECONDS}{secure}"
        )

    def _clear_session_cookie_header(
        self, *, request: HttpRequest | None = None
    ) -> str:
        """Build Set-Cookie header value that expires the session cookie."""

        secure = "; Secure" if self._session_cookie_secure(request) else ""
        return f"{self.auth_session_cookie_name}=; Path={self.base_path}; HttpOnly; SameSite=Lax; Max-Age=0{secure}"

    def _origin_allowed(self, request: HttpRequest) -> bool:
        """Return whether one auth helper HTTP request comes from the configured app origin."""

        if not self.host_origin:
            return False
        raw_origin = str(request.headers.get("Origin", "")).strip()
        if raw_origin:
            try:
                origin = normalize_origin(raw_origin)
            except ValueError:
                return False
            return origin == self.host_origin

        fetch_site = str(request.headers.get("Sec-Fetch-Site", "")).strip().lower()
        if fetch_site == "same-origin":
            return True

        raw_referer = str(request.headers.get("Referer", "")).strip()
        if not raw_referer:
            return False
        try:
            parts = urlsplit(raw_referer)
            referer_origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
            return (
                normalize_origin(referer_origin, field_name="referer")
                == self.host_origin
            )
        except ValueError:
            return False

    @staticmethod
    def _cookie_value(cookie_header: str, name: str) -> str:
        """Extract one cookie value by name from a Cookie header."""

        for segment in cookie_header.split(";"):
            key, separator, raw_value = segment.strip().partition("=")
            if separator and key == name:
                return raw_value.strip()
        return ""

    async def _process_http_request(
        self, _connection: object, request: HttpRequest
    ) -> HttpResponse | None:
        """Handle lightweight same-origin auth cookie set/clear HTTP endpoints."""

        path = request.path.split("?", 1)[0]
        auth_paths = {
            self.auth_session_cookie_set_path,
            self.auth_session_cookie_clear_path,
            self.auth_session_cookie_check_path,
        }
        if path == self.websocket_path:
            return None

        if path.startswith(VOICE_URL_PREFIX):
            return self._serve_voice_file(path, request)

        if path not in auth_paths:
            headers = Headers()
            headers["Content-Type"] = "text/plain; charset=utf-8"
            headers["Cache-Control"] = "no-store"
            return HttpResponse(404, "Not Found", headers, b"not found")

        headers = Headers()
        headers["Content-Type"] = "text/plain; charset=utf-8"
        headers["Cache-Control"] = "no-store"
        client_header = str(
            request.headers.get(AUTH_SESSION_COOKIE_CLIENT_HEADER, "")
        ).strip()
        if client_header != "1":
            return HttpResponse(400, "Bad Request", headers, b"missing client header")
        if not self._origin_allowed(request):
            return HttpResponse(403, "Forbidden", headers, b"origin not allowed")

        if path == self.auth_session_cookie_check_path:
            cookie_header = str(request.headers.get("Cookie", "")).strip()
            token = self._cookie_value(cookie_header, self.auth_session_cookie_name)
            if not token:
                return HttpResponse(401, "Unauthorized", headers, b"missing session")
            try:
                self.auth_service.resume(token)
            except AuthError:
                return HttpResponse(401, "Unauthorized", headers, b"invalid session")
            return HttpResponse(204, "No Content", headers, b"")

        if path == self.auth_session_cookie_clear_path:
            headers["Set-Cookie"] = self._clear_session_cookie_header(request=request)
            return HttpResponse(200, "OK", headers, b"cleared")

        authorization = str(request.headers.get("Authorization", "")).strip()
        if not authorization.lower().startswith("bearer "):
            return HttpResponse(400, "Bad Request", headers, b"missing bearer token")
        token = authorization[7:].strip()
        if not token:
            return HttpResponse(400, "Bad Request", headers, b"missing bearer token")
        try:
            session = self.auth_service.resume(token)
        except AuthError:
            return HttpResponse(401, "Unauthorized", headers, b"invalid session")
        headers["Set-Cookie"] = self._session_cookie_header(
            session.token, request=request
        )
        return HttpResponse(200, "OK", headers, b"ok")

    def _session_token_from_websocket_cookie(self, websocket: object) -> str:
        """Read session token from websocket handshake Cookie header."""

        request = getattr(websocket, "request", None)
        headers = getattr(request, "headers", None)
        if headers is None:
            return ""
        cookie_header = str(headers.get("Cookie", "")).strip()
        if not cookie_header:
            return ""
        return self._cookie_value(cookie_header, self.auth_session_cookie_name)

    def _serve_voice_file(
        self, path: str, _request: HttpRequest
    ) -> HttpResponse:
        """Serve one generated voice MP3 from the runtime voice directory."""

        filename = path[len(VOICE_URL_PREFIX) :]
        resolved = voice_file_path(filename)
        if resolved is None:
            headers = Headers()
            headers["Content-Type"] = "text/plain; charset=utf-8"
            headers["Cache-Control"] = "no-store"
            return HttpResponse(404, "Not Found", headers, b"not found")
        try:
            audio_bytes = resolved.read_bytes()
        except OSError:
            headers = Headers()
            headers["Content-Type"] = "text/plain; charset=utf-8"
            headers["Cache-Control"] = "no-store"
            return HttpResponse(500, "Internal Server Error", headers, b"read error")
        headers = Headers()
        headers["Content-Type"] = "audio/mpeg"
        headers["Cache-Control"] = "public, max-age=3600"
        return HttpResponse(200, "OK", headers, audio_bytes)

    def _build_admin_menu_actions_for_client(
        self, client: ClientConnection | None
    ) -> list[dict[str, str]]:
        """Build server-authored admin menu actions allowed for one client."""

        if client is None:
            return []
        client_permissions = client.permissions or set()
        return [
            {"id": action["id"], "label": action["label"], "tooltip": action["tooltip"]}
            for action in ADMIN_MENU_ACTION_DEFINITIONS
            if action["permission"] in client_permissions
        ]

    @staticmethod
    def _sorted_permissions(values: set[str] | tuple[str, ...] | None) -> list[str]:
        """Return deterministic sorted permission list."""

        if not values:
            return []
        return sorted(str(value) for value in values if str(value).strip())

    def _client_has_permission(self, client: ClientConnection, key: str) -> bool:
        """Return whether one authenticated client currently has a permission key."""

        if not client.authenticated or not client.user_id:
            return False
        if client.permissions is None:
            client.permissions = self.auth_service.get_user_permissions(client.user_id)
        return key in client.permissions

    def _refresh_client_permissions(self, client: ClientConnection) -> list[str]:
        """Refresh one client's role/permissions from auth storage and return permissions list."""

        if not client.user_id:
            client.permissions = set()
            return []
        user = self.auth_service.get_user_by_id(client.user_id)
        if user is None:
            client.permissions = set()
            return []
        client.role = user.role
        client.permissions = set(user.permissions)
        return self._sorted_permissions(client.permissions)

    async def _send_auth_permissions(self, client: ClientConnection) -> None:
        """Push one authenticated client's current role + permission set."""

        permissions = self._refresh_client_permissions(client)
        await self._send(
            client.websocket,
            AuthPermissionsPacket(
                type="auth_permissions",
                role=client.role,
                permissions=permissions,
                adminMenuActions=self._build_admin_menu_actions_for_client(client),
            ),
        )

    async def _sync_permissions_for_user_ids(self, user_ids: list[str]) -> None:
        """Refresh and push permissions for active websocket clients matching user ids."""

        wanted = {str(user_id) for user_id in user_ids}
        if not wanted:
            return
        for active in self.clients.values():
            if not active.user_id or active.user_id not in wanted:
                continue
            await self._send_auth_permissions(active)

    def _notification_summary(
        self, record: NotificationRecord, *, user_id: str
    ) -> AdminNotificationSummary:
        """Convert one notification record to its outbound summary."""

        return AdminNotificationSummary(
            id=record.id,
            createdAt=record.created_at_ms,
            kind=record.kind,
            title=record.title,
            message=record.message,
            targetUserId=record.target_user_id,
            actorUserId=record.actor_user_id,
            read=record.is_read_for(user_id),
        )

    async def _send_admin_notifications(
        self, client: ClientConnection, *, scope: Literal["own", "admin"]
    ) -> None:
        """Send visible notifications for the current user/admin."""

        if not client.user_id:
            await self._send_admin_action_result(
                client,
                ok=False,
                action="notifications_mark_read",
                message="Sign in to read notifications.",
            )
            return
        include_admin = scope == "admin"
        if include_admin and not self._client_has_permission(
            client, "notifications.read.any"
        ):
            await self._send_admin_action_result(
                client,
                ok=False,
                action="notifications_mark_read",
                message="Not authorized.",
            )
            return
        records = self.notification_service.list_for_user(
            user_id=client.user_id, include_admin=include_admin
        )
        await self._send(
            client.websocket,
            AdminNotificationsListResultPacket(
                type="admin_notifications_list",
                scope=scope,
                unreadCount=self.notification_service.unread_count(
                    user_id=client.user_id, include_admin=include_admin
                ),
                notifications=[
                    self._notification_summary(record, user_id=client.user_id)
                    for record in records
                ],
            ),
        )

    async def _add_notification(
        self,
        *,
        kind: str,
        title: str,
        message: str,
        target_user_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> NotificationRecord:
        """Create one notification and push a lightweight alert to active targets."""

        record = self.notification_service.add(
            now_ms=self.item_service.now_ms(),
            kind=kind,
            title=title,
            message=message,
            target_user_id=target_user_id,
            actor_user_id=actor_user_id,
        )
        if target_user_id is not None:
            preferences = self.auth_service.get_ntfy_preferences(target_user_id)
            if preferences["enabled"] and self.ntfy_publisher.configured:
                await asyncio.to_thread(
                    self.ntfy_publisher.publish,
                    topic=str(preferences["topic"]),
                    title=record.title,
                    message=record.message,
                    click=f"{self.host_origin}/chatgrid/",
                )
        for active in self.clients.values():
            if not active.user_id:
                continue
            if target_user_id is not None and active.user_id != target_user_id:
                continue
            if target_user_id is None and not self._client_has_permission(
                active, "notifications.read.any"
            ):
                continue
            await self._send(
                active.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"Notification: {record.title}.",
                    system=True,
                ),
            )
        return record

    def _flush_state_save(self) -> None:
        """Immediately flush pending state persistence and clear debounce state."""

        if self._pending_state_save_handle is not None:
            self._pending_state_save_handle.cancel()
            self._pending_state_save_handle = None
        self._pending_state_save_started_at = None
        self.item_service.save_state()

    def _request_state_save(self) -> None:
        """Debounce/coalesce item-state persistence to reduce write churn."""

        loop = asyncio.get_running_loop()
        now = loop.time()
        if self._pending_state_save_started_at is None:
            self._pending_state_save_started_at = now
        elapsed_ms = int((now - self._pending_state_save_started_at) * 1000)
        if elapsed_ms >= self.state_save_max_delay_ms:
            self._flush_state_save()
            return
        if self._pending_state_save_handle is not None:
            self._pending_state_save_handle.cancel()
        remaining_ms = max(0, self.state_save_max_delay_ms - elapsed_ms)
        delay_ms = min(self.state_save_debounce_ms, remaining_ms)
        self._pending_state_save_handle = loop.call_later(
            delay_ms / 1000, self._flush_state_save
        )

    def _is_nickname_taken(
        self, nickname: str, exclude_client_id: str | None = None
    ) -> bool:
        """Check whether nickname is already used by another active client."""

        wanted = self._nickname_key(nickname)
        for other in self.clients.values():
            if exclude_client_id is not None and other.id == exclude_client_id:
                continue
            if self._nickname_key(other.nickname) == wanted:
                return True
        return False

    @staticmethod
    def _item_type_label(item: WorldItem) -> str:
        """Return user-facing item type wording for chat/status strings."""

        return "radio" if item.type == "radio_station" else item.type

    @staticmethod
    def _client_ip(client: ClientConnection) -> str:
        """Extract best-effort remote IP string for audit logs and auth throttling."""

        address = getattr(client.websocket, "remote_address", None)
        if isinstance(address, tuple) and address:
            peer_raw = address[0]
        elif isinstance(address, str):
            peer_raw = address
        else:
            peer_raw = None
        peer_ip = SignalingServer._normalized_ip(peer_raw)
        if not peer_ip:
            return "unknown"

        # Trust X-Forwarded-For only from a loopback proxy hop (e.g., local Apache/nginx).
        try:
            peer_addr = ipaddress.ip_address(peer_ip)
        except ValueError:
            return peer_ip
        if not peer_addr.is_loopback:
            return peer_ip

        request = getattr(client.websocket, "request", None)
        headers = getattr(request, "headers", None)
        if headers is None:
            return peer_ip
        forwarded = str(headers.get("X-Forwarded-For", "")).strip()
        if not forwarded:
            return peer_ip
        # In common reverse-proxy chains, the trusted proxy appends the immediate
        # client IP to the end of X-Forwarded-For. Read right-to-left so a
        # client-supplied left-side value can't spoof throttling/audit identity.
        for candidate in reversed(forwarded.split(",")):
            parsed = SignalingServer._normalized_ip(candidate)
            if parsed:
                return parsed
        return peer_ip

    @staticmethod
    def _normalized_ip(value: object) -> str | None:
        """Return normalized IP text or None when input is invalid."""

        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        if "%" in text:
            text = text.split("%", 1)[0]
        try:
            return str(ipaddress.ip_address(text))
        except ValueError:
            return None

    @staticmethod
    def _prune_failure_window(bucket: deque[float], now_s: float) -> None:
        """Drop expired auth-failure timestamps outside the active limit window."""

        threshold = now_s - AUTH_RATE_LIMIT_WINDOW_S
        while bucket and bucket[0] < threshold:
            bucket.popleft()

    def _auth_identity_key(self, client: ClientConnection, packet: ClientPacket) -> str:
        """Build username/IP scoped key used for auth failure throttling."""

        if isinstance(packet, (AuthLoginPacket, AuthRegisterPacket)):
            username = packet.username.strip().lower()
        elif isinstance(packet, AuthResumePacket):
            username = "resume"
        elif isinstance(packet, AuthExternalPacket):
            username = "external"
        else:
            username = "unknown"
        return f"{self._client_ip(client)}::{username}"

    def _is_auth_rate_limited(
        self, client: ClientConnection, packet: ClientPacket
    ) -> bool:
        """Return True when recent auth failures exceed IP or identity thresholds."""

        now_s = time.monotonic()
        ip_key = self._client_ip(client)
        identity_key = self._auth_identity_key(client, packet)

        ip_bucket = self._auth_failures_by_ip.setdefault(ip_key, deque())
        identity_bucket = self._auth_failures_by_identity.setdefault(
            identity_key, deque()
        )
        self._prune_failure_window(ip_bucket, now_s)
        self._prune_failure_window(identity_bucket, now_s)

        return (
            len(ip_bucket) >= AUTH_RATE_LIMIT_PER_IP
            or len(identity_bucket) >= AUTH_RATE_LIMIT_PER_IDENTITY
        )

    def _record_auth_failure(
        self, client: ClientConnection, packet: ClientPacket
    ) -> None:
        """Record a failed auth attempt for IP and identity-scoped throttling."""

        now_s = time.monotonic()
        ip_key = self._client_ip(client)
        identity_key = self._auth_identity_key(client, packet)
        self._auth_failures_by_ip.setdefault(ip_key, deque()).append(now_s)
        self._auth_failures_by_identity.setdefault(identity_key, deque()).append(now_s)

    def _clear_auth_failures(
        self, client: ClientConnection, packet: ClientPacket
    ) -> None:
        """Clear identity-scoped auth failures after a successful authentication."""

        now_s = time.monotonic()
        identity_key = self._auth_identity_key(client, packet)
        bucket = self._auth_failures_by_identity.get(identity_key)
        if not bucket:
            return
        bucket.clear()
        self._prune_failure_window(bucket, now_s)

    async def _sleep_auth_failure_jitter(self) -> None:
        """Apply small randomized delay to reduce high-resolution auth timing probes."""

        await asyncio.sleep(
            SYSTEM_RANDOM.uniform(
                AUTH_FAILURE_JITTER_MIN_MS, AUTH_FAILURE_JITTER_MAX_MS
            )
        )

    async def _run_auth_hash_task(self, func, /, *args, **kwargs):
        """Run auth service call in a worker thread behind bounded hash concurrency."""

        async with self._auth_hash_semaphore:
            return await asyncio.to_thread(func, *args, **kwargs)

    @staticmethod
    def _is_door_transition_item(item: WorldItem) -> bool:
        """Return whether successful use should sound like a physical door."""

        if item.type in {"cabin", "house", "room", "shack", "shed"}:
            return True
        if item.type != "service_link":
            return False
        kind = str(item.params.get("serviceKind", "")).strip().lower()
        if kind in {"portal", "game", "app", "service", "site", "station", "tool"}:
            return False
        return bool(str(item.params.get("targetLocation", "")).strip())

    @classmethod
    def _resolve_item_use_sound(cls, item: WorldItem) -> str | None:
        """Resolve one-shot use sound, preferring per-item param override."""

        if cls._is_door_transition_item(item):
            return "sounds/doors/door-open.mp3?v=20260714-real-door"
        param_sound = item.params.get("useSound")
        if isinstance(param_sound, str):
            token = param_sound.strip()
            if token:
                return token
            return None
        if isinstance(item.useSound, str) and item.useSound.strip():
            return item.useSound.strip()
        return None

    @staticmethod
    def _should_broadcast_game_launch(item: WorldItem) -> bool:
        """Return whether this item use should invite same-square players into a game."""

        if item.type != "service_link":
            return False
        kind = str(item.params.get("serviceKind", "")).strip().lower()
        if kind != "game":
            return False
        if str(item.params.get("targetLocation", "")).strip():
            return False
        if str(item.params.get("doorState", "unlocked")).strip().lower() == "locked":
            return False
        return bool(str(item.params.get("url", "")).strip())

    @staticmethod
    def _can_enter_service_link_target(item: WorldItem) -> bool:
        """Return whether a service link's target location may be entered now."""

        if item.type != "service_link":
            return False
        kind = str(item.params.get("serviceKind", "")).strip().lower()
        target_location = str(item.params.get("targetLocation", "")).strip()
        if not target_location and kind != "portal":
            return False
        if str(item.params.get("doorState", "unlocked")).strip().lower() == "locked":
            return False
        if kind == "portal" and effective_portal_state(item) == "closed":
            return False
        return item.params.get("enabled") is not False

    @staticmethod
    def _required_key_id_for(item: WorldItem) -> str:
        """Return the normalized key id required by a locked item."""

        door_state = str(item.params.get("doorState", "unlocked")).strip().lower()
        if door_state != "locked":
            return ""
        return str(item.params.get("requiredKeyId", "") or "").strip()

    def _find_unlock_key_for(
        self, client: ClientConnection, item: WorldItem
    ) -> WorldItem | None:
        """Find a matching carried or door-square key for one locked item."""

        required_key_id = self._required_key_id_for(item)
        if not required_key_id:
            return None
        candidates = [
            *self.item_service.carried_items_for_client(client.id),
            *[
                candidate
                for candidate in self.items.values()
                if candidate.carrierId is None
                and candidate.locationId == item.locationId
                and candidate.x == item.x
                and candidate.y == item.y
            ],
        ]
        for candidate in candidates:
            key_id = str(candidate.params.get("keyId", "") or "").strip()
            if key_id == required_key_id:
                return candidate
        return None

    def _linked_house_alarm(self, door: WorldItem) -> WorldItem | None:
        """Return the alarm panel that authoritatively guards one exterior door."""

        alarm_id = str(door.params.get("accessAlarmItemId") or "").strip()
        alarm = self.items.get(alarm_id) if alarm_id else None
        return alarm if alarm is not None and alarm.type == "house_alarm" else None

    def _has_house_entry_access(self, client: ClientConnection, door: WorldItem) -> bool:
        """Return whether identity or a recent successful keypad entry permits travel."""

        alarm = self._linked_house_alarm(door)
        if alarm is None:
            return True
        if evaluate_house_alarm_access(
            alarm, client.nickname, username=client.username or ""
        ) == "authorized":
            return True
        key = (client.id, door.id)
        expires_at = self._house_entry_invites.get(key)
        if expires_at is None:
            return False
        if expires_at < time.monotonic():
            self._house_entry_invites.pop(key, None)
            return False
        self._house_entry_invites.pop(key, None)
        return True

    async def _deny_guarded_house_entry(
        self, client: ClientConnection, door: WorldItem
    ) -> None:
        """Keep a visitor outside, sound a spatial knock, and identify the keypad."""

        alarm = self._linked_house_alarm(door)
        alarm_name = alarm.title if alarm is not None else "alarm keypad"
        await self._broadcast_guarded_door_knock(client, door)
        if alarm is not None:
            await self._notify_house_entry_event(
                alarm,
                client,
                (
                    f"{client.nickname} knocks at the front door. "
                    f"Use /allow {client.nickname} to let them in or "
                    f"/deny {client.nickname} to keep them outside."
                ),
            )
        await self._send_item_result(
            client,
            False,
            "use",
            f"The door is secured. Use {alarm_name} on this square to request or enter access.",
            door.id,
        )

    def _doors_for_house_alarm(self, alarm: WorldItem) -> list[WorldItem]:
        """Return exterior doors authoritatively linked to one alarm panel."""

        return [
            candidate
            for candidate in self.items.values()
            if candidate.type == "service_link"
            and str(candidate.params.get("accessAlarmItemId") or "").strip() == alarm.id
        ]

    def _protected_scopes_for_house_alarm(self, alarm: WorldItem) -> set[str]:
        """Return house-wide interior scopes protected by one alarm panel."""

        scopes: set[str] = set()
        for door in self._doors_for_house_alarm(alarm):
            target_location = str(door.params.get("targetLocation") or "").strip()
            if target_location:
                scopes.add(self._house_access_scope_for_location(target_location))
        return scopes

    @staticmethod
    def _is_house_alarm_controller(alarm: WorldItem, client: ClientConnection) -> bool:
        """Return whether the signed-in account may approve or deny alarm requests."""

        username = (client.username or "").strip().casefold()
        if not username:
            return False
        allowed = {
            value.strip().casefold()
            for value in str(alarm.params.get("authorizedUsernames") or "").split(",")
            if value.strip()
        }
        enrolled = str(alarm.params.get("enrolledUsername") or "").strip().casefold()
        return username == enrolled or username in allowed

    def _controls_alarm_from_current_house(
        self, alarm: WorldItem, client: ClientConnection
    ) -> bool:
        """Return whether a client can answer this alarm from their current room."""

        if not self._is_house_alarm_controller(alarm, client):
            return False
        protected_scopes = self._protected_scopes_for_house_alarm(alarm)
        if not protected_scopes:
            return False
        return self._house_access_scope_for_location(client.location_id) in protected_scopes

    def _guarded_entry_matches_for_name(
        self, client: ClientConnection, requested_name: str
    ) -> list[tuple[WorldItem, WorldItem, ClientConnection]]:
        """Find guarded exterior-door visitors a resident may answer by name."""

        matches: list[tuple[WorldItem, WorldItem, ClientConnection]] = []
        if not requested_name.strip():
            return matches
        for alarm in self.items.values():
            if alarm.type != "house_alarm":
                continue
            if not self._controls_alarm_from_current_house(alarm, client):
                continue
            for door in self._doors_for_house_alarm(alarm):
                waiting = self._find_user_by_name_in_location(
                    requested_name, door.locationId
                )
                if waiting is not None:
                    matches.append((alarm, door, waiting))
        return matches

    async def _notify_house_entry_event(
        self, alarm: WorldItem, client: ClientConnection, message: str
    ) -> None:
        """Alert occupants and configured owner identities about one entry event."""

        protected_scopes = self._protected_scopes_for_house_alarm(alarm)
        for occupant in self.clients.values():
            if (
                self._house_access_scope_for_location(occupant.location_id)
                not in protected_scopes
            ):
                continue
            await self._send(
                occupant.websocket,
                BroadcastChatMessagePacket(type="chat_message", message=message, system=True),
            )
        usernames = {
            value.strip()
            for value in str(alarm.params.get("authorizedUsernames") or "").split(",")
            if value.strip()
        }
        enrolled = str(alarm.params.get("enrolledUsername") or "").strip()
        if enrolled:
            usernames.add(enrolled)
        for username in usernames:
            target_user_id = self.auth_service.get_user_id_by_username(username)
            if target_user_id:
                await self._add_notification(
                    kind="house.entry",
                    title=str(alarm.params.get("houseName") or "House entry"),
                    message=message,
                    target_user_id=target_user_id,
                    actor_user_id=client.user_id,
                )

    async def _complete_house_alarm_entry(
        self,
        *,
        client: ClientConnection,
        alarm: WorldItem,
        access_result: str,
    ) -> None:
        """Open the linked door and move an authenticated entrant after policy delay."""

        delay = 10.0 if access_result == "guest" else 0.0
        if delay:
            await self._send_item_result(
                client, True, "use", "Guest access verified. The door will open in ten seconds.", alarm.id
            )
            await self._notify_house_entry_event(
                alarm, client, f"{client.nickname} verified guest access and will enter in ten seconds."
            )
            await asyncio.sleep(delay)
        if client.websocket not in self.clients:
            return
        doors = self._doors_for_house_alarm(alarm)
        door = next(
            (
                candidate
                for candidate in doors
                if candidate.locationId == client.location_id
                and candidate.x == client.x
                and candidate.y == client.y
            ),
            doors[0] if doors else None,
        )
        if door is None:
            return
        target_location = str(door.params.get("targetLocation") or "").strip()
        if not target_location:
            return
        await self._notify_house_entry_event(
            alarm, client, f"{client.nickname} is entering {alarm.params.get('houseName') or 'the house'}."
        )
        await self._broadcast_location(
            door.locationId,
            ItemUseSoundPacket(
                type="item_use_sound",
                itemId=door.id,
                sound="sounds/doors/door-open.mp3?v=20260714-real-door",
                x=door.x,
                y=door.y,
                range=14,
            ),
        )
        await self._change_client_location(client, target_location)

    @staticmethod
    def _is_drifting_telepad(item: WorldItem) -> bool:
        """Return whether an item is a world telepad eligible for gentle drift."""

        if item.type != "service_link":
            return False
        kind = str(item.params.get("serviceKind") or "").strip().lower()
        sound = str(item.params.get("emitSound") or "").strip().lower()
        return kind in {"portal", "teleport", "telepad"} and "teleport_pad" in sound

    async def _run_telepad_drift_loop(self) -> None:
        """Move telepads one safe square occasionally to keep their positions playful."""

        while True:
            await asyncio.sleep(SYSTEM_RANDOM.uniform(45.0, 110.0))
            pads = [item for item in self.items.values() if self._is_drifting_telepad(item)]
            if not pads:
                continue
            pad = SYSTEM_RANDOM.choice(pads)
            candidates = [
                (pad.x + dx, pad.y + dy)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                if 0 <= pad.x + dx < self.grid_size and 0 <= pad.y + dy < self.grid_size
            ]
            occupied = {
                (item.x, item.y)
                for item in self.items.values()
                if item.locationId == pad.locationId and item.id != pad.id
                and item.params.get("blocksMovement") is True
            }
            candidates = [position for position in candidates if position not in occupied]
            if not candidates:
                continue
            pad.x, pad.y = SYSTEM_RANDOM.choice(candidates)
            pad.updatedAt = self.item_service.now_ms()
            self._request_state_save()
            await self._broadcast_item(pad)

    def _inside_door_for_guarded_entry(self, door: WorldItem) -> WorldItem | None:
        """Find the interior return door corresponding to one guarded exterior door."""

        target_location = str(door.params.get("targetLocation") or "").strip()
        if not target_location:
            return None
        for candidate in self.items.values():
            if candidate.type != "service_link" or candidate.locationId != target_location:
                continue
            candidate_target = str(candidate.params.get("targetLocation") or "").strip()
            if candidate_target == door.locationId:
                return candidate
        return None

    async def _broadcast_guarded_door_knock(
        self, client: ClientConnection, door: WorldItem
    ) -> None:
        """Play one real spatial knock outside and just inside a guarded home."""

        sound = "sounds/doors/door-knock.mp3?v=20260716"
        await self._broadcast_location(
            door.locationId,
            ItemUseSoundPacket(
                type="item_use_sound",
                itemId=door.id,
                sound=sound,
                x=door.x,
                y=door.y,
                range=14,
            ),
        )
        inside_door = self._inside_door_for_guarded_entry(door)
        if inside_door is None:
            return
        await self._broadcast_location(
            inside_door.locationId,
            ItemUseSoundPacket(
                type="item_use_sound",
                itemId=inside_door.id,
                sound=sound,
                x=inside_door.x,
                y=inside_door.y,
                range=18,
            ),
        )

    @staticmethod
    def _is_raywonder_studio_entry_door(item: WorldItem) -> bool:
        """Return whether one item is the entry-hall door into the studio."""

        if item.type != "service_link":
            return False
        kind = str(item.params.get("serviceKind", "")).strip().lower()
        target_location = str(item.params.get("targetLocation", "")).strip().casefold()
        return kind == "door" and target_location == RAYWONDER_STUDIO_LOCATION_ID

    def _has_valid_studio_invite(self, client: ClientConnection) -> bool:
        """Return whether the client currently has a live studio-entry invite."""

        expires_at = self._studio_entry_invites.get(client.id)
        if expires_at is None:
            return False
        if expires_at < time.monotonic():
            self._studio_entry_invites.pop(client.id, None)
            return False
        return True

    async def _knock_on_raywonder_studio_door(
        self, client: ClientConnection, item: WorldItem
    ) -> None:
        """Notify both sides when someone uses the private studio door."""

        await self._send_item_result(
            client,
            True,
            "use",
            "You knock on the studio door.",
            item.id,
        )
        await self._broadcast_location(
            RAYWONDER_ENTRY_LOCATION_ID,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=f"{client.nickname} knocks on the studio door.",
                system=True,
            ),
            exclude=client.websocket,
        )
        await self._broadcast_location(
            RAYWONDER_STUDIO_LOCATION_ID,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=(
                    f"{client.nickname} knocks on the studio door. "
                    f"Use /allow {client.nickname} to let them in."
                ),
                system=True,
            ),
        )

    @staticmethod
    def _portal_location_pool(item: WorldItem, current_location_id: str) -> list[str]:
        """Return normalized destination ids a random portal may choose from."""

        raw_pool = str(item.params.get("portalLocationPool", "")).strip()
        if raw_pool:
            candidates = [
                normalize_location_id(token)
                for token in raw_pool.replace(";", ",").split(",")
                if token.strip()
            ]
        else:
            candidates = [
                location.id
                for location in WORLD_LOCATIONS
                if location.id in RANDOM_PORTAL_LOCATION_IDS
            ]
        seen: set[str] = set()
        pool: list[str] = []
        for location_id in candidates:
            if location_id == current_location_id or location_id in seen:
                continue
            if location_id not in {location.id for location in WORLD_LOCATIONS}:
                continue
            seen.add(location_id)
            pool.append(location_id)
        return pool

    def _resolve_service_link_target_location(
        self, item: WorldItem, current_location_id: str
    ) -> str:
        """Resolve static or random service-link travel destination."""

        if not self._can_enter_service_link_target(item):
            return ""
        kind = str(item.params.get("serviceKind", "")).strip().lower()
        target_location = str(item.params.get("targetLocation", "")).strip()
        if kind != "portal":
            return self._normalize_world_location_id(target_location) if target_location else ""
        destination_mode = (
            str(item.params.get("portalDestinationMode", "random")).strip().lower()
            or "random"
        )
        if destination_mode == "static":
            return self._normalize_world_location_id(target_location) if target_location else ""
        pool = self._portal_location_pool(item, current_location_id)
        if pool:
            return SYSTEM_RANDOM.choice(pool)
        return self._normalize_world_location_id(target_location) if target_location else ""

    def _resolve_place_target_location(self, item: WorldItem) -> str:
        """Resolve simple place-item travel destination, if configured."""

        if item.type not in PLACE_TARGET_ITEM_TYPES:
            return ""
        if str(item.params.get("doorState", "unlocked")).strip().lower() == "locked":
            return ""
        target_location = str(item.params.get("targetLocation", "")).strip()
        return self._normalize_world_location_id(target_location) if target_location else ""

    @staticmethod
    def _format_display_sound_name(value: object) -> str:
        """Return display-friendly sound token (file name only) for item property menus."""

        raw = str(value or "").strip()
        if not raw:
            return "none"
        if raw.lower() == "none":
            return "none"
        without_query = raw.split("?", 1)[0].split("#", 1)[0]
        segments = [segment for segment in without_query.split("/") if segment]
        return segments[-1] if segments else raw

    @staticmethod
    def _format_display_timestamp_ms(value: int) -> str:
        """Format epoch milliseconds to compact UTC text used in item property menus."""

        dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")

    def _build_item_display_values(self, item: WorldItem) -> dict[str, str]:
        """Build server-authoritative item property display values for readonly/system fields."""

        carrier_label = "none"
        if item.carrierId:
            carrier = self._get_client_by_id(item.carrierId)
            carrier_label = carrier.nickname if carrier is not None else item.carrierId
        verification_display = ""
        if item.type == "service_link":
            status = str(
                item.params.get("verificationStatus") or "author_verified"
            ).strip()
            verification_display = status.replace("_", " ")
        return {
            "type": item.type,
            "x": str(item.x),
            "y": str(item.y),
            "carrierId": carrier_label,
            "version": str(item.version),
            "createdBy": item.createdByName or item.createdBy,
            "updatedBy": item.updatedByName or item.updatedBy,
            "createdAt": self._format_display_timestamp_ms(item.createdAt),
            "updatedAt": self._format_display_timestamp_ms(item.updatedAt),
            "capabilities": ", ".join(item.capabilities)
            if item.capabilities
            else "none",
            "useSound": self._format_display_sound_name(
                item.params.get("useSound", item.useSound)
            ),
            "emitSound": self._format_display_sound_name(
                item.params.get("emitSound", item.emitSound)
            ),
            "verificationStatus": verification_display,
        }

    def _outbound_item(self, item: WorldItem) -> WorldItem:
        """Return one outbound item snapshot enriched with server-owned display values."""

        return item.model_copy(
            update={"display": self._build_item_display_values(item)}
        )

    @staticmethod
    def _item_updated_actor(client: ClientConnection) -> tuple[str, str]:
        """Resolve `(actor_id, actor_name)` used in item update tracking fields."""

        actor_id = client.user_id or client.id
        actor_name = client.username or client.nickname or actor_id
        return actor_id, actor_name

    @staticmethod
    def _owns_item(client: ClientConnection, item: WorldItem) -> bool:
        """Return whether the authenticated client is the creator/owner of an item."""

        if not client.user_id:
            return False
        return item.createdBy == client.user_id

    @staticmethod
    def _is_generic_furniture_title(title: str, furniture_kind: object) -> bool:
        """Return whether a furniture title is only the generic kind label."""

        normalized_title = title.strip().casefold().replace("_", " ")
        normalized_kind = str(furniture_kind or "").strip().casefold().replace("_", " ")
        return bool(normalized_title and normalized_title == normalized_kind)

    @staticmethod
    def _surface_dependents_for(
        item_id: str, items: dict[str, WorldItem]
    ) -> list[WorldItem]:
        """Return items that store this item as their current supporting surface."""

        return [
            item
            for item in items.values()
            if str(item.params.get("surfaceId", "") or "").strip() == item_id
        ]

    def _client_creates_trusted_items(self, client: ClientConnection) -> bool:
        """Return whether new items from this client should be verified immediately."""

        return self._client_has_permission(
            client, "item.edit.any"
        ) or self._client_has_permission(client, "server.manage_settings")

    def _apply_item_creation_verification(
        self, client: ClientConnection, item: WorldItem
    ) -> None:
        """Apply creation-time verification policy to newly added link items."""

        if item.type != "service_link":
            return
        if self._client_creates_trusted_items(client):
            item.params = {
                **item.params,
                "verificationStatus": "author_verified",
                "verificationAvailableAt": 0,
            }
            return
        item.params = {
            **item.params,
            "verificationStatus": "unverified",
            "verificationAvailableAt": item.createdAt + ITEM_AUTO_VERIFY_DELAY_MS,
        }

    def _item_verification_block_message(self, item: WorldItem, now_ms: int) -> str:
        """Return a use-block message, or an empty string when the item is usable."""

        if item.type != "service_link":
            return ""
        status = str(
            item.params.get("verificationStatus") or "author_verified"
        ).strip().lower()
        if status in {"community_verified", "author_verified", "staff_verified"}:
            return ""
        ready_at = item.params.get("verificationAvailableAt")
        try:
            ready_at_ms = int(ready_at or 0)
        except (TypeError, ValueError):
            ready_at_ms = 0
        if ready_at_ms <= 0:
            ready_at_ms = int(item.createdAt) + ITEM_AUTO_VERIFY_DELAY_MS
        if now_ms >= ready_at_ms:
            return ""
        remaining_seconds = max(1, int((ready_at_ms - now_ms + 999) / 1000))
        if remaining_seconds >= 60:
            remaining_minutes = max(1, int((remaining_seconds + 59) / 60))
            wait_text = f"{remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
        else:
            wait_text = f"{remaining_seconds} seconds"
        return (
            f"{item.title} is waiting for verification. "
            f"It can be used in about {wait_text}."
        )

    async def _ensure_item_verified_for_use(
        self,
        client: ClientConnection,
        item: WorldItem,
        action: Literal["use", "secondary_use"],
    ) -> bool:
        """Enforce item verification before use and auto-verify matured links."""

        now_ms = self.item_service.now_ms()
        block_message = self._item_verification_block_message(item, now_ms)
        if block_message:
            await self._send_item_result(client, False, action, block_message, item.id)
            return False
        if item.type == "service_link":
            status = str(
                item.params.get("verificationStatus") or "author_verified"
            ).strip().lower()
            if status == "unverified":
                item.params = {
                    **item.params,
                    "verificationStatus": "community_verified",
                    "verificationAvailableAt": int(
                        item.params.get("verificationAvailableAt") or 0
                    ),
                }
                item.updatedAt = now_ms
                item.updatedBy = "system"
                item.updatedByName = "system"
                item.version += 1
                self._request_state_save()
                await self._broadcast_item(item)
        return True

    @staticmethod
    def _is_raywonder_house_location(location_id: str) -> bool:
        """Return whether a location belongs to the Raywonder house interior."""

        return location_id.startswith(RAYWONDER_HOUSE_LOCATION_PREFIX)

    @classmethod
    def _carry_scope_for_location(cls, location_id: str) -> str:
        """Return the broader place where carried items may remain in hand."""

        if cls._is_raywonder_house_location(location_id):
            return "raywonder_house"
        return location_id

    @staticmethod
    def _house_access_scope_for_location(location_id: str) -> str:
        """Return the house-wide access scope for a room location."""

        if "_house_" in location_id:
            return f"{location_id.split('_house_', 1)[0]}_house"
        return location_id

    @staticmethod
    def _is_remote_synced_house_radio_location(location_id: str) -> bool:
        """Return whether a house room radio should follow the universal remote."""

        return (
            location_id.startswith(RAYWONDER_HOUSE_LOCATION_PREFIX)
            and location_id != "raywonder_house_relaxation_room"
        )

    @staticmethod
    def _is_radio_remote(item: WorldItem) -> bool:
        """Return whether a house object should act as a universal radio remote."""

        if item.type != "house_object":
            return False
        object_kind = str(item.params.get("objectKind", "")).strip().lower()
        if object_kind != "remote":
            return False
        title = item.title.strip().lower()
        description = str(item.params.get("description", "")).strip().lower()
        return "radio" in title or "radio" in description

    @staticmethod
    def _is_tv_remote(item: WorldItem) -> bool:
        """Return whether a house object should act as a universal TV remote."""

        if item.type != "house_object":
            return False
        object_kind = str(item.params.get("objectKind", "")).strip().lower()
        if object_kind != "remote":
            return False
        title = item.title.strip().lower()
        description = str(item.params.get("description", "")).strip().lower()
        haystack = f"{title} {description}"
        return any(
            token in haystack
            for token in ("tv", "television", "movie", "movies", "channel", "channels")
        )

    @staticmethod
    def _remote_controls_linked_radios(remote: WorldItem) -> bool:
        """Return whether a remote should act on the linked house radio group."""

        value = remote.params.get("remoteControlLinkedRadios", True)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() not in {"off", "false", "0", "no"}
        return True

    @staticmethod
    def _remote_controls_linked_tvs(remote: WorldItem) -> bool:
        """Return whether a remote should act on the linked house TV group."""

        value = remote.params.get("remoteControlLinkedTvs", True)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() not in {"off", "false", "0", "no"}
        return True

    @staticmethod
    def _is_house_keeper(item: WorldItem) -> bool:
        """Return whether an item is a small in-world house repair helper."""

        return item.type == "house_keeper"

    @staticmethod
    def _house_keeper_targets(item: WorldItem) -> set[str]:
        """Return normalized target kinds this house keeper may inspect or fix."""

        raw_targets = str(item.params.get("targetKinds") or "radio, object")
        targets = {
            token.strip().casefold()
            for token in raw_targets.replace(";", ",").split(",")
            if token.strip()
        }
        if not targets:
            return {"radio", "object"}
        return targets

    @staticmethod
    def _house_keeper_authorized(item: WorldItem, nickname: str) -> bool:
        """Return whether a user may ask this keeper to act."""

        names = str(item.params.get("authorizedNames") or "").split(",")
        allowed = {name.strip().casefold() for name in names if name.strip()}
        if not allowed:
            return True
        return nickname.strip().casefold() in allowed

    @staticmethod
    def _house_keeper_background_enabled(item: WorldItem) -> bool:
        """Return whether a keeper may run quiet scheduled checks."""

        value = item.params.get("backgroundChecksEnabled", True)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().casefold() not in {"0", "false", "no", "off", "disabled"}
        return True

    @staticmethod
    def _house_keeper_check_interval_ms(item: WorldItem) -> int:
        """Return the bounded interval between scheduled keeper checks."""

        try:
            hours = int(item.params.get("checkIntervalHours", 6))
        except (TypeError, ValueError):
            hours = 6
        hours = max(1, min(168, hours))
        return hours * 60 * 60 * 1000

    def _house_keeper_system_client(self, keeper: WorldItem) -> ClientConnection:
        """Build a minimal actor identity for server-owned keeper work."""

        keeper_name = str(keeper.params.get("keeperName") or keeper.title).strip()
        return ClientConnection(
            websocket=cast(ServerConnection, object()),
            id=f"house-keeper:{keeper.id}",
            authenticated=True,
            user_id="system:house_keeper",
            username=keeper_name or "House keeper",
            nickname=keeper_name or "House keeper",
            location_id=keeper.locationId,
            x=keeper.x,
            y=keeper.y,
            world_ready=True,
        )

    async def _move_house_keeper_one_step(self, keeper: WorldItem) -> bool:
        """Move a keeper one in-bounds tile in its current room when possible."""

        if keeper.carrierId is not None:
            return False
        candidates = [
            (keeper.x + dx, keeper.y + dy)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if self._is_in_bounds(keeper.x + dx, keeper.y + dy, keeper.locationId)
        ]
        if not candidates:
            return False
        SYSTEM_RANDOM.shuffle(candidates)
        next_x, next_y = candidates[0]
        if next_x == keeper.x and next_y == keeper.y:
            return False
        keeper.x = next_x
        keeper.y = next_y
        now_ms = self.item_service.now_ms()
        keeper.updatedAt = now_ms
        keeper.updatedBy = "system:house_keeper"
        keeper.updatedByName = str(
            keeper.params.get("keeperName") or keeper.title or "House keeper"
        ).strip()
        keeper.version += 1
        await self._broadcast_item(keeper)
        self._request_state_save()
        return True

    @staticmethod
    def _radio_presets(item: WorldItem) -> list[dict[str, str]]:
        """Return valid station preset dictionaries from one radio item."""

        raw_presets = item.params.get("stationPresets")
        if not isinstance(raw_presets, list):
            return []
        presets: list[dict[str, str]] = []
        for entry in raw_presets:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title") or entry.get("name") or "").strip()
            stream_url = str(entry.get("streamUrl") or entry.get("url") or "").strip()
            if not title or not stream_url:
                continue
            preset = {"title": title, "streamUrl": stream_url}
            switch_sound = str(
                entry.get("switchSound") or entry.get("stationSwitchSound") or ""
            ).strip()
            if switch_sound:
                preset["switchSound"] = switch_sound
            presets.append(preset)
        return presets

    @staticmethod
    def _radio_station_index(item: WorldItem, preset_count: int) -> int:
        """Return the normalized station index for one radio."""

        try:
            station_index = int(item.params.get("stationIndex", 0))
        except (TypeError, ValueError):
            station_index = 0
        if preset_count <= 0:
            return 0
        return station_index % preset_count

    @staticmethod
    def _is_tv_media_item(item: WorldItem) -> bool:
        """Return whether a house object should play as a TV media source."""

        return (
            item.type == "house_object"
            and str(item.params.get("objectKind", "")).strip().lower() == "tv"
        )

    @classmethod
    def _is_stream_media_item(cls, item: WorldItem) -> bool:
        """Return whether an item uses the shared spatial media runtime."""

        return item.type == "radio_station" or cls._is_tv_media_item(item)

    @staticmethod
    def _radio_playback_identity(params: dict) -> tuple[bool, str, str, int]:
        """Return the params that define a radio playback timeline."""

        try:
            station_index = int(params.get("stationIndex", 0))
        except (TypeError, ValueError):
            station_index = 0
        return (
            params.get("enabled") is not False,
            str(params.get("streamUrl") or "").strip(),
            str(params.get("playbackUrl") or "").strip(),
            station_index,
        )

    def _sync_radio_play_started_at(
        self, item: WorldItem, previous_params: dict, now_ms: int
    ) -> None:
        """Keep one authoritative radio playhead marker for reconnect resume."""

        if not self._is_stream_media_item(item):
            return
        enabled, stream_url, playback_url, station_index = self._radio_playback_identity(
            item.params
        )
        if not enabled or not (stream_url or playback_url):
            item.params["playStartedAt"] = 0
            return
        previous_identity = self._radio_playback_identity(previous_params)
        try:
            current_marker = int(item.params.get("playStartedAt", 0) or 0)
        except (TypeError, ValueError):
            current_marker = 0
        current_identity = (enabled, stream_url, playback_url, station_index)
        if current_marker <= 0 or previous_identity != current_identity:
            item.params["playStartedAt"] = now_ms

    def _nearest_house_radio_for_remote(
        self, client: ClientConnection, remote: WorldItem
    ) -> WorldItem | None:
        """Pick the nearest usable house radio/speaker for this carried remote."""

        client_scope = self._carry_scope_for_location(client.location_id)
        remote_scope = self._carry_scope_for_location(remote.locationId)
        candidates = [
            item
            for item in self.items.values()
            if item.type == "radio_station"
            and self._carry_scope_for_location(item.locationId)
            in {client_scope, remote_scope}
            and item.carrierId is None
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                item.locationId != client.location_id,
                abs(item.x - client.x) + abs(item.y - client.y)
                if item.locationId == client.location_id
                else 10_000,
                str(item.params.get("speakerRole") or "primary").strip().lower()
                != "primary",
                item.title.lower(),
                item.id,
            )
        )
        return candidates[0]

    def _nearest_house_tv_for_remote(
        self, client: ClientConnection, remote: WorldItem
    ) -> WorldItem | None:
        """Pick the nearest usable house TV for this carried remote."""

        client_scope = self._carry_scope_for_location(client.location_id)
        remote_scope = self._carry_scope_for_location(remote.locationId)
        candidates = [
            item
            for item in self.items.values()
            if self._is_tv_media_item(item)
            and self._carry_scope_for_location(item.locationId)
            in {client_scope, remote_scope}
            and item.carrierId is None
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                item.locationId != client.location_id,
                abs(item.x - client.x) + abs(item.y - client.y)
                if item.locationId == client.location_id
                else 10_000,
                item.title.lower(),
                item.id,
            )
        )
        return candidates[0]

    async def _apply_radio_station_index(
        self,
        item: WorldItem,
        station_index: int,
        client: ClientConnection,
        *,
        enabled: bool | None = None,
        play_started_at: int | None = None,
    ) -> None:
        """Tune one radio through its normal validator and broadcast the result."""

        presets = self._radio_presets(item)
        if not presets:
            return
        next_index = station_index % len(presets)
        station = presets[next_index]
        next_params = {
            **item.params,
            "stationIndex": next_index,
            "streamUrl": station["streamUrl"],
            "playbackUrl": "",
            "stationName": station["title"],
            "stationSwitchSound": station.get("switchSound", ""),
            "nowPlaying": "",
        }
        if enabled is not None:
            next_params["enabled"] = enabled
        handler = get_item_type_handler(item.type)
        previous_params = dict(item.params)
        item.params = handler.validate_update(item, next_params)
        await self._resolve_radio_playback_before_broadcast(item)
        now_ms = self.item_service.now_ms()
        self._sync_radio_play_started_at(
            item, previous_params, play_started_at or now_ms
        )
        item.updatedAt = now_ms
        actor_id, actor_name = self._item_updated_actor(client)
        item.updatedBy = actor_id
        item.updatedByName = actor_name
        item.version += 1
        self._request_state_save()
        await self._broadcast_item(item)

    async def _apply_radio_station_state(
        self,
        item: WorldItem,
        station_index: int,
        station: dict[str, str],
        client: ClientConnection,
        *,
        enabled: bool | None = None,
        play_started_at: int | None = None,
    ) -> None:
        """Tune one radio/speaker to an already-selected station state."""

        presets = self._radio_presets(item)
        if presets:
            await self._apply_radio_station_index(
                item,
                station_index,
                client,
                enabled=enabled,
                play_started_at=play_started_at,
            )
            return
        next_params = {
            **item.params,
            "stationIndex": station_index,
            "streamUrl": station["streamUrl"],
            "playbackUrl": "",
            "stationName": station["title"],
            "stationSwitchSound": station.get("switchSound", ""),
            "nowPlaying": "",
        }
        if enabled is not None:
            next_params["enabled"] = enabled
        handler = get_item_type_handler(item.type)
        previous_params = dict(item.params)
        item.params = handler.validate_update(item, next_params)
        item.params["stationName"] = station["title"][:160]
        item.params["stationSwitchSound"] = station.get("switchSound", "")
        item.params["nowPlaying"] = ""
        await self._resolve_radio_playback_before_broadcast(item)
        now_ms = self.item_service.now_ms()
        self._sync_radio_play_started_at(
            item, previous_params, play_started_at or now_ms
        )
        item.updatedAt = now_ms
        actor_id, actor_name = self._item_updated_actor(client)
        item.updatedBy = actor_id
        item.updatedByName = actor_name
        item.version += 1
        self._request_state_save()
        await self._broadcast_item(item)

    async def _apply_radio_media_volume(
        self, item: WorldItem, media_volume: int, client: ClientConnection
    ) -> None:
        """Apply one radio media volume update through normal validation."""

        next_params = {**item.params, "mediaVolume": max(0, min(1000, media_volume))}
        handler = get_item_type_handler(item.type)
        item.params = handler.validate_update(item, next_params)
        item.updatedAt = self.item_service.now_ms()
        actor_id, actor_name = self._item_updated_actor(client)
        item.updatedBy = actor_id
        item.updatedByName = actor_name
        item.version += 1
        self._request_state_save()
        await self._broadcast_item(item)

    def _radio_group_targets_for_remote(
        self, target: WorldItem, *, require_presets: bool
    ) -> list[WorldItem]:
        """Return connected house radios that should respond with the target."""

        linked_group = str(target.params.get("linkedMediaGroup") or "").strip()
        targets: list[WorldItem] = []
        for item in self.items.values():
            if (
                item.type != "radio_station"
                or not self._is_remote_synced_house_radio_location(item.locationId)
            ):
                continue
            if require_presets and not self._radio_presets(item):
                continue
            if linked_group:
                if str(item.params.get("linkedMediaGroup") or "").strip() != linked_group:
                    continue
            elif item.locationId != target.locationId:
                continue
            targets.append(item)
        targets.sort(key=lambda item: (item.locationId, item.title.lower(), item.id))
        return targets

    def _tv_group_targets_for_remote(
        self, target: WorldItem, *, require_presets: bool
    ) -> list[WorldItem]:
        """Return connected house TVs that should respond with the target."""

        linked_group = str(target.params.get("linkedMediaGroup") or "").strip()
        targets: list[WorldItem] = []
        for item in self.items.values():
            if not self._is_tv_media_item(item) or not self._is_raywonder_house_location(
                item.locationId
            ):
                continue
            if require_presets and not self._radio_presets(item):
                continue
            if linked_group:
                if str(item.params.get("linkedMediaGroup") or "").strip() != linked_group:
                    continue
            elif item.locationId != target.locationId:
                continue
            targets.append(item)
        targets.sort(key=lambda item: (item.locationId, item.title.lower(), item.id))
        return targets

    def _tv_targets_for_remote(
        self, remote: WorldItem, target: WorldItem, *, require_presets: bool
    ) -> list[WorldItem]:
        """Return the TVs affected by a remote setting and current target."""

        if not self._remote_controls_linked_tvs(remote):
            if require_presets and not self._radio_presets(target):
                return []
            return [target]
        return self._tv_group_targets_for_remote(target, require_presets=require_presets)

    def _tv_station_source_for_target(self, target: WorldItem) -> WorldItem | None:
        """Return the preset-bearing TV that should define channel changes."""

        candidates: list[WorldItem] = []
        if self._radio_presets(target):
            candidates.append(target)
        for item in self._tv_group_targets_for_remote(target, require_presets=True):
            if item.id != target.id:
                candidates.append(item)
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                item.params.get("enabled") is False,
                item.id != target.id,
                item.locationId,
                item.title.lower(),
                item.id,
            )
        )
        return candidates[0]

    def _radio_targets_for_active_tv(self, tv: WorldItem) -> list[WorldItem]:
        """Return radios that should yield to or sync with an active TV."""

        linked_group = str(tv.params.get("linkedMediaGroup") or "").strip()
        targets: list[WorldItem] = []
        for item in self.items.values():
            if item.type != "radio_station" or item.carrierId is not None:
                continue
            if linked_group:
                if str(item.params.get("linkedMediaGroup") or "").strip() != linked_group:
                    continue
            elif item.locationId != tv.locationId:
                continue
            targets.append(item)
        targets.sort(key=lambda item: (item.locationId, item.title.lower(), item.id))
        return targets

    @staticmethod
    def _radio_should_sync_to_active_tv(radio: WorldItem) -> bool:
        """Return whether a radio item can behave as a TV speaker component."""

        if radio.type != "radio_station":
            return False
        if SignalingServer._radio_presets(radio):
            return False
        role = str(radio.params.get("speakerRole") or "primary").strip().lower()
        return role != "primary" or radio.params.get("syncWithPrimary") is True

    async def _reconcile_radios_for_active_tv(
        self,
        tv: WorldItem,
        client: ClientConnection,
        *,
        play_started_at: int | None = None,
    ) -> int:
        """Switch competing radios off or sync speaker components to an active TV."""

        if not self._is_tv_media_item(tv) or tv.params.get("enabled") is False:
            return 0
        stream_url = str(tv.params.get("streamUrl") or "").strip()
        playback_url = str(tv.params.get("playbackUrl") or "").strip()
        if not (stream_url or playback_url):
            return 0
        try:
            station_index = int(tv.params.get("stationIndex", 0) or 0)
        except (TypeError, ValueError):
            station_index = 0
        try:
            marker = int(play_started_at or tv.params.get("playStartedAt", 0) or 0)
        except (TypeError, ValueError):
            marker = 0
        if marker <= 0:
            marker = self.item_service.now_ms()
        station_name = str(tv.params.get("stationName") or "").strip() or tv.title
        now_playing = str(tv.params.get("nowPlaying") or "").strip()
        changed = 0
        for radio in self._radio_targets_for_active_tv(tv):
            previous_params = dict(radio.params)
            if self._radio_should_sync_to_active_tv(radio):
                next_params = {
                    **radio.params,
                    "enabled": True,
                    "stationIndex": station_index,
                    "streamUrl": stream_url,
                    "playbackUrl": playback_url,
                    "stationName": station_name,
                    "nowPlaying": now_playing,
                    "stationSwitchSound": "",
                    "playStartedAt": marker,
                }
            else:
                next_params = {
                    **radio.params,
                    "enabled": False,
                    "playStartedAt": 0,
                }
            if next_params == radio.params:
                continue
            try:
                radio.params = get_item_type_handler(radio.type).validate_update(
                    radio, next_params
                )
            except ValueError:
                continue
            if self._radio_should_sync_to_active_tv(radio):
                radio.params["playbackUrl"] = playback_url
                radio.params["stationName"] = station_name[:160]
                radio.params["nowPlaying"] = now_playing[:200]
                radio.params["playStartedAt"] = marker
            if radio.params == previous_params:
                continue
            radio.updatedAt = self.item_service.now_ms()
            actor_id, actor_name = self._item_updated_actor(client)
            radio.updatedBy = actor_id
            radio.updatedByName = actor_name
            radio.version += 1
            self._request_state_save()
            await self._broadcast_item(radio)
            changed += 1
        return changed

    def _radio_targets_for_remote(
        self, remote: WorldItem, target: WorldItem, *, require_presets: bool
    ) -> list[WorldItem]:
        """Return the radios affected by a remote setting and current target."""

        if not self._remote_controls_linked_radios(remote):
            if require_presets and not self._radio_presets(target):
                return []
            return [target]
        return self._radio_group_targets_for_remote(target, require_presets=require_presets)

    def _radio_station_source_for_target(self, target: WorldItem) -> WorldItem | None:
        """Return the preset-bearing radio that should define station changes."""

        candidates: list[WorldItem] = []
        if self._radio_presets(target):
            candidates.append(target)
        for item in self._radio_group_targets_for_remote(target, require_presets=True):
            if item.id != target.id:
                candidates.append(item)
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                item.params.get("enabled") is False,
                str(item.params.get("speakerRole") or "primary").strip().lower()
                != "primary",
                item.id != target.id,
                item.locationId,
                item.title.lower(),
                item.id,
            )
        )
        return candidates[0]

    def _playing_radio_source_for_group(self, target: WorldItem) -> WorldItem | None:
        """Return an active linked radio source that can feed a dropped component."""

        linked_group = str(target.params.get("linkedMediaGroup") or "").strip()
        if target.type != "radio_station" or not linked_group:
            return None
        candidates = [
            item
            for item in self.items.values()
            if item.id != target.id
            and item.type == "radio_station"
            and item.locationId == target.locationId
            and item.carrierId is None
            and str(item.params.get("linkedMediaGroup") or "").strip()
            == linked_group
            and item.params.get("enabled") is not False
            and (
                str(item.params.get("playbackUrl") or "").strip()
                or str(item.params.get("streamUrl") or "").strip()
            )
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                str(item.params.get("speakerRole") or "primary").strip().lower()
                != "primary",
                not self._radio_presets(item),
                item.title.lower(),
                item.id,
            )
        )
        return candidates[0]

    @staticmethod
    def _radio_is_active_playing_source(item: WorldItem) -> bool:
        """Return whether a radio has active media suitable for speaker linking."""

        if item.type != "radio_station" or item.params.get("enabled") is False:
            return False
        return bool(
            str(item.params.get("playbackUrl") or "").strip()
            or str(item.params.get("streamUrl") or "").strip()
        )

    @staticmethod
    def _radio_component_should_auto_link(item: WorldItem) -> bool:
        """Return whether a blank radio item should adopt a nearby playing group."""

        if item.type != "radio_station":
            return False
        if str(item.params.get("linkedMediaGroup") or "").strip():
            return False
        role = str(item.params.get("speakerRole") or "primary").strip().lower()
        return role != "primary" or item.params.get("syncWithPrimary") is True

    def _auto_link_radio_component_to_nearby_group(self, item: WorldItem) -> bool:
        """Link a blank speaker component to the nearest active grouped radio."""

        if not self._radio_component_should_auto_link(item):
            return False
        candidates: list[tuple[float, bool, bool, str, str, WorldItem]] = []
        for candidate in self.items.values():
            if (
                candidate.id == item.id
                or candidate.locationId != item.locationId
                or candidate.carrierId is not None
                or not self._radio_is_active_playing_source(candidate)
            ):
                continue
            group = str(candidate.params.get("linkedMediaGroup") or "").strip()
            if not group:
                continue
            distance = ((candidate.x - item.x) ** 2 + (candidate.y - item.y) ** 2) ** 0.5
            try:
                emit_range = int(candidate.params.get("emitRange", 10) or 10)
            except (TypeError, ValueError):
                emit_range = 10
            if distance > max(10, emit_range):
                continue
            role = str(candidate.params.get("speakerRole") or "primary").strip().lower()
            candidates.append(
                (
                    distance,
                    role != "primary",
                    not self._radio_presets(candidate),
                    candidate.title.lower(),
                    candidate.id,
                    candidate,
                )
            )
        if not candidates:
            return False
        candidates.sort()
        source = candidates[0][-1]
        item.params["linkedMediaGroup"] = str(
            source.params.get("linkedMediaGroup") or ""
        ).strip()
        item.params["syncWithPrimary"] = True
        return True

    async def _sync_dropped_radio_with_playing_group(self, item: WorldItem) -> bool:
        """Reconnect a dropped linked radio component to the group's active media."""

        if item.type != "radio_station":
            return False
        role = str(item.params.get("speakerRole") or "primary").strip().lower()
        should_sync = (
            item.params.get("syncWithPrimary") is True
            or role != "primary"
            or not str(item.params.get("streamUrl") or "").strip()
        )
        if not should_sync:
            return False
        source = self._playing_radio_source_for_group(item)
        if source is None:
            return False
        copied_fields = {
            "streamUrl": str(source.params.get("streamUrl") or "").strip(),
            "playbackUrl": str(source.params.get("playbackUrl") or "").strip(),
            "stationName": str(source.params.get("stationName") or "").strip(),
            "nowPlaying": str(source.params.get("nowPlaying") or "").strip(),
            "stationSwitchSound": str(
                source.params.get("stationSwitchSound") or ""
            ).strip(),
            "enabled": source.params.get("enabled") is not False,
        }
        try:
            copied_fields["playStartedAt"] = int(
                source.params.get("playStartedAt", 0) or 0
            )
        except (TypeError, ValueError):
            copied_fields["playStartedAt"] = 0
        try:
            copied_fields["stationIndex"] = int(source.params.get("stationIndex", 0))
        except (TypeError, ValueError):
            copied_fields["stationIndex"] = 0
        next_params = {**item.params, **copied_fields}
        if next_params == item.params:
            return False
        item.params = get_item_type_handler(item.type).validate_update(
            item, next_params
        )
        item.params.update(copied_fields)
        await self._resolve_radio_playback_before_broadcast(item)
        return True

    async def _sync_radio_speakers_from_primary(
        self, primary: WorldItem, client: ClientConnection
    ) -> int:
        """Keep same-room speaker components on the room's one real radio."""

        if primary.type != "radio_station":
            return 0
        group = str(primary.params.get("linkedMediaGroup") or "").strip()
        role = str(primary.params.get("speakerRole") or "primary").strip().lower()
        if not group or role != "primary":
            return 0
        marker = int(primary.params.get("playStartedAt", 0) or 0)
        copied = {
            "streamUrl": str(primary.params.get("streamUrl") or "").strip(),
            "playbackUrl": str(primary.params.get("playbackUrl") or "").strip(),
            "stationIndex": int(primary.params.get("stationIndex", 0) or 0),
            "stationName": str(primary.params.get("stationName") or "").strip(),
            "nowPlaying": str(primary.params.get("nowPlaying") or "").strip(),
            "stationSwitchSound": "",
            "enabled": primary.params.get("enabled") is not False,
            "playStartedAt": marker,
        }
        changed = 0
        for speaker in self.items.values():
            if (
                speaker.id == primary.id
                or speaker.type != "radio_station"
                or speaker.locationId != primary.locationId
                or speaker.carrierId is not None
                or str(speaker.params.get("linkedMediaGroup") or "").strip() != group
                or self._radio_presets(speaker)
            ):
                continue
            speaker.params = get_item_type_handler(speaker.type).validate_update(
                speaker, {**speaker.params, **copied, "syncWithPrimary": True}
            )
            speaker.params.update(copied)
            await self._resolve_radio_playback_before_broadcast(speaker)
            speaker.updatedAt = self.item_service.now_ms()
            speaker.updatedBy, speaker.updatedByName = self._item_updated_actor(client)
            speaker.version += 1
            await self._broadcast_item(speaker)
            changed += 1
        if changed:
            self._request_state_save()
        return changed

    async def _handle_radio_remote_control(
        self,
        client: ClientConnection,
        remote: WorldItem,
        action: Literal["station_next", "station_previous", "volume_up", "volume_down"],
    ) -> bool:
        """Handle explicit keyboard remote-control actions for a carried radio remote."""

        if not self._is_radio_remote(remote):
            return False
        if remote.carrierId != client.id:
            await self._send_item_result(
                client,
                False,
                "use",
                "The radio remote needs to be in your hand.",
                remote.id,
            )
            return True
        if not self._is_raywonder_house_location(client.location_id):
            await self._send_item_result(
                client,
                False,
                "use",
                "The radio remote is only programmed for the house radios.",
                remote.id,
            )
            return True
        target = self._nearest_house_radio_for_remote(client, remote)
        if target is None:
            await self._send_item_result(
                client,
                False,
                "use",
                "No house radio is available from this room.",
                remote.id,
            )
            return True

        if action in {"station_next", "station_previous"}:
            source = (
                self._radio_station_source_for_target(target)
                if self._remote_controls_linked_radios(remote)
                else target
            )
            presets = self._radio_presets(source) if source is not None else []
            if not presets:
                await self._send_item_result(
                    client,
                    False,
                    "use",
                    f"{target.title} has no station presets.",
                    remote.id,
                )
                return True
            step = 1 if action == "station_next" else -1
            next_index = self._radio_station_index(source, len(presets)) + step
            station = presets[next_index % len(presets)]["title"]
            station_state = presets[next_index % len(presets)]
            group_play_started_at = self.item_service.now_ms()
            changed = 0
            for item in self._radio_targets_for_remote(
                remote, target, require_presets=False
            ):
                try:
                    await self._apply_radio_station_state(
                        item,
                        next_index,
                        station_state,
                        client,
                        play_started_at=group_play_started_at,
                    )
                except ValueError:
                    continue
                changed += 1
            if changed <= 0:
                await self._send_item_result(
                    client,
                    False,
                    "use",
                    f"Remote could not tune {target.title} to {station}. Station presets were left intact.",
                    remote.id,
                )
                return True
            await self._send_item_result(
                client,
                True,
                "use",
                f"Remote tuned {changed} connected radio{'s' if changed != 1 else ''} to {station}.",
                remote.id,
            )
            return True

        step = 5 if action == "volume_up" else -5
        changed = 0
        changed_volumes: list[int] = []
        for item in self._radio_targets_for_remote(
            remote, target, require_presets=False
        ):
            try:
                current_volume = int(item.params.get("mediaVolume", 50))
            except (TypeError, ValueError):
                current_volume = 50
            next_volume = max(0, min(1000, current_volume + step))
            try:
                await self._apply_radio_media_volume(item, next_volume, client)
            except ValueError:
                continue
            changed += 1
            changed_volumes.append(next_volume)
        if changed <= 0:
            await self._send_item_result(
                client,
                False,
                "use",
                "No connected radio volume could be changed.",
                remote.id,
            )
            return True
        if changed_volumes and min(changed_volumes) == max(changed_volumes):
            volume_text = f"to volume {changed_volumes[0]}"
        else:
            volume_text = f"by {step:+d}, range {min(changed_volumes)} to {max(changed_volumes)}"
        await self._send_item_result(
            client,
            True,
            "use",
            f"Remote adjusted {changed} connected radio{'s' if changed != 1 else ''} {volume_text}.",
            remote.id,
        )
        return True

    async def _handle_tv_remote_control(
        self,
        client: ClientConnection,
        remote: WorldItem,
        action: Literal["station_next", "station_previous", "volume_up", "volume_down"],
    ) -> bool:
        """Handle explicit keyboard remote-control actions for a carried TV remote."""

        if not self._is_tv_remote(remote):
            return False
        if remote.carrierId != client.id:
            await self._send_item_result(
                client,
                False,
                "use",
                "The TV remote needs to be in your hand.",
                remote.id,
            )
            return True
        if not self._is_raywonder_house_location(client.location_id):
            await self._send_item_result(
                client,
                False,
                "use",
                "The TV remote is only programmed for the house TVs.",
                remote.id,
            )
            return True
        target = self._nearest_house_tv_for_remote(client, remote)
        if target is None:
            await self._send_item_result(
                client,
                False,
                "use",
                "No house TV is available from this room.",
                remote.id,
            )
            return True

        if action in {"station_next", "station_previous"}:
            source = (
                self._tv_station_source_for_target(target)
                if self._remote_controls_linked_tvs(remote)
                else target
            )
            presets = self._radio_presets(source) if source is not None else []
            if not presets:
                await self._send_item_result(
                    client,
                    False,
                    "use",
                    f"{target.title} has no channel presets.",
                    remote.id,
                )
                return True
            step = 1 if action == "station_next" else -1
            next_index = self._radio_station_index(source, len(presets)) + step
            channel_state = presets[next_index % len(presets)]
            channel = channel_state["title"]
            changed = 0
            play_started_at = self.item_service.now_ms()
            for item in self._tv_targets_for_remote(
                remote, target, require_presets=False
            ):
                try:
                    await self._apply_radio_station_state(
                        item,
                        next_index,
                        channel_state,
                        client,
                        enabled=True,
                        play_started_at=play_started_at,
                    )
                except ValueError:
                    continue
                await self._reconcile_radios_for_active_tv(
                    item, client, play_started_at=play_started_at
                )
                changed += 1
            if changed <= 0:
                await self._send_item_result(
                    client,
                    False,
                    "use",
                    f"Remote could not tune {target.title} to {channel}. Channel presets were left intact.",
                    remote.id,
                )
                return True
            await self._send_item_result(
                client,
                True,
                "use",
                f"Remote tuned {changed} connected TV{'s' if changed != 1 else ''} to {channel}.",
                remote.id,
            )
            return True

        step = 5 if action == "volume_up" else -5
        changed = 0
        changed_volumes: list[int] = []
        for item in self._tv_targets_for_remote(remote, target, require_presets=False):
            try:
                current_volume = int(item.params.get("mediaVolume", 50))
            except (TypeError, ValueError):
                current_volume = 50
            next_volume = max(0, min(1000, current_volume + step))
            try:
                await self._apply_radio_media_volume(item, next_volume, client)
            except ValueError:
                continue
            changed += 1
            changed_volumes.append(next_volume)
        if changed <= 0:
            await self._send_item_result(
                client,
                False,
                "use",
                "No connected TV volume could be changed.",
                remote.id,
            )
            return True
        if changed_volumes and min(changed_volumes) == max(changed_volumes):
            volume_text = f"to volume {changed_volumes[0]}"
        else:
            volume_text = f"by {step:+d}, range {min(changed_volumes)} to {max(changed_volumes)}"
        await self._send_item_result(
            client,
            True,
            "use",
            f"Remote adjusted {changed} connected TV{'s' if changed != 1 else ''} {volume_text}.",
            remote.id,
        )
        return True

    async def _handle_radio_remote_use(
        self, client: ClientConnection, remote: WorldItem, *, sync_all: bool
    ) -> bool:
        """Handle a universal house radio remote. Returns true when handled."""

        if not self._is_radio_remote(remote):
            return False
        if not self._is_raywonder_house_location(client.location_id):
            await self._send_item_result(
                client,
                False,
                "secondary_use" if sync_all else "use",
                "The radio remote is only programmed for the house radios.",
                remote.id,
            )
            return True
        target = self._nearest_house_radio_for_remote(client, remote)
        if target is None:
            await self._send_item_result(
                client,
                False,
                "secondary_use" if sync_all else "use",
                "No house radio is available from this room.",
                remote.id,
            )
            return True
        source = (
            self._radio_station_source_for_target(target)
            if self._remote_controls_linked_radios(remote)
            else target
        )
        presets = self._radio_presets(source) if source is not None else []
        if not presets:
            await self._send_item_result(
                client,
                False,
                "secondary_use" if sync_all else "use",
                f"{target.title} has no station presets.",
                remote.id,
            )
            return True

        if not sync_all:
            next_index = self._radio_station_index(source, len(presets)) + 1
            station = presets[next_index % len(presets)]["title"]
            station_state = presets[next_index % len(presets)]
            changed = 0
            for item in self._radio_targets_for_remote(
                remote, target, require_presets=False
            ):
                try:
                    await self._apply_radio_station_state(
                        item, next_index, station_state, client
                    )
                except ValueError:
                    continue
                changed += 1
            if changed <= 0:
                await self._send_item_result(
                    client,
                    False,
                    "use",
                    f"Remote could not tune {target.title} to {station}. Station presets were left intact.",
                    remote.id,
                )
                return True
            await self._send_item_result(
                client,
                True,
                "use",
                f"Remote tuned {changed} house radio station{'s' if changed != 1 else ''} to {station}.",
                remote.id,
            )
            return True

        target_index = self._radio_station_index(source, len(presets))
        station = presets[target_index]["title"]
        station_state = presets[target_index]
        changed = 0
        for item in self._radio_targets_for_remote(
            remote, target, require_presets=False
        ):
            try:
                await self._apply_radio_station_state(
                    item, target_index, station_state, client
                )
            except ValueError:
                continue
            changed += 1
        if changed <= 0:
            await self._send_item_result(
                client,
                False,
                "secondary_use",
                f"Remote could not tune {target.title} to {station}. Station presets were left intact.",
                remote.id,
            )
            return True
        await self._send_item_result(
            client,
            True,
            "secondary_use",
            f"Synced {changed} house radio speaker{'s' if changed != 1 else ''} to {station}.",
            remote.id,
        )
        return True

    async def _handle_tv_remote_use(
        self, client: ClientConnection, remote: WorldItem, *, sync_all: bool
    ) -> bool:
        """Handle a universal house TV remote. Returns true when handled."""

        if not self._is_tv_remote(remote):
            return False
        action = "secondary_use" if sync_all else "use"
        if not self._is_raywonder_house_location(client.location_id):
            await self._send_item_result(
                client,
                False,
                action,
                "The TV remote is only programmed for the house TVs.",
                remote.id,
            )
            return True
        target = self._nearest_house_tv_for_remote(client, remote)
        if target is None:
            await self._send_item_result(
                client,
                False,
                action,
                "No house TV is available from this room.",
                remote.id,
            )
            return True
        source = (
            self._tv_station_source_for_target(target)
            if self._remote_controls_linked_tvs(remote)
            else target
        )
        presets = self._radio_presets(source) if source is not None else []
        if not presets:
            await self._send_item_result(
                client,
                False,
                action,
                f"{target.title} has no channel presets.",
                remote.id,
            )
            return True

        target_index = self._radio_station_index(source, len(presets))
        next_index = target_index if sync_all else target_index + 1
        channel_state = presets[next_index % len(presets)]
        channel = channel_state["title"]
        changed = 0
        play_started_at = self.item_service.now_ms()
        for item in self._tv_targets_for_remote(remote, target, require_presets=False):
            try:
                await self._apply_radio_station_state(
                    item,
                    next_index,
                    channel_state,
                    client,
                    enabled=True,
                    play_started_at=play_started_at,
                )
            except ValueError:
                continue
            changed += 1
        if changed <= 0:
            await self._send_item_result(
                client,
                False,
                action,
                f"Remote could not tune {target.title} to {channel}. Channel presets were left intact.",
                remote.id,
            )
            return True
        if sync_all:
            message = (
                f"Synced {changed} house TV{'s' if changed != 1 else ''} to {channel}."
            )
        else:
            message = (
                f"Remote tuned {changed} house TV{'s' if changed != 1 else ''} to {channel}."
            )
        await self._send_item_result(client, True, action, message, remote.id)
        return True

    async def _repair_one_house_radio(
        self, item: WorldItem, client: ClientConnection
    ) -> list[str]:
        """Repair common in-world radio state issues and return change notes."""

        presets = self._radio_presets(item)
        next_params = dict(item.params)
        notes: list[str] = []
        if presets:
            index = self._radio_station_index(item, len(presets))
            station = presets[index]
            if item.params.get("stationIndex") != index:
                notes.append("station index")
            stream_url = str(item.params.get("streamUrl") or "").strip()
            if not stream_url or stream_url.startswith("htt*"):
                notes.append("stream URL")
                next_params["streamUrl"] = station["streamUrl"]
            if str(item.params.get("stationName") or "").strip() != station["title"]:
                notes.append("station name")
            next_params.update(
                {
                    "stationIndex": index,
                    "stationName": station["title"],
                    "stationSwitchSound": station.get("switchSound", ""),
                }
            )
        playback_url = str(item.params.get("playbackUrl") or "").strip()
        if playback_url.startswith("htt*"):
            notes.append("stale playback URL")
            next_params["playbackUrl"] = ""
        if item.params.get("enabled") is False:
            notes.append("power")
            next_params["enabled"] = True
        if not notes:
            return []

        handler = get_item_type_handler(item.type)
        previous_params = dict(item.params)
        item.params = handler.validate_update(item, next_params)
        await self._resolve_radio_playback_before_broadcast(item)
        now_ms = self.item_service.now_ms()
        self._sync_radio_play_started_at(item, previous_params, now_ms)
        item.updatedAt = now_ms
        actor_id, actor_name = self._item_updated_actor(client)
        item.updatedBy = actor_id
        item.updatedByName = actor_name
        item.version += 1
        self._request_state_save()
        await self._broadcast_item(item)
        return sorted(set(notes))

    async def _repair_one_house_object(
        self, item: WorldItem, client: ClientConnection
    ) -> list[str]:
        """Repair common in-world household object condition state."""

        condition = str(item.params.get("condition") or "intact").strip().lower()
        if condition not in {"broken", "cracked"}:
            return []
        handler = get_item_type_handler(item.type)
        item.params = handler.validate_update(
            item, {**item.params, "condition": "repaired"}
        )
        item.updatedAt = self.item_service.now_ms()
        actor_id, actor_name = self._item_updated_actor(client)
        item.updatedBy = actor_id
        item.updatedByName = actor_name
        item.version += 1
        self._request_state_save()
        await self._broadcast_item(item)
        return ["condition"]

    async def _run_house_keeper_auto_check(self, keeper: WorldItem) -> bool:
        """Run one quiet scheduled in-world house keeper check."""

        if not self._is_house_keeper(keeper):
            return False
        if not self._house_keeper_background_enabled(keeper):
            return False
        if keeper.carrierId is not None:
            return False
        now_ms = self.item_service.now_ms()
        last_check_at = int(keeper.params.get("lastAutoCheckAt") or 0)
        if last_check_at > 0 and (
            now_ms - last_check_at < self._house_keeper_check_interval_ms(keeper)
        ):
            return False

        moved = await self._move_house_keeper_one_step(keeper)
        targets = self._house_keeper_targets(keeper)
        repair_mode = str(
            keeper.params.get("repairMode") or "auto_repair"
        ).strip().lower()
        actor = self._house_keeper_system_client(keeper)
        inspected = 0
        fixed: list[str] = []

        if self._is_raywonder_house_location(keeper.locationId):
            candidates = [
                item
                for item in self.items.values()
                if item.id != keeper.id
                and item.carrierId is None
                and item.locationId == keeper.locationId
            ]
            candidates.sort(
                key=lambda item: (
                    abs(item.x - keeper.x) + abs(item.y - keeper.y),
                    item.title.lower(),
                    item.id,
                )
            )
            for item in candidates:
                if item.type == "radio_station" and "radio" in targets:
                    inspected += 1
                    if repair_mode == "auto_repair":
                        notes = await self._repair_one_house_radio(item, actor)
                        if notes:
                            fixed.append(f"{item.title} ({', '.join(notes)})")
                    continue
                if item.type == "house_object" and (
                    "object" in targets or "objects" in targets
                ):
                    inspected += 1
                    if repair_mode == "auto_repair":
                        notes = await self._repair_one_house_object(item, actor)
                        if notes:
                            fixed.append(f"{item.title} ({', '.join(notes)})")

        if fixed:
            summary = (
                f"Auto checked room; fixed {len(fixed)} item"
                f"{'s' if len(fixed) != 1 else ''}: {', '.join(fixed)}."
            )
        elif inspected:
            summary = (
                f"Auto checked {inspected} room item"
                f"{'s' if inspected != 1 else ''}; nothing needed repair."
            )
        else:
            summary = "Auto checked room; no supported repair targets were found."
        if moved:
            summary = f"Moved one tile. {summary}"
        summary = summary[:240]

        handler = get_item_type_handler(keeper.type)
        keeper.params = handler.validate_update(
            keeper,
            {
                **keeper.params,
                "lastAutoCheckAt": now_ms,
                "lastAutoCheckSummary": summary,
            },
        )
        keeper.updatedAt = now_ms
        keeper.updatedBy = "system:house_keeper"
        keeper.updatedByName = str(
            keeper.params.get("keeperName") or keeper.title or "House keeper"
        ).strip()
        keeper.version += 1
        await self._broadcast_item(keeper)
        self._request_state_save()
        LOGGER.info("house keeper auto-check item=%s summary=%s", keeper.id, summary)
        return True

    async def _run_house_keeper_loop(self) -> None:
        """Run scheduled baseline autonomy for in-world house keepers."""

        while True:
            for keeper in list(self.items.values()):
                if not self._is_house_keeper(keeper):
                    continue
                try:
                    await self._run_house_keeper_auto_check(keeper)
                except Exception as exc:
                    LOGGER.warning(
                        "house keeper auto-check failed item=%s: %s", keeper.id, exc
                    )
            await asyncio.sleep(HOUSE_KEEPER_AUTO_CHECK_POLL_INTERVAL_S)

    async def _handle_house_keeper_use(
        self, client: ClientConnection, keeper: WorldItem, *, deep_scan: bool
    ) -> bool:
        """Handle opt-in house keeper diagnostics and in-world repairs."""

        if not self._is_house_keeper(keeper):
            return False
        action = "secondary_use" if deep_scan else "use"
        if not self._house_keeper_authorized(keeper, client.nickname):
            await self._send_item_result(
                client,
                False,
                action,
                f"{keeper.title} is not authorized for {client.nickname}.",
                keeper.id,
            )
            return True
        targets = self._house_keeper_targets(keeper)
        repair_mode = str(keeper.params.get("repairMode") or "auto_repair").strip().lower()
        location_ids = {client.location_id}
        in_modeled_house = self._is_raywonder_house_location(client.location_id)
        if deep_scan and in_modeled_house:
            location_ids = {
                item.locationId
                for item in self.items.values()
                if self._is_raywonder_house_location(item.locationId)
            }
        candidates = [
            item
            for item in self.items.values()
            if item.carrierId is None and item.locationId in location_ids
        ]
        candidates.sort(
            key=lambda item: (
                abs(item.x - client.x) + abs(item.y - client.y),
                item.locationId,
                item.title.lower(),
                item.id,
            )
        )

        fixed: list[str] = []
        inspected = 0
        if in_modeled_house:
            for item in candidates:
                if item.id == keeper.id:
                    continue
                if item.type == "radio_station" and "radio" in targets:
                    inspected += 1
                    if repair_mode == "auto_repair":
                        notes = await self._repair_one_house_radio(item, client)
                        if notes:
                            fixed.append(f"{item.title} ({', '.join(notes)})")
                    continue
                if item.type == "house_object" and (
                    "object" in targets or "objects" in targets
                ):
                    inspected += 1
                    if repair_mode == "auto_repair":
                        notes = await self._repair_one_house_object(item, client)
                        if notes:
                            fixed.append(f"{item.title} ({', '.join(notes)})")

        location_notes: list[str] = []
        if repair_mode == "auto_repair" and (not in_modeled_house or not fixed):
            location_notes = await self._repair_community_locations(broadcast=True)

        keeper_name = str(keeper.params.get("keeperName") or keeper.title).strip()
        scope = "house" if deep_scan else "room"
        if fixed and location_notes:
            message = (
                f"{keeper_name} checked the {scope}, fixed {len(fixed)} "
                f"item{'s' if len(fixed) != 1 else ''}: {', '.join(fixed)}, "
                f"and repaired {len(location_notes)} community location issue"
                f"{'s' if len(location_notes) != 1 else ''}."
            )
        elif fixed:
            message = f"{keeper_name} checked the {scope} and fixed {len(fixed)} item{'s' if len(fixed) != 1 else ''}: {', '.join(fixed)}."
        elif location_notes:
            message = (
                f"{keeper_name} found no urgent house work and repaired "
                f"{len(location_notes)} community location issue"
                f"{'s' if len(location_notes) != 1 else ''}."
            )
        elif inspected:
            message = f"{keeper_name} checked {inspected} {scope} item{'s' if inspected != 1 else ''}. Nothing needed repair."
        elif not in_modeled_house:
            message = f"{keeper_name} checked nearby community locations. Nothing needed repair."
        else:
            message = f"{keeper_name} checked the {scope}. No supported repair targets were found."
        await self._send_item_result(client, True, action, message, keeper.id)
        return True

    def _get_item_emit_range(self, item: WorldItem) -> int:
        """Return effective emit range for one item with sane bounds."""

        value = item.params.get("emitRange")
        if isinstance(value, (int, float)):
            emit_range = int(value)
            if emit_range > 0:
                return emit_range
        definition = get_item_definition(item.type)
        if isinstance(definition.emit_range, int) and definition.emit_range > 0:
            return definition.emit_range
        return 15

    def _has_listener_in_range(self, item: WorldItem) -> bool:
        """Return whether any connected user is currently inside item hear range."""

        emit_range = self._get_item_emit_range(item)
        for client in self.clients.values():
            if client.location_id != item.locationId:
                continue
            if max(abs(client.x - item.x), abs(client.y - item.y)) <= emit_range:
                return True
        return False

    @staticmethod
    def _fetch_stream_metadata(stream_url: str) -> tuple[str, str, str]:
        """Read stream metadata and return station/title/resolved playback URL."""

        if not stream_url:
            return "", "", ""
        resolved = resolve_aaastreamer_playback(
            stream_url, timeout=RADIO_METADATA_TIMEOUT_S
        )
        if resolved is not None:
            return resolved.title, resolved.now_playing, resolved.playback_url
        try:
            with open_validated_public_url(
                stream_url,
                headers={"Icy-MetaData": "1", "User-Agent": "ChatGrid"},
                timeout=RADIO_METADATA_TIMEOUT_S,
            ) as response:
                station = str(
                    response.headers.get("icy-name")
                    or response.headers.get("ice-name")
                    or ""
                ).strip()
                title = ""
                metaint_raw = response.headers.get("icy-metaint")
                if metaint_raw:
                    metaint = int(metaint_raw)
                    if metaint > 0:
                        response.read(metaint)
                        meta_len_byte = response.read(1)
                        if meta_len_byte:
                            meta_length = meta_len_byte[0] * 16
                            if meta_length > 0:
                                meta = response.read(meta_length).decode(
                                    errors="ignore"
                                )
                                match = re.search(r"StreamTitle='(.*?)';", meta)
                                if match:
                                    title = match.group(1).strip()
                return station[:160], title[:200], ""
        except (OSError, URLError, ValueError):
            return "", "", ""

    async def _refresh_radio_metadata_once(self) -> None:
        """Refresh station/title metadata for active radios near at least one listener."""

        radios = [
            item
            for item in self.items.values()
            if item.type == "radio_station"
            and bool(item.params.get("enabled", True))
            and isinstance(item.params.get("streamUrl"), str)
            and str(item.params.get("streamUrl", "")).strip()
            and self._has_listener_in_range(item)
        ]
        for item in radios:
            stream_url = str(item.params.get("streamUrl", "")).strip()
            metadata = await asyncio.to_thread(self._fetch_stream_metadata, stream_url)
            # Keep compatibility with older test/integration overrides that
            # returned only station and title before playback URLs were added.
            station_name, now_playing = metadata[:2]
            playback_url = metadata[2] if len(metadata) > 2 else ""
            current_station = str(item.params.get("stationName", "")).strip()
            current_playing = str(item.params.get("nowPlaying", "")).strip()
            current_playback_url = str(item.params.get("playbackUrl", "")).strip()
            if (
                station_name == current_station
                and now_playing == current_playing
                and playback_url == current_playback_url
            ):
                continue
            item.params["stationName"] = station_name
            item.params["nowPlaying"] = now_playing
            item.params["playbackUrl"] = playback_url
            item.updatedAt = self.item_service.now_ms()
            item.updatedBy = "system"
            item.updatedByName = "system"
            item.version += 1
            self._request_state_save()
            await self._broadcast_item(item)

    async def _resolve_radio_playback_before_broadcast(self, item: WorldItem) -> None:
        """Resolve station-page playback before browsers try to play a media item."""

        if not self._is_stream_media_item(item) or item.params.get("enabled") is False:
            return
        stream_url = str(item.params.get("streamUrl", "")).strip()
        if not stream_url or str(item.params.get("playbackUrl", "")).strip():
            return
        station_name, now_playing, playback_url = await asyncio.to_thread(
            self._fetch_stream_metadata, stream_url
        )
        if station_name:
            item.params["stationName"] = station_name
        if now_playing:
            item.params["nowPlaying"] = now_playing
        if playback_url:
            item.params["playbackUrl"] = playback_url

    async def _resolve_radio_playback_for_items(
        self, items: Iterable[WorldItem]
    ) -> int:
        """Resolve active radio items and return the changed-item count."""

        now_ms = self.item_service.now_ms()
        changed_count = 0
        for item in items:
            previous_params = dict(item.params)
            await self._resolve_radio_playback_before_broadcast(item)
            if item.params == previous_params:
                continue
            self._sync_radio_play_started_at(item, previous_params, now_ms)
            item.updatedAt = now_ms
            item.updatedBy = "system"
            item.updatedByName = "system"
            item.version += 1
            changed_count += 1
        if changed_count:
            self._request_state_save()
        return changed_count

    async def _resolve_radio_playback_for_welcome(
        self, location_id: str
    ) -> None:
        """Resolve active media items before sending a location snapshot to a client."""

        await self._resolve_radio_playback_for_items(
            item
            for item in self.items.values()
            if item.locationId == location_id and self._is_stream_media_item(item)
        )

    async def _resolve_radio_playback_on_startup(self) -> None:
        """Resolve active persisted media items once so rooms start with playable URLs."""

        changed_count = await self._resolve_radio_playback_for_items(
            item for item in self.items.values() if self._is_stream_media_item(item)
        )
        if changed_count:
            LOGGER.info("resolved playback URLs for %d startup media items", changed_count)

    async def _run_radio_metadata_loop(self) -> None:
        """Background polling loop that refreshes radio now-playing metadata."""

        try:
            while True:
                await self._refresh_radio_metadata_once()
                await asyncio.sleep(RADIO_METADATA_POLL_INTERVAL_S)
        except asyncio.CancelledError:
            return

    @classmethod
    def _build_clock_time_sounds(cls, params: dict) -> list[str]:
        """Build ordered EL640 sample URLs for just the clock time phrase."""

        tz_name = cls._normalize_clock_timezone(params.get("timeZone"))
        use_24_hour = cls._parse_clock_use_24_hour(params.get("use24Hour")) is True
        now = datetime.now(ZoneInfo(tz_name))
        hour24 = now.hour
        minute = now.minute
        ampm = "AM" if hour24 < 12 else "PM"
        hour12 = hour24 % 12 or 12

        sounds: list[str] = ["/sounds/clock/el640/its.ogg"]

        if use_24_hour:
            if hour24 < 20:
                sounds.append(f"/sounds/clock/el640/{hour24}.ogg")
            else:
                tens = (hour24 // 10) * 10
                ones = hour24 % 10
                sounds.append(f"/sounds/clock/el640/{tens}.ogg")
                if ones != 0:
                    sounds.append(f"/sounds/clock/el640/{ones}.ogg")
        else:
            sounds.append(f"/sounds/clock/el640/{hour12}.ogg")

        if minute > 0:
            if minute < 10:
                sounds.append("/sounds/clock/el640/o.ogg")
            if minute < 20:
                sounds.append(f"/sounds/clock/el640/{minute}.ogg")
            else:
                tens = (minute // 10) * 10
                ones = minute % 10
                sounds.append(f"/sounds/clock/el640/{tens}.ogg")
                if ones != 0:
                    sounds.append(f"/sounds/clock/el640/{ones}.ogg")

        if not use_24_hour:
            sounds.append(f"/sounds/clock/el640/{ampm}.ogg")
        return sounds

    @classmethod
    def _build_clock_announcement_sounds(
        cls, params: dict, *, top_of_hour: bool, alarm: bool
    ) -> list[str]:
        """Build ordered EL640 sample URLs for one clock announcement variant."""

        sounds: list[str] = []
        if alarm:
            sounds.extend(
                [
                    "/sounds/clock/archive/bell-alert-gentle.ogg",
                    "/sounds/clock/el640/announcement.ogg",
                ]
            )
        elif top_of_hour:
            sounds.extend(
                [
                    "/sounds/clock/archive/bell-clear-single.ogg",
                    "/sounds/clock/el640/hour1.ogg",
                ]
            )
        else:
            sounds.append("/sounds/clock/archive/chime-hint-soft.ogg")
        sounds.extend(cls._build_clock_time_sounds(params))
        if alarm:
            sounds.append("/sounds/clock/el640/alarm.ogg")
        elif top_of_hour:
            sounds.append("/sounds/clock/el640/hour2.ogg")
        return sounds

    async def _broadcast_clock_announcement(
        self, item: WorldItem, *, top_of_hour: bool, alarm: bool
    ) -> None:
        """Broadcast one server-authoritative clock speech sequence from item position."""

        sound_x, sound_y = self._get_item_sound_source_position(item)
        sound_range = self._get_item_emit_range(item)
        sounds = self._build_clock_announcement_sounds(
            item.params, top_of_hour=top_of_hour, alarm=alarm
        )
        if not sounds:
            return
        await self._broadcast_location(
            item.locationId,
            ItemClockAnnouncePacket(
                type="item_clock_announce",
                itemId=item.id,
                sounds=sounds,
                x=sound_x,
                y=sound_y,
                range=sound_range,
            )
        )

    async def _run_clock_top_of_hour_loop(self) -> None:
        """Background polling loop that triggers scheduled speech for clock items."""

        try:
            while True:
                valid_clock_ids = {
                    item.id for item in self.items.values() if item.type == "clock"
                }
                for stale_id in list(self._clock_top_of_hour_markers.keys()):
                    if stale_id not in valid_clock_ids:
                        self._clock_top_of_hour_markers.pop(stale_id, None)
                for stale_id in list(self._clock_alarm_markers.keys()):
                    if stale_id not in valid_clock_ids:
                        self._clock_alarm_markers.pop(stale_id, None)
                for item in self.items.values():
                    if item.type != "clock":
                        continue
                    tz_name = self._normalize_clock_timezone(
                        item.params.get("timeZone")
                    )
                    now = datetime.now(ZoneInfo(tz_name))
                    top_of_hour_enabled = (
                        item.params.get("topOfHourAnnounce", True) is True
                    )
                    marker = (
                        self._clock_auto_announce_marker(now, item.params)
                        if top_of_hour_enabled
                        else None
                    )
                    if marker is not None:
                        if self._clock_top_of_hour_markers.get(item.id) != marker:
                            self._clock_top_of_hour_markers[item.id] = marker
                            interval_minutes = (
                                self._parse_clock_announce_interval_minutes(
                                    item.params.get("announceIntervalMinutes", 60)
                                )
                            )
                            await self._broadcast_clock_announcement(
                                item,
                                top_of_hour=interval_minutes == 60,
                                alarm=False,
                            )

                    alarm_enabled = item.params.get("alarmEnabled", False) is True
                    alarm_time = parse_alarm_time_flexible(
                        item.params.get("alarmTime", "")
                    )
                    if alarm_enabled and alarm_time is not None:
                        alarm_hour, alarm_minute = alarm_time
                        if (
                            now.hour == alarm_hour
                            and now.minute == alarm_minute
                            and now.second <= 1
                        ):
                            marker = now.strftime("%Y-%m-%d-%H-%M")
                            if self._clock_alarm_markers.get(item.id) != marker:
                                self._clock_alarm_markers[item.id] = marker
                                await self._broadcast_clock_announcement(
                                    item, top_of_hour=False, alarm=True
                                )
                await asyncio.sleep(CLOCK_ANNOUNCE_POLL_INTERVAL_S)
        except asyncio.CancelledError:
            return

    def _get_item_sound_source_position(self, item: WorldItem) -> tuple[int, int]:
        """Resolve source position for item-emitted one-shot sounds."""

        if item.carrierId:
            carrier = self._get_client_by_id(item.carrierId)
            if carrier is not None:
                return carrier.x, carrier.y
        return item.x, item.y

    def _get_client_by_id(self, client_id: str) -> ClientConnection | None:
        """Resolve one connected client by id."""

        for connected in self.clients.values():
            if connected.id == client_id:
                return connected
        return None

    def _get_piano_source_position(self, item: WorldItem) -> tuple[int, int]:
        """Resolve world position used for piano note spatial broadcasts."""

        if item.carrierId:
            carrier = self._get_client_by_id(item.carrierId)
            if carrier is not None:
                return carrier.x, carrier.y
        return item.x, item.y

    async def _broadcast_item_piano_note(
        self,
        item: WorldItem,
        *,
        sender_id: str,
        key_id: str,
        midi: int,
        on: bool,
        instrument_override: str | None = None,
        voice_mode_override: str | None = None,
        attack_override: int | None = None,
        decay_override: int | None = None,
        release_override: int | None = None,
        brightness_override: int | None = None,
        emit_range_override: int | None = None,
        exclude: ServerConnection | None = None,
    ) -> None:
        """Broadcast one piano note event using current item synth settings."""

        instrument = (
            (
                instrument_override
                if isinstance(instrument_override, str)
                else str(item.params.get("instrument", "piano"))
            )
            .strip()
            .lower()
        )
        voice_mode = (
            (
                voice_mode_override
                if isinstance(voice_mode_override, str)
                else str(item.params.get("voiceMode", "poly"))
            )
            .strip()
            .lower()
        )
        if voice_mode not in {"poly", "mono"}:
            voice_mode = "poly"
        octave = (
            int(item.params.get("octave", 0))
            if isinstance(item.params.get("octave", 0), (int, float))
            else 0
        )
        attack = (
            int(attack_override)
            if isinstance(attack_override, int)
            else int(item.params.get("attack", 15))
            if isinstance(item.params.get("attack", 15), (int, float))
            else 15
        )
        decay = (
            int(decay_override)
            if isinstance(decay_override, int)
            else int(item.params.get("decay", 45))
            if isinstance(item.params.get("decay", 45), (int, float))
            else 45
        )
        release = (
            int(release_override)
            if isinstance(release_override, int)
            else int(item.params.get("release", 35))
            if isinstance(item.params.get("release", 35), (int, float))
            else 35
        )
        brightness = (
            int(brightness_override)
            if isinstance(brightness_override, int)
            else int(item.params.get("brightness", 55))
            if isinstance(item.params.get("brightness", 55), (int, float))
            else 55
        )
        emit_range = (
            int(emit_range_override)
            if isinstance(emit_range_override, int)
            else int(item.params.get("emitRange", 15))
            if isinstance(item.params.get("emitRange", 15), (int, float))
            else 15
        )
        source_x, source_y = self._get_piano_source_position(item)
        await self._broadcast_location(
            item.locationId,
            ItemPianoNoteBroadcastPacket(
                type="item_piano_note",
                itemId=item.id,
                senderId=sender_id,
                keyId=key_id,
                midi=max(0, min(127, int(midi))),
                on=on,
                instrument=instrument,
                voiceMode=voice_mode,
                octave=max(-2, min(2, octave)),
                attack=max(0, min(100, attack)),
                decay=max(0, min(100, decay)),
                release=max(0, min(100, release)),
                brightness=max(0, min(100, brightness)),
                x=source_x,
                y=source_y,
                emitRange=max(5, min(20, emit_range)),
            ),
            exclude=exclude,
        )

    def _cancel_piano_playback(self, item_id: str) -> None:
        """Cancel active playback task for one piano item, if any."""

        task = self.piano_playback_tasks_by_item.pop(item_id, None)
        if task is not None and not task.done():
            task.cancel()

    @staticmethod
    def _recording_elapsed_ms(
        session: PianoRecordingSession, now_monotonic: float | None = None
    ) -> int:
        """Compute effective recorded duration, including currently active segment."""

        elapsed_ms = (
            int(session.get("elapsedMs", 0))
            if isinstance(session.get("elapsedMs"), (int, float))
            else 0
        )
        paused = session.get("paused") is True
        if paused:
            return max(0, elapsed_ms)
        last_resume = session.get("lastResumeMonotonic")
        if isinstance(last_resume, (int, float)):
            now_value = (
                now_monotonic
                if isinstance(now_monotonic, (int, float))
                else time.monotonic()
            )
            elapsed_ms += max(0, int((now_value - float(last_resume)) * 1000))
        return max(0, elapsed_ms)

    async def _finalize_piano_recording(
        self, item_id: str, *, notify_owner: bool = False
    ) -> None:
        """Persist and broadcast one active recording session, then clear runtime state."""

        session = self.piano_recording_state_by_item.pop(item_id, None)
        if not session:
            return
        auto_stop_task = session.get("autoStopTask")
        if isinstance(auto_stop_task, asyncio.Task) and not auto_stop_task.done():
            auto_stop_task.cancel()
        item = self.items.get(item_id)
        if not item or item.type != "piano":
            return
        elapsed_ms = max(
            0, min(PIANO_RECORDING_MAX_MS, self._recording_elapsed_ms(session))
        )
        events = list(session.get("events", []))
        song_id = f"item:{item.id}:recording"
        keys: list[str] = []
        key_to_index: dict[str, int] = {}
        states: list[list[object]] = []
        state_to_index: dict[tuple[object, ...], int] = {}
        compact_events: list[list[int]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            t = (
                int(event.get("t", 0))
                if isinstance(event.get("t"), (int, float))
                else 0
            )
            key_id = str(event.get("keyId", "")).strip()
            midi = (
                int(event.get("midi", 0))
                if isinstance(event.get("midi"), (int, float))
                else 0
            )
            on = 1 if event.get("on") is True else 0
            instrument = (
                str(event.get("instrument", "piano")).strip().lower() or "piano"
            )
            voice_mode = str(event.get("voiceMode", "poly")).strip().lower()
            if voice_mode not in {"mono", "poly"}:
                voice_mode = "poly"
            attack = (
                int(event.get("attack", 15))
                if isinstance(event.get("attack"), (int, float))
                else 15
            )
            decay = (
                int(event.get("decay", 45))
                if isinstance(event.get("decay"), (int, float))
                else 45
            )
            release = (
                int(event.get("release", 35))
                if isinstance(event.get("release"), (int, float))
                else 35
            )
            brightness = (
                int(event.get("brightness", 55))
                if isinstance(event.get("brightness"), (int, float))
                else 55
            )
            emit_range = (
                int(event.get("emitRange", 15))
                if isinstance(event.get("emitRange"), (int, float))
                else 15
            )
            state_key = (
                instrument,
                voice_mode,
                max(0, min(100, attack)),
                max(0, min(100, decay)),
                max(0, min(100, release)),
                max(0, min(100, brightness)),
                max(5, min(20, emit_range)),
            )
            if not key_id:
                continue
            index = key_to_index.get(key_id)
            if index is None:
                index = len(keys)
                keys.append(key_id)
                key_to_index[key_id] = index
            state_index = state_to_index.get(state_key)
            if state_index is None:
                state_index = len(states)
                states.append(list(state_key))
                state_to_index[state_key] = state_index
            compact_events.append(
                [
                    max(0, min(PIANO_RECORDING_MAX_MS, t)),
                    index,
                    max(0, min(127, midi)),
                    on,
                    state_index,
                ]
            )
        compact_events.sort(key=lambda row: row[0])
        first_state = states[0] if states else ["piano", "poly", 15, 45, 35, 55, 15]
        self.item_service.piano_songs[song_id] = {
            "meta": {
                "instrument": first_state[0],
                "voiceMode": first_state[1],
                "attack": first_state[2],
                "decay": first_state[3],
                "release": first_state[4],
                "brightness": first_state[5],
                "emitRange": first_state[6],
                "recordingLengthMs": elapsed_ms,
            },
            "keys": keys,
            "states": states,
            "events": compact_events,
        }
        self.item_service.save_piano_songs()
        owner_id = str(session.get("ownerClientId", ""))
        owner = self._get_client_by_id(owner_id) if owner_id else None
        item.params["songId"] = song_id
        item.params.pop("recording", None)
        item.params.pop("recordingLengthMs", None)
        item.updatedAt = self.item_service.now_ms()
        item.updatedBy = owner.user_id if owner and owner.user_id else "system"
        item.updatedByName = owner.username if owner and owner.username else "system"
        item.version += 1
        self._request_state_save()
        await self._broadcast_item(item)
        if owner and notify_owner:
            await self._send_piano_status(
                owner,
                item_id=item.id,
                event="record_stopped",
                recording_state="idle",
            )
            await self._send_item_result(
                owner, True, "use", "Recording stopped.", item.id
            )

    async def _auto_stop_piano_recording(self, item_id: str) -> None:
        """Stop a recording automatically at the max recording duration."""

        try:
            while True:
                session = self.piano_recording_state_by_item.get(item_id)
                if session is None:
                    return
                if self._recording_elapsed_ms(session) >= PIANO_RECORDING_MAX_MS:
                    await self._finalize_piano_recording(item_id, notify_owner=True)
                    return
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            return

    async def _start_piano_playback(self, item: WorldItem) -> None:
        """Run one piano recording playback task and broadcast note events."""

        sender_id = f"item:{item.id}:playback"
        events: list[PianoRecordingEvent] = []
        song_id = str(item.params.get("songId", "")).strip()
        song_payload = self.item_service.piano_songs.get(song_id) if song_id else None
        if isinstance(song_payload, dict):
            keys = song_payload.get("keys")
            states = song_payload.get("states")
            compact_events = song_payload.get("events")
            meta = song_payload.get("meta")
            if isinstance(keys, list) and isinstance(compact_events, list):
                base_state = None
                if isinstance(meta, dict):
                    instrument = (
                        str(meta.get("instrument", "")).strip().lower() or "piano"
                    )
                    raw_voice_mode = str(meta.get("voiceMode", "")).strip().lower()
                    voice_mode = (
                        raw_voice_mode if raw_voice_mode in {"mono", "poly"} else "poly"
                    )
                    attack = (
                        int(meta.get("attack", 15))
                        if isinstance(meta.get("attack"), (int, float))
                        else 15
                    )
                    decay = (
                        int(meta.get("decay", 45))
                        if isinstance(meta.get("decay"), (int, float))
                        else 45
                    )
                    release = (
                        int(meta.get("release", 35))
                        if isinstance(meta.get("release"), (int, float))
                        else 35
                    )
                    brightness = (
                        int(meta.get("brightness", 55))
                        if isinstance(meta.get("brightness"), (int, float))
                        else 55
                    )
                    emit_range = (
                        int(meta.get("emitRange", 15))
                        if isinstance(meta.get("emitRange"), (int, float))
                        else 15
                    )
                    base_state = (
                        instrument,
                        voice_mode,
                        max(0, min(100, attack)),
                        max(0, min(100, decay)),
                        max(0, min(100, release)),
                        max(0, min(100, brightness)),
                        max(5, min(20, emit_range)),
                    )
                for row in compact_events:
                    if not isinstance(row, list) or len(row) < 4:
                        continue
                    raw_time, raw_key_idx, raw_midi, raw_on = row[:4]
                    if (
                        not isinstance(raw_time, (int, float))
                        or not isinstance(raw_key_idx, (int, float))
                        or not isinstance(raw_midi, (int, float))
                    ):
                        continue
                    key_idx = int(raw_key_idx)
                    if key_idx < 0 or key_idx >= len(keys):
                        continue
                    raw_key = keys[key_idx]
                    if not isinstance(raw_key, str) or not raw_key.strip():
                        continue
                    state = base_state
                    if (
                        len(row) >= 5
                        and isinstance(states, list)
                        and isinstance(row[4], (int, float))
                    ):
                        state_idx = int(row[4])
                        if 0 <= state_idx < len(states):
                            state_row = states[state_idx]
                            if isinstance(state_row, list) and len(state_row) >= 7:
                                candidate_instrument = (
                                    str(state_row[0]).strip().lower() or "piano"
                                )
                                candidate_voice_mode = str(state_row[1]).strip().lower()
                                state = (
                                    candidate_instrument,
                                    candidate_voice_mode
                                    if candidate_voice_mode in {"mono", "poly"}
                                    else "poly",
                                    max(
                                        0,
                                        min(
                                            100,
                                            int(state_row[2])
                                            if isinstance(state_row[2], (int, float))
                                            else 15,
                                        ),
                                    ),
                                    max(
                                        0,
                                        min(
                                            100,
                                            int(state_row[3])
                                            if isinstance(state_row[3], (int, float))
                                            else 45,
                                        ),
                                    ),
                                    max(
                                        0,
                                        min(
                                            100,
                                            int(state_row[4])
                                            if isinstance(state_row[4], (int, float))
                                            else 35,
                                        ),
                                    ),
                                    max(
                                        0,
                                        min(
                                            100,
                                            int(state_row[5])
                                            if isinstance(state_row[5], (int, float))
                                            else 55,
                                        ),
                                    ),
                                    max(
                                        5,
                                        min(
                                            20,
                                            int(state_row[6])
                                            if isinstance(state_row[6], (int, float))
                                            else 15,
                                        ),
                                    ),
                                )
                    if state is None:
                        continue
                    events.append(
                        {
                            "t": max(0, min(PIANO_RECORDING_MAX_MS, int(raw_time))),
                            "keyId": raw_key[:32],
                            "midi": max(0, min(127, int(raw_midi))),
                            "on": bool(raw_on),
                            "instrument": state[0],
                            "voiceMode": state[1],
                            "attack": state[2],
                            "decay": state[3],
                            "release": state[4],
                            "brightness": state[5],
                            "emitRange": state[6],
                        }
                    )
        events.sort(key=lambda entry: int(entry["t"]))
        if not events:
            return

        active_keys: dict[str, int] = {}
        previous_at_ms = 0
        try:
            for event in events:
                current_at_ms = int(event["t"])
                delay_ms = max(0, current_at_ms - previous_at_ms)
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000)
                current_item = self.items.get(item.id)
                if not current_item or current_item.type != "piano":
                    break
                key_id = str(event["keyId"])
                midi = int(event["midi"])
                on = bool(event["on"])
                if on:
                    active_keys[key_id] = midi
                else:
                    active_keys.pop(key_id, None)
                await self._broadcast_item_piano_note(
                    current_item,
                    sender_id=sender_id,
                    key_id=key_id,
                    midi=midi,
                    on=on,
                    instrument_override=event.get("instrument")
                    if isinstance(event.get("instrument"), str)
                    else None,
                    voice_mode_override=event.get("voiceMode")
                    if isinstance(event.get("voiceMode"), str)
                    else None,
                    attack_override=event.get("attack")
                    if isinstance(event.get("attack"), int)
                    else None,
                    decay_override=event.get("decay")
                    if isinstance(event.get("decay"), int)
                    else None,
                    release_override=event.get("release")
                    if isinstance(event.get("release"), int)
                    else None,
                    brightness_override=event.get("brightness")
                    if isinstance(event.get("brightness"), int)
                    else None,
                    emit_range_override=event.get("emitRange")
                    if isinstance(event.get("emitRange"), int)
                    else None,
                )
                previous_at_ms = current_at_ms
        except asyncio.CancelledError:
            pass
        finally:
            current_item = self.items.get(item.id)
            if current_item and current_item.type == "piano":
                for key_id, midi in list(active_keys.items()):
                    await self._broadcast_item_piano_note(
                        current_item,
                        sender_id=sender_id,
                        key_id=key_id,
                        midi=midi,
                        on=False,
                    )
            current_task = self.piano_playback_tasks_by_item.get(item.id)
            if current_task is asyncio.current_task():
                self.piano_playback_tasks_by_item.pop(item.id, None)

    def _is_in_bounds(self, x: int, y: int, location_id: str | None = None) -> bool:
        """Check whether a coordinate is inside server-authoritative world bounds."""

        location = self._get_world_location(location_id or DEFAULT_LOCATION_ID)
        return 0 <= x < min(self.grid_size, location.width) and 0 <= y < min(self.grid_size, location.height)

    def _movement_window_index(self, now_ms: int) -> int:
        """Return current movement rate-limit window index for a server timestamp."""

        return max(0, now_ms // self.movement_tick_ms)

    def _consume_movement_budget(
        self, client: ClientConnection, now_ms: int, requested_delta: int
    ) -> bool:
        """Consume per-window movement budget; return whether the move is allowed."""

        window_index = self._movement_window_index(now_ms)
        if client.movement_window_index != window_index:
            client.movement_window_index = window_index
            client.movement_window_steps_used = 0
        remaining = max(
            0, self.movement_max_steps_per_tick - client.movement_window_steps_used
        )
        if requested_delta > remaining:
            return False
        client.movement_window_steps_used += requested_delta
        return True

    @staticmethod
    def _normalize_clock_timezone(value: object) -> str:
        """Normalize timezone input to one of supported clock zones."""

        token = str(value or "").strip()
        if token in CLOCK_TIME_ZONE_OPTIONS:
            return token
        return CLOCK_DEFAULT_TIME_ZONE

    @staticmethod
    def _parse_clock_use_24_hour(value: object) -> bool | None:
        """Parse bool-like clock format values (`on/off`, `true/false`, etc.)."""

        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            token = value.strip().lower()
            if token in {"on", "true", "1", "yes"}:
                return True
            if token in {"off", "false", "0", "no"}:
                return False
        return None

    @staticmethod
    def _parse_clock_announce_interval_minutes(value: object) -> int:
        """Normalize automatic clock announcement interval to 1-60 minutes."""

        try:
            parsed = int(str(value or "").strip())
        except (TypeError, ValueError):
            parsed = 60
        return max(1, min(60, parsed))

    @classmethod
    def _clock_auto_announce_marker(cls, now: datetime, params: dict) -> str | None:
        """Return a per-minute marker when this clock should auto-announce now."""

        if now.second > 1:
            return None
        interval_minutes = cls._parse_clock_announce_interval_minutes(
            params.get("announceIntervalMinutes", 60)
        )
        if now.minute % interval_minutes != 0:
            return None
        return now.strftime("%Y-%m-%d-%H-%M")

    @classmethod
    def _format_clock_display_time(cls, params: dict) -> str:
        """Render current clock text based on item timezone/format params."""

        tz_name = cls._normalize_clock_timezone(params.get("timeZone"))
        use_24_hour = cls._parse_clock_use_24_hour(params.get("use24Hour"))
        if use_24_hour is None:
            use_24_hour = False
        now = datetime.now(ZoneInfo(tz_name))
        if use_24_hour:
            return now.strftime("%H:%M")
        hour_12 = now.hour % 12 or 12
        return f"{hour_12}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}"

    async def _change_client_location(
        self, client: ClientConnection, location_id: str
    ) -> bool:
        """Move one client to another world location and sync its local room state."""

        await self._repair_community_locations(broadcast=True)
        next_location = self._get_world_location(location_id)
        old_location_id = client.location_id
        if next_location.id == old_location_id:
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"You are already in {next_location.name}.",
                    system=True,
                ),
            )
            return False

        await self._broadcast_location(
            old_location_id,
            UserLeftPacket(type="user_left", id=client.id),
            exclude=client.websocket,
        )
        await self._broadcast_location(
            old_location_id,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=f"{client.nickname} left for {next_location.name}.",
                system=True,
            ),
            exclude=client.websocket,
        )

        old_x = client.x
        old_y = client.y
        now_ms = self.item_service.now_ms()
        carry_scope_changed = self._carry_scope_for_location(
            old_location_id
        ) != self._carry_scope_for_location(next_location.id)
        await self._clear_hand_connections(client)
        if carry_scope_changed:
            await self._return_carried_items_before_scope_exit(
                client,
                old_location_id=old_location_id,
                old_x=old_x,
                old_y=old_y,
                now_ms=now_ms,
            )
        client.location_id = next_location.id
        client.x = min(max(next_location.spawn_x, 0), self.grid_size - 1)
        client.y = min(max(next_location.spawn_y, 0), self.grid_size - 1)
        client.seated_item_id = None
        client.seated_offset = 0.0
        client.posture = "standing"
        client.last_position_update_ms = now_ms
        client.movement_window_index = self._movement_window_index(now_ms)
        client.movement_window_steps_used = 0
        self._persist_client_position(client, force=True)
        if not carry_scope_changed:
            await self._update_carried_items_after_client_move(
                client,
                old_x=old_x,
                old_y=old_y,
                now_ms=now_ms,
                location_changed=True,
            )

        await self._send(
            client.websocket,
            LocationChangedPacket(
                type="location_changed",
                id=client.id,
                userId=client.user_id,
                nickname=client.nickname,
                locationId=client.location_id,
                locationName=next_location.name,
                x=client.x,
                y=client.y,
            ),
        )
        for other in self.clients.values():
            if other.id == client.id or other.location_id != client.location_id:
                continue
            await self._send(
                client.websocket,
                LocationChangedPacket(
                    type="location_changed",
                    id=other.id,
                    userId=other.user_id,
                    nickname=other.nickname,
                    locationId=other.location_id,
                    locationName=next_location.name,
                    x=other.x,
                    y=other.y,
                ),
            )
        for item in self.items.values():
            if item.locationId == client.location_id:
                await self._send(
                    client.websocket,
                    ItemUpsertPacket(type="item_upsert", item=self._outbound_item(item)),
                )
        await self._broadcast_location(
            client.location_id,
            LocationChangedPacket(
                type="location_changed",
                id=client.id,
                userId=client.user_id,
                nickname=client.nickname,
                locationId=client.location_id,
                locationName=next_location.name,
                x=client.x,
                y=client.y,
            ),
            exclude=client.websocket,
        )
        await self._broadcast_location(
            client.location_id,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=f"{client.nickname} arrived in {next_location.name}.",
                system=True,
            ),
            exclude=client.websocket,
        )
        await self._send(
            client.websocket,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=f"You arrive in {next_location.name}. {next_location.description}",
                system=True,
            ),
        )
        self._request_state_save()
        return True

    async def _send_item_result(
        self,
        client: ClientConnection,
        ok: bool,
        action: Literal[
            "add",
            "pickup",
            "drop",
            "delete",
            "transfer",
            "use",
            "secondary_use",
            "interact",
            "update",
        ],
        message: str,
        item_id: str | None = None,
    ) -> None:
        """Send a structured item action result to one client."""

        await self._send(
            client.websocket,
            ItemActionResultPacket(
                type="item_action_result",
                ok=ok,
                action=action,
                message=message,
                itemId=item_id,
            ),
        )

    @staticmethod
    def _item_mobility(item: WorldItem) -> str:
        """Return a normalized mobility marker for item pickup/drop validation."""

        raw_mobility = str(item.params.get("itemMobility") or "").strip().lower()
        raw_size = str(item.params.get("itemSize") or "").strip().lower()
        return raw_mobility or raw_size

    def _item_can_be_relocated(self, item: WorldItem) -> bool:
        """Return whether an item can be carried or moved as part of an assembly."""

        mobility = self._item_mobility(item)
        if mobility in {"fixed", "fixture", "anchored", "immovable"}:
            return False
        if item.type == "house_object":
            placement = str(item.params.get("placement") or "").strip().lower()
            if placement in {"wall", "ceiling", "window", "fixture"}:
                return False
        return "carryable" in item.capabilities

    @staticmethod
    def _carried_load_count(items: list[WorldItem]) -> int:
        """Count carried roots while treating surfaced contents as part of their furniture load."""

        carried_ids = {item.id for item in items}
        return sum(
            1
            for item in items
            if str(item.params.get("surfaceId", "") or "").strip() not in carried_ids
        )

    def _client_can_pickup_drop_item(
        self, client: ClientConnection, item: WorldItem
    ) -> bool:
        """Return whether the client may pick up/drop one item component."""

        return self._client_has_permission(
            client, "item.pickup_drop.any"
        ) or (
            self._client_has_permission(client, "item.pickup_drop.own")
            and self._owns_item(client, item)
        )

    def _linked_relocation_items(
        self, item: WorldItem, *, include_attached: bool = True
    ) -> list[WorldItem]:
        """Return the item set that should relocate with this item."""

        linked = (
            list(self.item_service.linked_assembly_for_item(item))
            if include_attached
            else [item]
        )
        linked_ids = {linked_item.id for linked_item in linked}
        if include_attached:
            changed = True
            while changed:
                changed = False
                for candidate in self.items.values():
                    if candidate.id in linked_ids or candidate.locationId != item.locationId:
                        continue
                    surface_id = str(candidate.params.get("surfaceId", "") or "").strip()
                    if surface_id in linked_ids:
                        linked.append(candidate)
                        linked_ids.add(candidate.id)
                        changed = True
        linked.sort(key=lambda linked_item: (linked_item.id != item.id, linked_item.id))
        return linked or [item]

    @staticmethod
    def _item_surface_moves_with_linked_set(
        item: WorldItem, linked_ids: set[str]
    ) -> bool:
        """Return whether an item should stay attached to a moved surface."""

        surface_id = str(item.params.get("surfaceId", "") or "").strip()
        return bool(surface_id and surface_id in linked_ids)

    def _linked_relocation_label(self, items: list[WorldItem]) -> str:
        """Return a short phrase for single-item vs linked-assembly results."""

        if len(items) == 1:
            return items[0].title
        return f"{items[0].title} and {len(items) - 1} linked part{'s' if len(items) != 2 else ''}"

    def _validate_linked_pickup(
        self, client: ClientConnection, root: WorldItem, items: list[WorldItem]
    ) -> str | None:
        """Return a user-facing validation error for linked pickup, if any."""

        for item in items:
            if item.carrierId and item.carrierId != client.id:
                return f"{item.title} is already being carried."
            if item.carrierId is None and item.locationId != client.location_id:
                return f"{item.title} is in another location."
            if not self._item_can_be_relocated(item):
                return f"{item.title} is fixed in place and cannot be picked up."
            if not self._client_can_pickup_drop_item(client, item):
                return f"Not authorized to pick up {item.title}."
        if root.carrierId is None and (root.x != client.x or root.y != client.y):
            return "Item is not on your square."
        return None

    def _validate_linked_drop(
        self, client: ClientConnection, root: WorldItem, items: list[WorldItem], x: int, y: int
    ) -> str | None:
        """Return a user-facing validation error for linked drop, if any."""

        if not self._is_in_bounds(x, y, client.location_id):
            return "Drop position is out of bounds."
        for item in items:
            if item.carrierId != client.id:
                return f"You are not carrying {item.title}."
            if not self._item_can_be_relocated(item):
                return f"{item.title} is fixed in place and cannot be dropped."
            if not self._client_can_pickup_drop_item(client, item):
                return f"Not authorized to drop {item.title}."
            next_x = x + (item.x - root.x)
            next_y = y + (item.y - root.y)
            if not self._is_in_bounds(next_x, next_y, client.location_id):
                return f"Dropping there would put {item.title} out of bounds."
        return None

    async def _update_carried_items_after_client_move(
        self,
        client: ClientConnection,
        *,
        old_x: int,
        old_y: int,
        now_ms: int,
        location_changed: bool = False,
    ) -> None:
        """Move every item carried by a client, preserving linked offsets."""

        carried_items = self.item_service.carried_items_for_client(client.id)
        if not carried_items:
            return
        actor_id, actor_name = self._item_updated_actor(client)
        delta_x = client.x - old_x
        delta_y = client.y - old_y
        for item in carried_items:
            if location_changed:
                item.locationId = client.location_id
            item.x = item.x + delta_x
            item.y = item.y + delta_y
            if not self._is_in_bounds(item.x, item.y, client.location_id):
                location = self._get_world_location(client.location_id)
                item.x = min(max(item.x, 0), min(self.grid_size, location.width) - 1)
                item.y = min(max(item.y, 0), min(self.grid_size, location.height) - 1)
            item.updatedAt = now_ms
            item.updatedBy = actor_id
            item.updatedByName = actor_name
            await self._broadcast_item(item)

    async def _return_carried_items_before_scope_exit(
        self,
        client: ClientConnection,
        *,
        old_location_id: str,
        old_x: int,
        old_y: int,
        now_ms: int,
    ) -> None:
        """Drop held items in the place the user is leaving so they can be found again."""

        carried_items = self.item_service.carried_items_for_client(client.id)
        if not carried_items:
            return
        actor_id, actor_name = self._item_updated_actor(client)
        changed_items: dict[str, WorldItem] = {}
        for item in carried_items:
            item.carrierId = None
            item.locationId = old_location_id
            item.x = old_x
            item.y = old_y
            if self._item_can_sit_on_surface(item):
                item.params = self._normalize_surface_location_params(
                    item, placement="floor"
                )
                item.version += 1
            item.updatedAt = now_ms
            item.updatedBy = actor_id
            item.updatedByName = actor_name
            changed_items[item.id] = item
        for item in await self._auto_place_dropped_items_on_surfaces(
            carried_items,
            now_ms=now_ms,
            actor_id=actor_id,
            actor_name=actor_name,
        ):
            changed_items[item.id] = item
        for item in changed_items.values():
            await self._broadcast_item(item)

    async def _send_piano_status(
        self,
        client: ClientConnection,
        *,
        item_id: str,
        event: Literal[
            "use_mode_entered",
            "record_started",
            "record_paused",
            "record_resumed",
            "record_stopped",
            "playback_started",
            "playback_stopped",
        ],
        recording_state: Literal["idle", "recording", "paused", "playback"]
        | None = None,
    ) -> None:
        """Send structured piano state transitions without relying on status-message text."""

        await self._send(
            client.websocket,
            ItemPianoStatusPacket(
                type="item_piano_status",
                itemId=item_id,
                event=event,
                recordingState=recording_state,
            ),
        )

    async def _broadcast_item(self, item: WorldItem) -> None:
        """Broadcast a full item snapshot update to clients in the item's location."""

        await self._broadcast_location(
            item.locationId,
            ItemUpsertPacket(type="item_upsert", item=self._outbound_item(item))
        )

    @staticmethod
    def _house_object_breaks_when_shoved(item: WorldItem) -> bool:
        """Return whether an object should break after being shoved off a surface."""

        condition = str(item.params.get("condition", "intact")).strip().lower()
        if condition in {"broken", "replacement"}:
            return False
        fragility = str(item.params.get("fragility", "normal")).strip().lower()
        material = str(item.params.get("material", "")).strip().lower()
        if fragility in {"fragile", "delicate"}:
            return True
        if fragility == "sturdy":
            return False
        return material in {"ceramic", "glass", "plant"}

    @staticmethod
    def _surface_placement_value(surface: WorldItem) -> str:
        """Return the house-object placement value for a furniture surface."""

        kind = str(surface.params.get("furnitureKind", "furniture")).strip().lower()
        if kind in {"table", "counter", "shelf"}:
            return kind
        return "furniture"

    def _normalize_house_object_location_params(
        self,
        item: WorldItem,
        *,
        placement: str,
        surface_id: str = "",
        surface_title: str = "",
        surface_order: int = 0,
    ) -> dict:
        """Return normalized params for a house object after pickup/drop/placement."""

        return get_item_type_handler(item.type).validate_update(
            item,
            {
                **item.params,
                "placement": placement,
                "surfaceId": surface_id,
                "surfaceTitle": surface_title,
                "surfaceOrder": surface_order,
            },
        )

    @staticmethod
    def _item_can_sit_on_surface(item: WorldItem) -> bool:
        """Return whether an item may occupy a furniture surface slot."""

        return item.type in {"house_object", "radio_station"}

    def _normalize_surface_location_params(
        self,
        item: WorldItem,
        *,
        placement: str,
        surface_id: str = "",
        surface_title: str = "",
        surface_order: int = 0,
    ) -> dict:
        """Return normalized params for an item after pickup/drop/surface placement."""

        if item.type == "house_object":
            return self._normalize_house_object_location_params(
                item,
                placement=placement,
                surface_id=surface_id,
                surface_title=surface_title,
                surface_order=surface_order,
            )
        return get_item_type_handler(item.type).validate_update(
            item,
            {
                **item.params,
                "surfaceId": surface_id,
                "surfaceTitle": surface_title,
                "surfaceOrder": surface_order,
            },
        )

    def _surface_slot_occupants(
        self, surface: WorldItem, *, excluding_ids: set[str] | None = None
    ) -> list[WorldItem]:
        """Return surface-safe items currently assigned to one furniture surface."""

        excluded = excluding_ids or set()
        occupants = [
            other
            for other in self.items.values()
            if other.id not in excluded
            and self._item_can_sit_on_surface(other)
            and other.locationId == surface.locationId
            and other.params.get("surfaceId") == surface.id
        ]
        return sorted(
            occupants,
            key=lambda other: (
                self._surface_order_value(other),
                other.createdAt,
                other.id,
            ),
        )

    @staticmethod
    def _surface_order_value(item: WorldItem) -> int:
        """Return one bounded surface-order value for sorting placed items."""

        try:
            value = int(item.params.get("surfaceOrder", 0) or 0)
        except (TypeError, ValueError):
            return 0
        return max(0, min(20, value))

    def _next_surface_order(
        self, surface: WorldItem, *, excluding_ids: set[str] | None = None
    ) -> int:
        """Return the next open order value for an item placed on a surface."""

        occupants = self._surface_slot_occupants(surface, excluding_ids=excluding_ids)
        if not occupants:
            return 0
        return min(20, max(self._surface_order_value(occupant) for occupant in occupants) + 1)

    def _normalize_surface_orders(self, surface: WorldItem) -> list[WorldItem]:
        """Compact one surface's occupants into contiguous left-to-right order values."""

        occupants = self._surface_slot_occupants(surface)
        for index, occupant in enumerate(occupants):
            if self._surface_order_value(occupant) == index:
                continue
            occupant.params = get_item_type_handler(occupant.type).validate_update(
                occupant,
                {
                    **occupant.params,
                    "surfaceOrder": index,
                },
            )
        return occupants

    async def _broadcast_surface_order_items(
        self, items: list[WorldItem], *, now_ms: int, actor_id: str, actor_name: str
    ) -> None:
        """Persist and broadcast item snapshots whose surface order changed."""

        for changed in items:
            changed.updatedAt = now_ms
            changed.updatedBy = actor_id
            changed.updatedByName = actor_name
            changed.version += 1
            await self._broadcast_item(changed)

    def _surface_has_open_slot(
        self, surface: WorldItem, *, excluding_ids: set[str] | None = None
    ) -> bool:
        """Return whether a furniture surface has room for another object."""

        if surface.type != "furniture" or not bool(surface.params.get("supportsObjects", True)):
            return False
        slot_count = int(surface.params.get("surfaceSlots", 0) or 0)
        return len(self._surface_slot_occupants(surface, excluding_ids=excluding_ids)) < slot_count

    def _open_surface_at_item_tile(
        self, item: WorldItem, *, excluding_ids: set[str] | None = None
    ) -> WorldItem | None:
        """Find an open furniture surface on the same tile as one item."""

        for candidate in self.items.values():
            if (
                candidate.id == item.id
                or candidate.id in (excluding_ids or set())
                or candidate.locationId != item.locationId
                or candidate.carrierId is not None
                or candidate.x != item.x
                or candidate.y != item.y
                or candidate.type != "furniture"
            ):
                continue
            if self._surface_has_open_slot(candidate, excluding_ids=excluding_ids):
                return candidate
        return None

    async def _auto_place_dropped_items_on_surfaces(
        self,
        dropped_items: list[WorldItem],
        *,
        now_ms: int,
        actor_id: str,
        actor_name: str,
    ) -> list[WorldItem]:
        """Resolve shelf/radio-style drops into physically sensible surface placement."""

        changed: dict[str, WorldItem] = {}
        dropped_ids = {item.id for item in dropped_items}

        for item in dropped_items:
            if (
                item.carrierId is not None
                or not self._item_can_sit_on_surface(item)
                or str(item.params.get("surfaceId", "") or "").strip()
            ):
                continue
            surface = self._open_surface_at_item_tile(item, excluding_ids=dropped_ids)
            if surface is None:
                continue
            item.params = self._normalize_surface_location_params(
                item,
                placement=self._surface_placement_value(surface),
                surface_id=surface.id,
                surface_title=surface.title,
                surface_order=self._next_surface_order(surface, excluding_ids={item.id}),
            )
            item.updatedAt = now_ms
            item.updatedBy = actor_id
            item.updatedByName = actor_name
            item.version += 1
            if self._auto_link_radio_component_to_nearby_group(item):
                item.version += 1
            if await self._sync_dropped_radio_with_playing_group(item):
                item.version += 1
            changed[item.id] = item

        for surface in dropped_items:
            if (
                surface.type != "furniture"
                or surface.carrierId is not None
                or not self._surface_has_open_slot(surface, excluding_ids=dropped_ids)
            ):
                continue
            for item in self.items.values():
                if (
                    item.id in dropped_ids
                    or item.id in changed
                    or item.carrierId is not None
                    or not self._item_can_sit_on_surface(item)
                    or str(item.params.get("surfaceId", "") or "").strip()
                    or item.locationId != surface.locationId
                    or item.x != surface.x
                    or item.y != surface.y
                ):
                    continue
                if not self._surface_has_open_slot(surface, excluding_ids=dropped_ids):
                    break
                item.params = self._normalize_surface_location_params(
                    item,
                    placement=self._surface_placement_value(surface),
                    surface_id=surface.id,
                    surface_title=surface.title,
                    surface_order=self._next_surface_order(surface, excluding_ids=dropped_ids),
                )
                item.updatedAt = now_ms
                item.updatedBy = actor_id
                item.updatedByName = actor_name
                item.version += 1
                if self._auto_link_radio_component_to_nearby_group(item):
                    item.version += 1
                if await self._sync_dropped_radio_with_playing_group(item):
                    item.version += 1
                changed[item.id] = item

        return list(changed.values())

    @staticmethod
    def _house_object_recovery_text(item: WorldItem) -> str:
        """Return repair, purchase, or gift guidance for a damaged object."""

        repair_cost = int(item.params.get("repairCost", 0) or 0)
        purchase_cost = int(item.params.get("purchaseCost", 0) or 0)
        replacement_hint = str(item.params.get("replacementHint", "") or "").strip()
        giftable = bool(item.params.get("giftable", True))
        parts: list[str] = []
        if repair_cost:
            parts.append(f"Repair: {repair_cost} credits.")
        if purchase_cost:
            parts.append(f"Purchase replacement: {purchase_cost} credits.")
        if giftable:
            parts.append("Someone can give the owner something similar.")
        if replacement_hint:
            parts.append(replacement_hint)
        return " ".join(parts)

    async def _handle_item_interact(
        self, client: ClientConnection, packet: ItemInteractPacket
    ) -> None:
        """Handle item-to-item house interactions such as placing and shoving."""

        if not self._client_has_permission(client, "item.use"):
            await self._send_item_result(
                client, False, "interact", "Not authorized to interact with items."
            )
            return
        item = self.items.get(packet.itemId)
        if item is None:
            await self._send_item_result(client, False, "interact", "Item not found.")
            return
        if item.locationId != client.location_id:
            await self._send_item_result(
                client, False, "interact", "Item is in another location.", item.id
            )
            return
        if item.carrierId not in (None, client.id):
            await self._send_item_result(
                client, False, "interact", "Item is not available.", item.id
            )
            return

        now_ms = self.item_service.now_ms()
        actor_id, actor_name = self._item_updated_actor(client)

        if packet.action == "place_on":
            target = self.items.get(packet.targetItemId or "")
            if target is None:
                await self._send_item_result(
                    client, False, "interact", "Surface not found.", item.id
                )
                return
            if not self._item_can_sit_on_surface(item) or target.type != "furniture":
                await self._send_item_result(
                    client,
                    False,
                    "interact",
                    "Only surface-safe items can be placed on furniture.",
                    item.id,
                )
                return
            if item.carrierId != client.id:
                await self._send_item_result(
                    client, False, "interact", f"You are not carrying {item.title}.", item.id
                )
                return
            if target.locationId != client.location_id or target.carrierId is not None:
                await self._send_item_result(
                    client, False, "interact", "That surface is not available.", item.id
                )
                return
            if target.x != client.x or target.y != client.y:
                await self._send_item_result(
                    client, False, "interact", "Surface is not on your square.", item.id
                )
                return
            if not bool(target.params.get("supportsObjects", True)):
                await self._send_item_result(
                    client,
                    False,
                    "interact",
                    f"{target.title} is not a usable surface.",
                    item.id,
                )
                return
            slot_count = int(target.params.get("surfaceSlots", 0) or 0)
            occupied = [
                other
                for other in self.items.values()
                if self._item_can_sit_on_surface(other)
                and other.locationId == target.locationId
                and other.params.get("surfaceId") == target.id
                and other.id != item.id
            ]
            if len(occupied) >= slot_count:
                await self._send_item_result(
                    client,
                    False,
                    "interact",
                    f"{target.title} has no open surface space.",
                    item.id,
                )
                return
            item.carrierId = None
            item.x = target.x
            item.y = target.y
            item.params = self._normalize_surface_location_params(
                item,
                placement=self._surface_placement_value(target),
                surface_id=target.id,
                surface_title=target.title,
                surface_order=self._next_surface_order(target, excluding_ids={item.id}),
            )
            auto_linked = self._auto_link_radio_component_to_nearby_group(item)
            synced_media = await self._sync_dropped_radio_with_playing_group(item)
            item.updatedAt = now_ms
            item.updatedBy = actor_id
            item.updatedByName = actor_name
            item.version += 1
            if auto_linked or synced_media:
                item.version += 1
            self._request_state_save()
            await self._broadcast_item(item)
            await self._broadcast_location(
                item.locationId,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"{client.nickname} places {item.title} on {target.title}.",
                    system=True,
                ),
                exclude=client.websocket,
            )
            await self._send_item_result(
                client,
                True,
                "interact",
                f"You place {item.title} on {target.title}.",
                item.id,
            )
            return

        if packet.action in {"move_surface_left", "move_surface_right"}:
            surface_id = str(item.params.get("surfaceId", "") or "").strip()
            if not surface_id:
                await self._send_item_result(
                    client,
                    False,
                    "interact",
                    f"{item.title} is not sitting on a surface.",
                    item.id,
                )
                return
            surface = self.items.get(surface_id)
            if surface is None or surface.type != "furniture":
                await self._send_item_result(
                    client, False, "interact", "Surface not found.", item.id
                )
                return
            if surface.locationId != client.location_id:
                await self._send_item_result(
                    client, False, "interact", "Surface is in another location.", item.id
                )
                return
            if item.carrierId is not None or surface.carrierId is not None:
                await self._send_item_result(
                    client,
                    False,
                    "interact",
                    "Set the surface down before changing item order.",
                    item.id,
                )
                return
            if (
                surface.x != client.x
                or surface.y != client.y
                or item.x != surface.x
                or item.y != surface.y
            ):
                await self._send_item_result(
                    client,
                    False,
                    "interact",
                    "Surface is not on your square.",
                    item.id,
                )
                return

            occupants = self._normalize_surface_orders(surface)
            current_index = next(
                (index for index, occupant in enumerate(occupants) if occupant.id == item.id),
                -1,
            )
            if current_index < 0:
                await self._send_item_result(
                    client,
                    False,
                    "interact",
                    f"{item.title} is not sitting on {surface.title}.",
                    item.id,
                )
                return

            direction = -1 if packet.action == "move_surface_left" else 1
            next_index = current_index + direction
            edge_label = "left" if direction < 0 else "right"
            if next_index < 0 or next_index >= len(occupants):
                await self._send_item_result(
                    client,
                    True,
                    "interact",
                    f"{item.title} is already at the {edge_label} edge of {surface.title}.",
                    item.id,
                )
                return

            neighbor = occupants[next_index]
            item.params = get_item_type_handler(item.type).validate_update(
                item,
                {
                    **item.params,
                    "surfaceOrder": next_index,
                },
            )
            neighbor.params = get_item_type_handler(neighbor.type).validate_update(
                neighbor,
                {
                    **neighbor.params,
                    "surfaceOrder": current_index,
                },
            )
            await self._broadcast_surface_order_items(
                [item, neighbor],
                now_ms=now_ms,
                actor_id=actor_id,
                actor_name=actor_name,
            )
            self._request_state_save()
            await self._send_item_result(
                client,
                True,
                "interact",
                f"You move {item.title} {edge_label} on {surface.title}.",
                item.id,
            )
            return

        if packet.action == "shove_off":
            if item.type != "house_object":
                await self._send_item_result(
                    client, False, "interact", "Only house objects can be shoved off.", item.id
                )
                return
            if item.carrierId is not None or item.x != client.x or item.y != client.y:
                await self._send_item_result(
                    client, False, "interact", "Object is not on your square.", item.id
                )
                return
            surface_title = str(item.params.get("surfaceTitle", "") or "").strip()
            if not str(item.params.get("surfaceId", "") or "").strip():
                await self._send_item_result(
                    client,
                    False,
                    "interact",
                    f"{item.title} is not sitting on a surface.",
                    item.id,
                )
                return
            next_condition = (
                "broken" if self._house_object_breaks_when_shoved(item) else "scuffed"
            )
            item.params = get_item_type_handler(item.type).validate_update(
                item,
                {
                    **item.params,
                    "surfaceId": "",
                    "surfaceTitle": "",
                    "condition": next_condition,
                },
            )
            item.updatedAt = now_ms
            item.updatedBy = actor_id
            item.updatedByName = actor_name
            item.version += 1
            self._request_state_save()
            await self._broadcast_item(item)
            if next_condition == "broken":
                recovery = self._house_object_recovery_text(item)
                self_message = (
                    f"You shove {item.title} off {surface_title}. It breaks. {recovery}"
                ).strip()
                others_message = (
                    f"{client.nickname} shoves {item.title} off {surface_title}. It breaks."
                )
            else:
                self_message = f"You shove {item.title} off {surface_title}. It lands scuffed, but not broken."
                others_message = f"{client.nickname} shoves {item.title} off {surface_title}."
            await self._broadcast_location(
                item.locationId,
                BroadcastChatMessagePacket(
                    type="chat_message", message=others_message, system=True
                ),
                exclude=client.websocket,
            )
            await self._send_item_result(
                client, True, "interact", self_message, item.id
            )
            return

        if packet.action in {"repair", "replace"}:
            if item.type != "house_object":
                await self._send_item_result(
                    client,
                    False,
                    "interact",
                    "Only house objects can be repaired or replaced.",
                    item.id,
                )
                return
            if item.carrierId is None and (item.x != client.x or item.y != client.y):
                await self._send_item_result(
                    client, False, "interact", "Object is not on your square.", item.id
                )
                return
            next_condition = "repaired" if packet.action == "repair" else "replacement"
            verb = "repair" if packet.action == "repair" else "replace"
            item.params = get_item_type_handler(item.type).validate_update(
                item, {**item.params, "condition": next_condition}
            )
            item.updatedAt = now_ms
            item.updatedBy = actor_id
            item.updatedByName = actor_name
            item.version += 1
            self._request_state_save()
            await self._broadcast_item(item)
            await self._broadcast_location(
                item.locationId,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"{client.nickname} {verb}s {item.title}.",
                    system=True,
                ),
                exclude=client.websocket,
            )
            await self._send_item_result(
                client, True, "interact", f"You {verb} {item.title}.", item.id
            )
            return

        await self._send_item_result(
            client, False, "interact", "Unknown item interaction.", item.id
        )

    async def _ensure_builtin_items_and_broadcast(self) -> list[WorldItem]:
        """Seed any newly shipped built-in items and broadcast them to live clients."""

        added = self.item_service.ensure_builtin_items()
        if not added:
            return []
        self.item_service.save_state()
        LOGGER.info("seeded %d newly available built-in world items", len(added))
        for item in added:
            await self._broadcast_item(item)
        return added

    async def _sync_blind_productions_billboards_once(self) -> list[WorldItem]:
        """Mirror public Blind Productions messages into Chat Grid billboards."""

        try:
            messages = await asyncio.to_thread(fetch_blind_productions_messages)
        except Exception as exc:
            LOGGER.warning("Blind Productions billboard sync failed: %s", exc)
            return []
        changed = upsert_blind_productions_billboards(
            self.item_service.items,
            messages,
            now_ms=self.item_service.now_ms(),
        )
        if not changed:
            return []
        self.item_service.save_state()
        LOGGER.info(
            "synced %d Blind Productions public message billboards", len(changed)
        )
        for item in changed:
            await self._broadcast_item(item)
        return changed

    async def _run_blind_productions_billboard_loop(self) -> None:
        """Periodically refresh public Blind Productions message billboards."""

        while True:
            await self._sync_blind_productions_billboards_once()
            await asyncio.sleep(600)

    async def _sync_world_cup_cafe_once(self) -> list[WorldItem]:
        """Refresh the café board and TV from FIFA's official live-score feed."""

        try:
            status = await asyncio.to_thread(fetch_world_cup_status)
        except Exception as exc:
            LOGGER.warning("FIFA World Cup café sync failed: %s", exc)
            return []
        changed = upsert_world_cup_cafe_status(
            self.item_service.items,
            status,
            now_ms=self.item_service.now_ms(),
        )
        if not changed:
            return []
        self.item_service.save_state()
        LOGGER.info("updated %d FIFA World Cup café items", len(changed))
        for item in changed:
            await self._broadcast_item(item)
        return changed

    async def _run_world_cup_cafe_loop(self) -> None:
        """Refresh live match state often enough for an in-world score board."""

        while True:
            await self._sync_world_cup_cafe_once()
            await asyncio.sleep(30)

    async def start(self) -> None:
        """Start websocket serving and run until cancelled."""

        protocol = "wss" if self._ssl_context else "ws"
        LOGGER.info(
            "starting signaling server on %s://%s:%d", protocol, self.host, self.port
        )
        await self._ensure_builtin_items_and_broadcast()
        await self._repair_community_locations(broadcast=True)
        recovered_items = self.item_service.recover_stale_carried_items()
        if recovered_items:
            self.item_service.save_state()
            LOGGER.info(
                "recovered %d stale carried world items at startup",
                len(recovered_items),
            )
        self._blind_productions_billboard_task = asyncio.create_task(
            self._run_blind_productions_billboard_loop()
        )
        self._world_cup_cafe_task = asyncio.create_task(
            self._run_world_cup_cafe_loop()
        )
        self._community_autofix_task = asyncio.create_task(
            self._run_community_autofix_loop()
        )
        self._house_keeper_task = asyncio.create_task(self._run_house_keeper_loop())
        self._radio_metadata_task = asyncio.create_task(self._run_radio_metadata_loop())
        self._clock_announce_task = asyncio.create_task(
            self._run_clock_top_of_hour_loop()
        )
        self._telepad_drift_task = asyncio.create_task(self._run_telepad_drift_loop())
        self._live_presence_task = asyncio.create_task(self._run_live_presence_loop())
        try:
            async with serve(
                self._handle_client,
                self.host,
                self.port,
                ssl=self._ssl_context,
                max_size=self.max_message_size,
                origins=[Origin(self.host_origin)] if self.host_origin else None,
                process_request=self._process_http_request,
            ):
                await asyncio.Future()
        finally:
            if self._telepad_drift_task is not None:
                self._telepad_drift_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._telepad_drift_task
                self._telepad_drift_task = None
            if self._live_presence_task is not None:
                self._live_presence_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._live_presence_task
                self._live_presence_task = None
            if self._pending_reboot_task is not None:
                self._pending_reboot_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._pending_reboot_task
                self._pending_reboot_task = None
            if self._clock_announce_task is not None:
                self._clock_announce_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._clock_announce_task
                self._clock_announce_task = None
            if self._blind_productions_billboard_task is not None:
                self._blind_productions_billboard_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._blind_productions_billboard_task
                self._blind_productions_billboard_task = None
            if self._world_cup_cafe_task is not None:
                self._world_cup_cafe_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._world_cup_cafe_task
                self._world_cup_cafe_task = None
            if self._radio_metadata_task is not None:
                self._radio_metadata_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._radio_metadata_task
                self._radio_metadata_task = None
            if self._community_autofix_task is not None:
                self._community_autofix_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._community_autofix_task
                self._community_autofix_task = None
            if self._house_keeper_task is not None:
                self._house_keeper_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._house_keeper_task
                self._house_keeper_task = None
            self._flush_state_save()
            self.auth_service.close()

    async def _handle_client(self, websocket: ServerConnection) -> None:
        """Handle one websocket client's connect/message/disconnect lifecycle."""

        client = ClientConnection(websocket=websocket, id=str(uuid.uuid4()))
        LOGGER.info("websocket opened id=%s", client.id)

        try:
            request = getattr(websocket, "request", None)
            request_path = str(getattr(request, "path", "")).split("?", 1)[0]
            if request_path != self.websocket_path:
                await websocket.close()
                return
            cookie_token = self._session_token_from_websocket_cookie(websocket)
            if cookie_token:
                await self._handle_auth_packet(
                    client,
                    AuthResumePacket(type="auth_resume", sessionToken=cookie_token),
                )
            if not client.authenticated:
                await self._send(
                    websocket,
                    AuthRequiredPacket(
                        type="auth_required",
                        message="Authentication required.",
                        authPolicy=self._auth_policy(),
                        gridName=self.grid_name,
                        welcomeMessage=self.welcome_message,
                        releaseVersion=self.release_version or None,
                        expectedClientRevision=self._current_expected_client_revision() or None,
                        serverVersion=self.server_version,
                    ),
                )
            async for raw_message in websocket:
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8", errors="replace")
                await self._handle_message(client, raw_message)
        except ConnectionClosed as exc:
            LOGGER.info(
                "websocket closed id=%s ip=%s code=%s reason=%s",
                client.id,
                self._client_ip(client),
                getattr(exc, "code", None),
                getattr(exc, "reason", "") or "",
            )
        except Exception:
            LOGGER.exception(
                "client message loop error id=%s ip=%s",
                client.id,
                self._client_ip(client),
            )
        finally:
            if websocket in self.clients:
                disconnected = self.clients.pop(websocket)
                self._write_live_presence(force=True)
                self.active_piano_keys_by_client.pop(disconnected.id, None)
                await self._clear_hand_connections(disconnected)
                self._persist_client_position(disconnected, force=True)
                if disconnected.user_id:
                    self._last_position_persist_ms_by_user.pop(
                        disconnected.user_id, None
                    )
                for item_id, session in list(
                    self.piano_recording_state_by_item.items()
                ):
                    if session.get("ownerClientId") != disconnected.id:
                        continue
                    await self._finalize_piano_recording(item_id)
                for item in self.item_service.drop_carried_items_for_disconnect(
                    disconnected
                ):
                    await self._broadcast_item(item)
                room_casts = self._active_media_casts.get(disconnected.location_id, {})
                ended_cast = room_casts.pop(disconnected.id, None)
                if ended_cast is not None:
                    if not room_casts:
                        self._active_media_casts.pop(disconnected.location_id, None)
                    await self._broadcast_location(
                        disconnected.location_id,
                        ended_cast.model_copy(update={"active": False}),
                        exclude=websocket,
                    )
                self._request_state_save()
                LOGGER.info(
                    "client disconnected id=%s nickname=%s total=%d",
                    disconnected.id,
                    disconnected.nickname,
                    len(self.clients),
                )
                await self._broadcast_location(
                    disconnected.location_id,
                    UserLeftPacket(type="user_left", id=disconnected.id),
                    exclude=websocket,
                )
                await self._broadcast_location(
                    disconnected.location_id,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"{disconnected.nickname} has logged out.",
                        system=True,
                    ),
                    exclude=websocket,
                )

    async def _send_welcome(self, client: ClientConnection) -> None:
        """Send initial world snapshot to a newly connected client."""

        await self._ensure_builtin_items_and_broadcast()
        await self._repair_community_locations(broadcast=True)
        await self._resolve_radio_playback_for_welcome(client.location_id)
        users = [
            RemoteUser(
                id=other.id,
                userId=other.user_id,
                nickname=other.nickname,
                locationId=other.location_id,
                x=other.x,
                y=other.y,
                posture=other.posture if other.seated_item_id else "standing",
                seatedItemId=other.seated_item_id,
                seatedOffset=other.seated_offset,
                handHeldById=other.hand_held_by_id,
            )
            for ws, other in self.clients.items()
            if ws is not client.websocket
            and other.location_id == client.location_id
        ]
        location = self._get_world_location(client.location_id)
        packet = WelcomePacket(
            type="welcome",
            id=client.id,
            player=RemoteUser(
                id=client.id,
                userId=client.user_id,
                nickname=client.nickname,
                locationId=client.location_id,
                x=client.x,
                y=client.y,
                posture=client.posture if client.seated_item_id else "standing",
                seatedItemId=client.seated_item_id,
                seatedOffset=client.seated_offset,
                handHeldById=client.hand_held_by_id,
            ),
            users=users,
            items=[
                self._outbound_item(item).model_dump(exclude_none=True)
                for item in self.items.values()
                if item.locationId == client.location_id
            ],
            worldConfig={
                "gridSize": self.grid_size,
                "gridWidth": min(self.grid_size, location.width),
                "gridHeight": min(self.grid_size, location.height),
                "movementTickMs": self.movement_tick_ms,
                "movementMaxStepsPerTick": self.movement_max_steps_per_tick,
                "locationId": client.location_id,
                "locationName": location.name,
                "locationDescription": location.description,
                "locations": self._world_locations_for_client(),
            },
            uiDefinitions=self._build_ui_definitions(client),
            serverInfo={
                "instanceId": self.instance_id,
                "releaseVersion": self.release_version,
                "serverVersion": self.server_version,
                "expectedClientRevision": self._current_expected_client_revision(),
                "gridName": self.grid_name,
                "welcomeMessage": self.welcome_message,
            },
            auth={
                "authenticated": client.authenticated,
                "userId": client.user_id,
                "username": client.username,
                "role": client.role if client.authenticated else None,
                "permissions": self._sorted_permissions(client.permissions),
                "policy": self._auth_policy(),
            },
        )
        await self._send(client.websocket, packet)
        for cast in self._active_media_casts.get(client.location_id, {}).values():
            await self._send(client.websocket, cast)

    async def _send_authenticated_welcome(self, client: ClientConnection) -> None:
        """Prepare authenticated client state and send welcome before world activation."""

        saved_x = getattr(client, "saved_x", None)
        saved_y = getattr(client, "saved_y", None)
        await self._repair_community_locations(broadcast=True)
        client.location_id = self._normalize_world_location_id(
            getattr(client, "saved_location_id", None) or DEFAULT_LOCATION_ID
        )
        location = self._get_world_location(client.location_id)
        if (
            isinstance(saved_x, int)
            and isinstance(saved_y, int)
            and self._is_in_bounds(saved_x, saved_y, client.location_id)
        ):
            client.x = saved_x
            client.y = saved_y
        else:
            client.x = min(max(location.spawn_x, 0), self.grid_size - 1)
            client.y = min(max(location.spawn_y, 0), self.grid_size - 1)
        now_ms = self.item_service.now_ms()
        self._refresh_client_permissions(client)
        if client.user_id:
            self.auth_service.ensure_ecrypto_account(client.user_id)
        client.last_position_update_ms = now_ms
        client.movement_window_index = self._movement_window_index(now_ms)
        client.movement_window_steps_used = 0
        client.world_ready = False
        await self._send_welcome(client)

    async def _activate_authenticated_client(self, client: ClientConnection) -> None:
        """Move a welcomed authenticated client into active world roster."""

        if client.websocket in self.clients:
            client.world_ready = True
            return
        client.world_ready = True
        self.clients[client.websocket] = client
        self._write_live_presence(force=True)
        LOGGER.info(
            "client authenticated id=%s user_id=%s username=%s total=%d",
            client.id,
            client.user_id,
            client.username,
            len(self.clients),
        )
        await self._broadcast_location(
            client.location_id,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=f"{client.nickname} has logged in.",
                system=True,
            ),
            exclude=client.websocket,
        )

    async def _handle_auth_packet(
        self, client: ClientConnection, packet: ClientPacket
    ) -> bool:
        """Handle pre-auth packets; returns True when packet was an auth command."""

        if client.authenticated and isinstance(
            packet,
            (AuthLoginPacket, AuthRegisterPacket, AuthResumePacket, AuthExternalPacket),
        ):
            await self._send(
                client.websocket,
                AuthResultPacket(
                    type="auth_result",
                    ok=False,
                    message="Already authenticated.",
                    authPolicy=self._auth_policy(),
                ),
            )
            return True

        if isinstance(
            packet,
            (AuthLoginPacket, AuthRegisterPacket, AuthResumePacket, AuthExternalPacket),
        ) and self._is_auth_rate_limited(client, packet):
            LOGGER.warning(
                "auth rate limited id=%s ip=%s packet=%s",
                client.id,
                self._client_ip(client),
                packet.type,
            )
            await self._sleep_auth_failure_jitter()
            await self._send(
                client.websocket,
                AuthResultPacket(
                    type="auth_result",
                    ok=False,
                    message="Too many authentication attempts. Try again shortly.",
                    authPolicy=self._auth_policy(),
                ),
            )
            return True

        try:
            if isinstance(packet, AuthRegisterPacket):
                session = await self._run_auth_hash_task(
                    self.auth_service.register,
                    packet.username,
                    packet.password,
                    email=packet.email,
                )
                LOGGER.info(
                    "auth register success id=%s ip=%s username=%s user_id=%s",
                    client.id,
                    self._client_ip(client),
                    session.user.username,
                    session.user.id,
                )
            elif isinstance(packet, AuthLoginPacket):
                session = await self._run_auth_hash_task(
                    self.auth_service.login, packet.username, packet.password
                )
                LOGGER.info(
                    "auth login success id=%s ip=%s username=%s user_id=%s",
                    client.id,
                    self._client_ip(client),
                    session.user.username,
                    session.user.id,
                )
            elif isinstance(packet, AuthResumePacket):
                session = self.auth_service.resume(packet.sessionToken)
                LOGGER.info(
                    "auth resume success id=%s ip=%s username=%s user_id=%s",
                    client.id,
                    self._client_ip(client),
                    session.user.username,
                    session.user.id,
                )
            elif isinstance(packet, AuthExternalPacket):
                session = self.auth_service.login_external_assertion(
                    packet.assertion,
                    signing_secret=self.external_auth_secret,
                    expected_audience="chatgrid",
                )
                LOGGER.info(
                    "auth external success id=%s ip=%s username=%s user_id=%s",
                    client.id,
                    self._client_ip(client),
                    session.user.username,
                    session.user.id,
                )
            elif isinstance(packet, AuthLogoutPacket):
                if client.session_token:
                    self.auth_service.revoke(client.session_token)
                    client.session_token = None
                client.permissions = set()
                LOGGER.info(
                    "auth logout id=%s ip=%s username=%s",
                    client.id,
                    self._client_ip(client),
                    client.username,
                )
                await self._send(
                    client.websocket,
                    AuthResultPacket(
                        type="auth_result",
                        ok=True,
                        message="Logged out.",
                        authPolicy=self._auth_policy(),
                    ),
                )
                await client.websocket.close()
                return True
            else:
                return False
        except AuthError as exc:
            if isinstance(
                packet,
                (
                    AuthLoginPacket,
                    AuthRegisterPacket,
                    AuthResumePacket,
                    AuthExternalPacket,
                ),
            ):
                self._record_auth_failure(client, packet)
                await self._sleep_auth_failure_jitter()
            response_message = str(exc)
            if isinstance(packet, AuthLoginPacket):
                response_message = AUTH_LOGIN_FAILURE_MESSAGE
            elif isinstance(packet, AuthResumePacket):
                response_message = AUTH_RESUME_FAILURE_MESSAGE
            elif isinstance(packet, AuthExternalPacket):
                response_message = AUTH_EXTERNAL_FAILURE_MESSAGE
            LOGGER.warning(
                "auth failure id=%s ip=%s packet=%s reason=%s",
                client.id,
                self._client_ip(client),
                packet.type,
                str(exc),
            )
            await self._send(
                client.websocket,
                AuthResultPacket(
                    type="auth_result",
                    ok=False,
                    message=response_message,
                    authPolicy=self._auth_policy(),
                ),
            )
            return True
        except Exception:
            if isinstance(
                packet,
                (
                    AuthLoginPacket,
                    AuthRegisterPacket,
                    AuthResumePacket,
                    AuthExternalPacket,
                ),
            ):
                self._record_auth_failure(client, packet)
                await self._sleep_auth_failure_jitter()
            LOGGER.exception(
                "auth unexpected error id=%s ip=%s packet=%s",
                client.id,
                self._client_ip(client),
                packet.type,
            )
            await self._send(
                client.websocket,
                AuthResultPacket(
                    type="auth_result",
                    ok=False,
                    message="Authentication failed due to a server error. Please try again.",
                    authPolicy=self._auth_policy(),
                ),
            )
            return True

        if isinstance(
            packet, (AuthLoginPacket, AuthRegisterPacket, AuthResumePacket, AuthExternalPacket)
        ):
            self._clear_auth_failures(client, packet)

        client.authenticated = True
        client.user_id = session.user.id
        client.username = session.user.username
        client.role = session.user.role
        client.permissions = set(session.user.permissions)
        client.session_token = session.token
        client.nickname = session.user.last_nickname or client.nickname
        client.saved_x = session.user.last_x
        client.saved_y = session.user.last_y
        client.saved_location_id = session.user.last_location_id
        await self._send(
            client.websocket,
            AuthResultPacket(
                type="auth_result",
                ok=True,
                message="Authenticated.",
                sessionToken=session.token,
                username=session.user.username,
                role=session.user.role,
                permissions=self._sorted_permissions(session.user.permissions),
                adminMenuActions=self._build_admin_menu_actions_for_client(client),
                nickname=client.nickname,
                authPolicy=self._auth_policy(),
            ),
        )
        await self._send_authenticated_welcome(client)
        return True

    def _build_ui_definitions(self, client: ClientConnection | None = None) -> dict:
        """Build server-owned UI definitions for item/menu rendering."""

        item_types: list[dict] = []
        for item_type in ITEM_TYPE_SEQUENCE:
            editable = list(ITEM_TYPE_EDITABLE_PROPERTIES.get(item_type, ("title",)))
            item_types.append(
                {
                    "type": item_type,
                    "label": ITEM_TYPE_LABELS.get(item_type, item_type),
                    "tooltip": ITEM_TYPE_TOOLTIPS.get(item_type),
                    "capabilities": list(get_item_definition(item_type).capabilities),
                    "editableProperties": editable,
                    "propertyMetadata": ITEM_TYPE_PROPERTY_METADATA.get(item_type, {}),
                    "globalProperties": get_item_global_properties(item_type),
                }
            )
        # Keep this as a menu variant rather than a new persisted runtime
        # type.  It creates a fully configured house-object remote anywhere
        # an admin can add an item, not only in a seeded living room.
        item_types.append(
            {
                "type": "radio_remote",
                "label": "Universal radio remote",
                "tooltip": "Add a universal radio remote here. It can tune nearby and linked radios.",
                "capabilities": ["editable", "carryable", "deletable", "usable"],
                "editableProperties": list(ITEM_TYPE_EDITABLE_PROPERTIES["house_object"]),
                "propertyMetadata": ITEM_TYPE_PROPERTY_METADATA["house_object"],
                "globalProperties": get_item_global_properties("house_object"),
            }
        )
        return {
            "itemTypeOrder": [*ITEM_TYPE_SEQUENCE, "radio_remote"],
            "itemTypes": item_types,
            "commandMetadata": {
                "mainModeActions": list(MAIN_MODE_SERVER_COMMAND_DEFINITIONS)
            },
            "itemManagement": {"actions": list(ITEM_MANAGEMENT_ACTION_DEFINITIONS)},
            "adminMenu": {"actions": self._build_admin_menu_actions_for_client(client)},
        }

    async def _broadcast_wheel_result_after_delay(
        self,
        client: ClientConnection,
        self_message: str,
        others_message: str,
        delay_seconds: float = 3.0,
    ) -> None:
        """Delay then publish wheel result text to self and other users."""

        await asyncio.sleep(delay_seconds)
        await self._broadcast_location(
            client.location_id,
            BroadcastChatMessagePacket(
                type="chat_message", message=others_message, system=True
            ),
            exclude=client.websocket,
        )
        if client.websocket in self.clients:
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message", message=self_message, system=True
                ),
            )

    async def _send_admin_action_result(
        self,
        client: ClientConnection,
        *,
        ok: bool,
        action: AdminActionName,
        message: str,
    ) -> None:
        """Send one structured admin action result packet to caller."""

        await self._send(
            client.websocket,
            AdminActionResultPacket(
                type="admin_action_result", ok=ok, action=action, message=message
            ),
        )

    @staticmethod
    def _format_duration(total_seconds: int) -> str:
        """Format a duration value as compact human-readable text."""

        seconds = max(0, int(total_seconds))
        days, remainder = divmod(seconds, 24 * 60 * 60)
        hours, remainder = divmod(remainder, 60 * 60)
        minutes, secs = divmod(remainder, 60)
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if secs or not parts:
            parts.append(f"{secs}s")
        return " ".join(parts)

    def _format_uptime(self) -> str:
        """Return current server uptime text."""

        elapsed_seconds = int(max(0.0, time.monotonic() - self._started_at_monotonic))
        return self._format_duration(elapsed_seconds)

    async def _run_delayed_reboot(self, requested_by: str, message: str) -> None:
        """Wait for reboot delay, then terminate process for supervisor restart."""

        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            return
        LOGGER.warning(
            "server reboot requested by=%s message=%s", requested_by, message
        )
        os.kill(os.getpid(), signal.SIGTERM)

    def _schedule_reboot(self, requested_by: str, message: str) -> bool:
        """Schedule one delayed reboot; return False when one is already pending."""

        if (
            self._pending_reboot_task is not None
            and not self._pending_reboot_task.done()
        ):
            return False
        self._pending_reboot_task = asyncio.create_task(
            self._run_delayed_reboot(requested_by, message)
        )
        return True

    async def _handle_chat_command(
        self, client: ClientConnection, message: str
    ) -> bool:
        """Handle slash commands in chat input; return True when handled."""

        if not message.startswith("/"):
            return False
        command_line = message[1:]
        command_token, separator, remainder = command_line.partition(" ")
        command = command_token.casefold()
        if command == "me":
            if not separator or remainder == "":
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="Usage: /me <action>",
                        system=True,
                    ),
                )
                return True
            await self._broadcast_location(
                client.location_id,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"{client.nickname} {remainder}",
                    senderId=client.id,
                    senderNickname=client.nickname,
                    system=False,
                    action=True,
                )
            )
            return True
        if command in SOCIAL_ACTION_ALIASES:
            await self._send_social_action_command(
                client, str(SOCIAL_ACTION_ALIASES[command]), remainder.strip()
            )
            return True
        if command in {"ecrypto", "crypto", "wallet"}:
            await self._send_ecrypto_command_result(client, remainder.strip())
            return True
        if command == "knock":
            if client.location_id != RAYWONDER_ENTRY_LOCATION_ID:
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="There is no studio door here to knock on.",
                        system=True,
                    ),
                )
                return True
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message="You knock on the studio door.",
                    system=True,
                ),
            )
            await self._broadcast_location(
                RAYWONDER_STUDIO_LOCATION_ID,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=(
                        f"{client.nickname} knocks on the studio door. "
                        f"Use /allow {client.nickname} to let them in."
                    ),
                    system=True,
                ),
            )
            return True
        if command in {"allow", "letin", "let-in"}:
            requested_name = remainder.strip() if separator else ""
            guarded_matches = self._guarded_entry_matches_for_name(
                client, requested_name
            )
            if guarded_matches:
                alarm, door, waiting = guarded_matches[0]
                self._house_entry_invites[(waiting.id, door.id)] = time.monotonic() + 30.0
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"You approve {waiting.nickname} for this entry.",
                        system=True,
                    ),
                )
                await self._send(
                    waiting.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"{client.nickname} approved your entry. The door will open in ten seconds.",
                        system=True,
                    ),
                )
                asyncio.create_task(
                    self._complete_house_alarm_entry(
                        client=waiting, alarm=alarm, access_result="guest"
                    )
                )
                return True
            if requested_name and any(
                alarm.type == "house_alarm"
                and self._controls_alarm_from_current_house(alarm, client)
                for alarm in self.items.values()
            ):
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="That user is not waiting at a guarded door you control.",
                        system=True,
                    ),
                )
                return True
            if client.location_id != RAYWONDER_STUDIO_LOCATION_ID:
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="You need to be inside the studio to allow someone in.",
                        system=True,
                    ),
                )
                return True
            if not separator or not remainder.strip():
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="Usage: /allow <user>",
                        system=True,
                    ),
                )
                return True
            target = self._find_user_by_name_in_location(
                remainder.strip(), RAYWONDER_ENTRY_LOCATION_ID
            )
            if target is None:
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="That user is not waiting outside the studio door.",
                        system=True,
                    ),
                )
                return True
            self._studio_entry_invites[target.id] = (
                time.monotonic() + STUDIO_ENTRY_INVITE_TTL_S
            )
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"You allow {target.nickname} into the studio.",
                    system=True,
                ),
            )
            await self._send(
                target.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"{client.nickname} allows you into the studio. Use the studio door to enter.",
                    system=True,
                ),
            )
            return True
        if command in {"deny", "keepout", "keep-out"}:
            requested_name = remainder.strip() if separator else ""
            if not requested_name:
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message", message="Usage: /deny <user>", system=True
                    ),
                )
                return True
            for _alarm, door, waiting in self._guarded_entry_matches_for_name(
                client, requested_name
            ):
                self._house_entry_invites.pop((waiting.id, door.id), None)
                await self._send(
                    waiting.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message", message="Entry was denied.", system=True
                    ),
                )
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"You deny entry to {waiting.nickname}.",
                        system=True,
                    ),
                )
                return True
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message", message="That user is not waiting at a guarded door you control.", system=True
                ),
            )
            return True
        if command in {"walkto", "walk-to", "walkup", "walk-up"}:
            await self._move_to_named_user(client, remainder.strip(), exact=False)
            return True
        if command in {"teleportto", "teleport-to", "join", "goto-user"}:
            await self._move_to_named_user(client, remainder.strip(), exact=True)
            return True
        if command == "up":
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"Server uptime: {self._format_uptime()}",
                    system=True,
                ),
            )
            return True
        if command == "version":
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"Server version: {self.server_version}",
                    system=True,
                ),
            )
            return True
        if command in {"go", "travel", "location"}:
            if not separator or not remainder.strip():
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"Usage: /go <location>. Locations: {location_options_text()}",
                        system=True,
                    ),
                )
                return True
            await self._handle_message(
                client,
                ChangeLocationPacket(
                    type="change_location", locationId=remainder.strip()
                ).model_dump_json(),
            )
            return True
        if command == "reboot":
            if not self._client_has_permission(client, "server.allow_reboot"):
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="Not authorized to reboot server.",
                        system=True,
                    ),
                )
                return True
            reboot_message = remainder if separator else ""
            if not self._schedule_reboot(
                client.username or client.nickname, reboot_message
            ):
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="Server reboot already in progress.",
                        system=True,
                    ),
                )
                return True
            announcement = "Server rebooting in 5 seconds."
            if reboot_message:
                announcement = f"{announcement} {reboot_message}"
            await self._broadcast(
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=announcement,
                    system=True,
                )
            )
            return True
        await self._send(
            client.websocket,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=f"Unknown command: /{command_token}",
                system=True,
            ),
        )
        return True

    async def _send_ecrypto_command_result(
        self, client: ClientConnection, command_line: str
    ) -> None:
        """Handle authenticated eCrypto bank commands from chat input."""

        message = self._handle_ecrypto_command(client, command_line)
        await self._send(
            client.websocket,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=message,
                system=True,
            ),
        )

    def _handle_ecrypto_command(self, client: ClientConnection, command_line: str) -> str:
        """Return the user-facing result for one eCrypto command."""

        if not client.authenticated or not client.user_id:
            return "Log in to use eCrypto bank features."
        parts = command_line.split()
        action = parts[0].casefold() if parts else "balance"
        try:
            if action in {"", "balance", "account", "summary"}:
                return self._ecrypto_account_status(client)
            if action in {"help", "?"}:
                return self._ecrypto_help_text()
            if action in {"wallets", "connections", "connected"}:
                return self._ecrypto_wallets_text(client)
            if action in {"inventory", "users", "accounts"}:
                return self._ecrypto_accounts_inventory_text(client)
            if action in {"connect", "wallet", "link"}:
                return self._ecrypto_connect_wallet(client, parts[1:])
            if action in {"connect-source", "link-source", "source"}:
                return self._ecrypto_connect_wallet(client, parts[1:], source_required=True)
            if action in {"faucet", "deposit", "testdeposit", "test-deposit"}:
                amount = self._parse_ecrypto_amount(parts[1] if len(parts) > 1 else "100")
                summary = self.auth_service.ecrypto_test_deposit(
                    client.user_id, amount, memo=f"grid {action}"
                )
                return (
                    f"Test eCrypto deposit complete. Balance: "
                    f"{summary.test_balance} TEST-ECR."
                )
            if action in {"transfer", "send", "pay"}:
                return self._ecrypto_transfer_text(client, parts[1:])
        except AuthError as exc:
            return str(exc)
        return self._ecrypto_help_text()

    @staticmethod
    def _parse_ecrypto_amount(value: str) -> int:
        """Parse a whole-number eCrypto amount from user command text."""

        token = str(value or "").strip().replace(",", "")
        if not re.fullmatch(r"[0-9]+", token):
            raise AuthError("Amount must be a whole number.")
        amount = int(token)
        if amount <= 0:
            raise AuthError("Amount must be positive.")
        return amount

    def _ecrypto_help_text(self) -> str:
        """Return concise command help for eCrypto bank use."""

        return (
            "eCrypto commands: /ecrypto balance, /ecrypto wallets, "
            "/ecrypto connect <test|real> <chain> <address> [label], "
            "/ecrypto connect-source <test|real> <chain> <address> <source> [label], "
            "/ecrypto faucet [amount] for test-chain funds, and "
            "/ecrypto transfer <username> <amount> [memo] for test-chain transfers. "
            "Admins and approved agents can use /ecrypto inventory for safe per-user account counts. "
            "Real-chain wallets are connection records only until an approved chain provider is wired."
        )

    def _ecrypto_bank_use_text(
        self, client: ClientConnection, item: WorldItem
    ) -> str:
        """Return the primary-use bank text for one logged-in user."""

        if item.params.get("enabled") is False:
            return f"{item.title} is closed."
        bank_name = str(item.params.get("bankName") or item.title).strip() or item.title
        if not client.authenticated or not client.user_id:
            return f"{bank_name}. Log in to check and use your eCrypto account."
        target_location = str(item.params.get("targetLocation") or "").strip()
        enter_note = " Secondary use enters the bank lobby." if target_location else ""
        return f"{bank_name}. {self._ecrypto_account_status(client)} Use /ecrypto help for wallet and test-chain actions.{enter_note}"

    def _ecrypto_bank_help_text(
        self, client: ClientConnection, item: WorldItem
    ) -> str:
        """Return secondary-use bank details and command help."""

        bank_name = str(item.params.get("bankName") or item.title).strip() or item.title
        description = str(item.params.get("description") or "").strip()
        access_note = str(item.params.get("accessNote") or "").strip()
        pieces = [f"{bank_name} supports logged-in eCrypto accounts."]
        if description:
            pieces.append(description)
        if access_note:
            pieces.append(access_note)
        if str(item.params.get("targetLocation") or "").strip():
            pieces.append("Entering the bank lobby.")
        pieces.append(self._ecrypto_help_text())
        if client.authenticated and client.user_id:
            pieces.append(self._ecrypto_wallets_text(client))
        return " ".join(pieces)

    def _ecrypto_account_status(self, client: ClientConnection) -> str:
        """Return one authenticated user's eCrypto account status line."""

        if not client.user_id:
            return "Log in to use eCrypto bank features."
        summary = self.auth_service.get_ecrypto_account_summary(client.user_id)
        return (
            f"eCrypto account @{summary.username}: {summary.test_balance} TEST-ECR, "
            f"{summary.wallet_count} connected wallet"
            f"{'' if summary.wallet_count == 1 else 's'} "
            f"({summary.test_wallet_count} test, {summary.real_wallet_count} real), "
            f"{summary.external_identity_count} linked sign-in "
            f"identit{'y' if summary.external_identity_count == 1 else 'ies'}."
        )

    def _ecrypto_wallets_text(self, client: ClientConnection) -> str:
        """Return connected wallet summaries for the current user."""

        if not client.user_id:
            return "Log in to use eCrypto bank features."
        wallets = self.auth_service.list_ecrypto_wallets(client.user_id)
        if not wallets:
            return "No wallets connected. Use /ecrypto connect <test|real> <chain> <address> [label]."
        parts = []
        for wallet in wallets[:10]:
            label = f" {wallet.label}" if wallet.label else ""
            source = f" from {wallet.source_label}" if wallet.source_label else ""
            verified = " verified" if wallet.verified_at_ms else " linked"
            parts.append(
                f"{wallet.network_mode} {wallet.chain}{label}: {wallet.address}{source}{verified}"
            )
        extra = len(wallets) - len(parts)
        suffix = f" Plus {extra} more." if extra > 0 else ""
        return "Connected eCrypto wallets. " + "; ".join(parts) + "." + suffix

    def _ecrypto_connect_wallet(
        self,
        client: ClientConnection,
        args: list[str],
        *,
        source_required: bool = False,
    ) -> str:
        """Connect one test or real blockchain wallet to the current account."""

        if not client.user_id:
            return "Log in to connect wallets."
        minimum_args = 4 if source_required else 3
        if len(args) < minimum_args:
            if source_required:
                return "Usage: /ecrypto connect-source <test|real> <chain> <address> <source> [label]"
            return "Usage: /ecrypto connect <test|real> <chain> <address> [label]"
        network_mode, chain, address = args[0], args[1], args[2]
        source_label = args[3] if source_required else None
        label_args = args[4:] if source_required else args[3:]
        label = " ".join(label_args).strip() or None
        wallet = self.auth_service.connect_ecrypto_wallet(
            client.user_id,
            chain=chain,
            address=address,
            network_mode=network_mode,
            label=label,
            source_label=source_label,
            verified=False,
        )
        source_text = f" from {wallet.source_label}" if wallet.source_label else ""
        if wallet.network_mode == "real":
            return (
                f"Real-chain wallet linked for {wallet.chain}{source_text}: {wallet.address}. "
                "It is stored for account use, but no real-chain transaction will be sent until a provider/signature flow is approved and connected."
            )
        return f"Test-chain wallet linked for {wallet.chain}{source_text}: {wallet.address}."

    def _ecrypto_accounts_inventory_text(self, client: ClientConnection) -> str:
        """Return a safe per-user eCrypto inventory for privileged users."""

        if not client.user_id:
            return "Log in to inspect eCrypto accounts."
        if not (
            self._client_has_permission(client, "server.manage_settings")
            or self._client_has_permission(client, "user.change_role")
        ):
            return "Not authorized to inspect other users' eCrypto account links."
        summaries = self.auth_service.list_ecrypto_account_summaries()
        if not summaries:
            return "No active eCrypto user accounts found."
        parts = []
        for summary in summaries[:20]:
            parts.append(
                f"@{summary.username}: account {summary.account_id}, "
                f"{summary.test_balance} TEST-ECR, {summary.wallet_count} wallets "
                f"({summary.test_wallet_count} test, {summary.real_wallet_count} real), "
                f"{summary.external_identity_count} sign-in links"
            )
        extra = len(summaries) - len(parts)
        suffix = f" Plus {extra} more active account{'s' if extra != 1 else ''}." if extra > 0 else ""
        return "eCrypto user inventory. " + "; ".join(parts) + "." + suffix

    def _ecrypto_transfer_text(
        self, client: ClientConnection, args: list[str]
    ) -> str:
        """Transfer internal test-chain eCrypto to another Chat Grid account."""

        if not client.user_id:
            return "Log in to transfer eCrypto."
        if len(args) < 2:
            return "Usage: /ecrypto transfer <username> <amount> [memo]"
        target_user_id = self.auth_service.get_user_id_by_username(args[0])
        if target_user_id is None:
            return "Target user not found."
        amount = self._parse_ecrypto_amount(args[1])
        memo = " ".join(args[2:]).strip()
        sender, recipient = self.auth_service.ecrypto_test_transfer(
            client.user_id, target_user_id, amount, memo=memo
        )
        return (
            f"Sent {amount} TEST-ECR to @{recipient.username}. "
            f"Your test balance is {sender.test_balance} TEST-ECR."
        )

    def _find_location_user_by_name(
        self, client: ClientConnection, target_name: str
    ) -> ClientConnection | None:
        """Find one visible same-location client by nickname or username."""

        return self._find_user_by_name_in_location(target_name, client.location_id, client)

    def _find_user_by_name_in_location(
        self,
        target_name: str,
        location_id: str,
        self_client: ClientConnection | None = None,
    ) -> ClientConnection | None:
        """Find one client by nickname or username inside a specific location."""

        needle = target_name.strip().casefold()
        if needle in {"", "me", "self", "myself"}:
            return self_client
        matches: list[ClientConnection] = []
        for candidate in self.clients.values():
            if candidate.location_id != location_id:
                continue
            names = [
                candidate.nickname,
                candidate.username or "",
            ]
            normalized = [name.strip().casefold() for name in names if name.strip()]
            if needle in normalized:
                return candidate
            if any(needle in name for name in normalized):
                matches.append(candidate)
        if len(matches) == 1:
            return matches[0]
        return None

    async def _send_social_action_command(
        self, client: ClientConnection, action_id: str, target_name: str
    ) -> None:
        """Broadcast a structured social action with a spatial cue."""

        definition = SOCIAL_ACTIONS[action_id]
        target = self._find_location_user_by_name(client, target_name)
        requires_target = bool(definition.get("requires_target", False))
        if requires_target and not target:
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"Usage: /{action_id} <user>",
                    system=True,
                ),
            )
            return
        target = target or client
        is_self = target.id == client.id
        template_key = "self_template" if is_self else "template"
        template = str(definition.get(template_key) or definition.get("template"))
        message = template.format(actor=client.nickname, target=target.nickname)
        await self._broadcast_location(
            client.location_id,
            SocialActionPacket(
                type="social_action",
                actionId=action_id,
                actorId=client.id,
                actorNickname=client.nickname,
                targetId=target.id,
                targetNickname=target.nickname,
                message=message,
                sound=str(definition.get("sound") or ""),
                x=target.x,
                y=target.y,
                range=12,
            ),
        )

    def _find_location_user_by_client_id(
        self, client: ClientConnection, target_id: str
    ) -> ClientConnection | None:
        """Find one visible same-location client by websocket client id."""

        clean_id = target_id.strip()
        for target in self.clients.values():
            if target.id != clean_id:
                continue
            if target.location_id != client.location_id or target.id == client.id:
                return None
            return target
        return None

    async def _handle_user_action(
        self, client: ClientConnection, packet: UserActionPacket
    ) -> None:
        """Validate and broadcast a contextual user-to-user action."""

        target = self._find_location_user_by_client_id(client, packet.targetId)
        if target is None:
            await self._send(
                client.websocket,
                UserActionResultPacket(
                    type="user_action_result",
                    ok=False,
                    actionId=packet.actionId,
                    targetId=packet.targetId,
                    message="That user is no longer nearby.",
                ),
            )
            return

        if packet.actionId in {"take_left_hand", "take_right_hand"}:
            if target.hand_held_by_id and target.hand_held_by_id != client.id:
                holder = self._find_location_user_by_client_id(
                    target, target.hand_held_by_id
                )
                holder_name = holder.nickname if holder is not None else "someone else"
                await self._send(
                    client.websocket,
                    UserActionResultPacket(
                        type="user_action_result",
                        ok=False,
                        actionId=packet.actionId,
                        targetId=target.id,
                        message=f"{target.nickname}'s hand is already held by {holder_name}.",
                    ),
                )
                return
            target.hand_held_by_id = client.id
            await self._sync_client_position(target)
        elif packet.actionId == "release_hand":
            if client.hand_held_by_id != target.id:
                await self._send(
                    client.websocket,
                    UserActionResultPacket(
                        type="user_action_result",
                        ok=False,
                        actionId=packet.actionId,
                        targetId=target.id,
                        message=f"{target.nickname} is not holding your hand.",
                    ),
                )
                return
            client.hand_held_by_id = None
            await self._sync_client_position(client)

        action_messages = {
            "hug": (
                f"{client.nickname} hugs {target.nickname}.",
                "/sounds/reactions/hug.mp3",
            ),
            "cuddle": (
                f"{client.nickname} cuddles close with {target.nickname}.",
                "/sounds/reactions/hug.mp3",
            ),
            "kiss": (
                f"{client.nickname} gives {target.nickname} an affectionate kiss.",
                "/sounds/reactions/hug.mp3",
            ),
            "tap_shoulder": (
                f"{client.nickname} taps {target.nickname} on the shoulder.",
                "/sounds/reactions/tap.mp3",
            ),
            "announce_focus": (
                f"{client.nickname} is focusing on {target.nickname}.",
                "/sounds/reactions/user.mp3",
            ),
            "wave": (
                f"{client.nickname} waves to {target.nickname}.",
                "/sounds/reactions/wave_hi.mp3",
            ),
            "high_five": (
                f"{client.nickname} high-fives {target.nickname}.",
                "/sounds/reactions/tap.mp3",
            ),
            "fist_bump": (
                f"{client.nickname} fist-bumps {target.nickname}.",
                "/sounds/reactions/tap.mp3",
            ),
            "handshake": (
                f"{client.nickname} offers {target.nickname} a friendly handshake.",
                "/sounds/reactions/tap.mp3",
            ),
            "hold_hands": (
                f"{client.nickname} offers to hold {target.nickname}'s hand.",
                "/sounds/reactions/user.mp3",
            ),
            "cheer": (
                f"{client.nickname} cheers for {target.nickname}.",
                "/sounds/reactions/wave_hi.mp3",
            ),
            "clap": (
                f"{client.nickname} applauds {target.nickname}.",
                "/sounds/reactions/tap.mp3",
            ),
            "laugh": (
                f"{client.nickname} laughs with {target.nickname}.",
                "/sounds/reactions/chat.mp3",
            ),
            "smile": (
                f"{client.nickname} smiles at {target.nickname}.",
                "/sounds/reactions/self.mp3",
            ),
            "wink": (
                f"{client.nickname} winks at {target.nickname}.",
                "/sounds/reactions/self.mp3",
            ),
            "nod": (
                f"{client.nickname} nods to {target.nickname}.",
                "/sounds/reactions/user.mp3",
            ),
            "shake_head": (
                f"{client.nickname} shakes her head at {target.nickname}.",
                "/sounds/reactions/user.mp3",
            ),
            "bow": (
                f"{client.nickname} bows to {target.nickname}.",
                "/sounds/reactions/self.mp3",
            ),
            "dance": (
                f"{client.nickname} dances near {target.nickname}.",
                "/sounds/reactions/wave_hi.mp3",
            ),
            "blush": (
                f"{client.nickname} blushes at {target.nickname}.",
                "/sounds/reactions/self.mp3",
            ),
            "cry": (
                f"{client.nickname} cries softly near {target.nickname}.",
                "/sounds/reactions/comfort.mp3",
            ),
            "yawn": (
                f"{client.nickname} yawns near {target.nickname}.",
                "/sounds/reactions/sigh.mp3",
            ),
            "apologize": (
                f"{client.nickname} apologizes to {target.nickname}.",
                "/sounds/reactions/self.mp3",
            ),
            "forgive": (
                f"{client.nickname} forgives {target.nickname}.",
                "/sounds/reactions/heart.mp3",
            ),
            "spin": (
                f"{client.nickname} spins around near {target.nickname}.",
                "/sounds/reactions/wave_hi.mp3",
            ),
            "jump": (
                f"{client.nickname} jumps excitedly near {target.nickname}.",
                "/sounds/reactions/wave_hi.mp3",
            ),
            "shrug": (
                f"{client.nickname} shrugs at {target.nickname}.",
                "/sounds/reactions/self.mp3",
            ),
            "facepalm": (
                f"{client.nickname} facepalms near {target.nickname}.",
                "/sounds/reactions/self.mp3",
            ),
            "gasp": (
                f"{client.nickname} gasps near {target.nickname}.",
                "/sounds/reactions/chat.mp3",
            ),
            "sigh": (
                f"{client.nickname} sighs near {target.nickname}.",
                "/sounds/reactions/self.mp3",
            ),
            "comfort": (
                f"{client.nickname} offers comfort to {target.nickname}.",
                "/sounds/reactions/hug.mp3",
            ),
            "pat_back": (
                f"{client.nickname} pats {target.nickname} on the back.",
                "/sounds/reactions/tap.mp3",
            ),
            "poke": (
                f"{client.nickname} pokes {target.nickname}.",
                "/sounds/reactions/tap.mp3",
            ),
            "boop": (
                f"{client.nickname} boops {target.nickname}.",
                "/sounds/reactions/tap.mp3",
            ),
            "salute": (
                f"{client.nickname} salutes {target.nickname}.",
                "/sounds/reactions/user.mp3",
            ),
            "point": (
                f"{client.nickname} points toward {target.nickname}.",
                "/sounds/reactions/user.mp3",
            ),
            "thumbs_up": (
                f"{client.nickname} gives {target.nickname} a thumbs-up.",
                "/sounds/reactions/user.mp3",
            ),
            "heart": (
                f"{client.nickname} sends {target.nickname} a heart.",
                "/sounds/reactions/hug.mp3",
            ),
            "sparkle": (
                f"{client.nickname} sparkles at {target.nickname}.",
                "/sounds/reactions/wave_hi.mp3",
            ),
            "celebrate": (
                f"{client.nickname} celebrates with {target.nickname}.",
                "/sounds/reactions/wave_hi.mp3",
            ),
            "tease": (
                f"{client.nickname} teases {target.nickname} playfully.",
                "/sounds/reactions/chat.mp3",
            ),
            "playful_smack": (
                f"{client.nickname} gives {target.nickname} a playful smack.",
                "/sounds/reactions/tap.mp3",
            ),
            "whisper": (
                f"{client.nickname} leans in to whisper to {target.nickname}.",
                "/sounds/reactions/chat.mp3",
            ),
            "listen": (
                f"{client.nickname} listens closely to {target.nickname}.",
                "/sounds/reactions/user.mp3",
            ),
            "sit_with": (
                f"{client.nickname} sits with {target.nickname}.",
                "/sounds/reactions/self.mp3",
            ),
            "step_back": (
                f"{client.nickname} gives {target.nickname} some space.",
                "/sounds/reactions/self.mp3",
            ),
            "take_left_hand": (
                f"{client.nickname} offers {target.nickname} a left hand. {target.nickname} may choose to go along or release.",
                "/sounds/reactions/user.mp3",
            ),
            "take_right_hand": (
                f"{client.nickname} offers {target.nickname} a right hand. {target.nickname} may choose to go along or release.",
                "/sounds/reactions/user.mp3",
            ),
            "release_hand": (
                f"{client.nickname} releases {target.nickname}'s hand.",
                "/sounds/reactions/self.mp3",
            ),
        }
        if packet.actionId in action_messages and packet.actionId not in {
            "walk_to",
            "teleport_to",
        }:
            action_messages[packet.actionId] = (
                action_messages[packet.actionId][0],
                _reaction_sound(packet.actionId),
            )
        message, sound = action_messages[packet.actionId]
        await self._broadcast_location(
            client.location_id,
            SocialActionPacket(
                type="social_action",
                actionId=packet.actionId,
                actorId=client.id,
                actorNickname=client.nickname,
                targetId=target.id,
                targetNickname=target.nickname,
                message=message,
                sound=sound,
                x=target.x,
                y=target.y,
                range=12,
            ),
        )
        await self._send(
            client.websocket,
            UserActionResultPacket(
                type="user_action_result",
                ok=True,
                actionId=packet.actionId,
                targetId=target.id,
                message=message,
            ),
        )

    def _adjacent_square_near_user(
        self, actor: ClientConnection, target: ClientConnection
    ) -> tuple[int, int]:
        """Choose an in-bounds square next to target, biased toward actor."""

        options = [
            (target.x - 1, target.y),
            (target.x + 1, target.y),
            (target.x, target.y - 1),
            (target.x, target.y + 1),
            (target.x - 1, target.y - 1),
            (target.x + 1, target.y + 1),
            (target.x - 1, target.y + 1),
            (target.x + 1, target.y - 1),
        ]
        in_bounds = [(x, y) for x, y in options if self._is_in_bounds(x, y)]
        if not in_bounds:
            return target.x, target.y
        return min(in_bounds, key=lambda xy: (xy[0] - actor.x) ** 2 + (xy[1] - actor.y) ** 2)

    def _path_to_square(
        self, start_x: int, start_y: int, target_x: int, target_y: int
    ) -> list[tuple[int, int]]:
        """Build a step-by-step Chebyshev path between two grid squares."""

        path: list[tuple[int, int]] = []
        x = start_x
        y = start_y
        guard = self.grid_size * 2
        while (x, y) != (target_x, target_y) and guard > 0:
            guard -= 1
            x += 1 if target_x > x else -1 if target_x < x else 0
            y += 1 if target_y > y else -1 if target_y < y else 0
            if not self._is_in_bounds(x, y):
                break
            path.append((x, y))
        return path

    def _position_packet_for(self, client: ClientConnection) -> BroadcastPositionPacket:
        """Build one authoritative presence/position packet for a client."""

        return BroadcastPositionPacket(
            type="update_position",
            id=client.id,
            locationId=client.location_id,
            x=client.x,
            y=client.y,
            posture=client.posture if client.seated_item_id else "standing",
            seatedItemId=client.seated_item_id,
            seatedOffset=client.seated_offset,
            handHeldById=client.hand_held_by_id,
        )

    @staticmethod
    def _is_seatable_item(item: WorldItem) -> bool:
        """Return whether one item can currently seat a person."""

        kind = str(
            item.params.get("furnitureKind")
            or item.params.get("objectKind")
            or item.type
        ).strip().lower()
        posture = str(item.params.get("postureMode", "")).strip().lower()
        return posture in {"sit", "lie", "sit_lie"} or kind in {"chair", "couch", "sofa", "bench", "stool", "loveseat", "bed"}

    @staticmethod
    def _seating_capacity(item: WorldItem) -> int:
        """Resolve the seating capacity for seatable furniture and couch objects."""

        raw_capacity = item.params.get("seatingCapacity")
        if raw_capacity is not None:
            try:
                return max(0, min(6, int(raw_capacity)))
            except (TypeError, ValueError):
                return 0
        kind = str(
            item.params.get("furnitureKind")
            or item.params.get("objectKind")
            or item.type
        ).strip().lower()
        if kind == "bed":
            return 2
        if kind in {"couch", "sofa"}:
            return 4
        if kind in {"bench", "loveseat"}:
            return 3
        if kind in {"chair", "stool"}:
            return 1
        return 0

    def _seated_clients_for_item(self, item_id: str) -> list[ClientConnection]:
        """Return connected clients currently seated on an item."""

        return [client for client in self.clients.values() if client.seated_item_id == item_id]

    def _seat_offset_for_index(self, index: int, capacity: int) -> float:
        """Resolve a small horizontal seat offset for rendering/spatial audio."""

        if capacity <= 1:
            return 0.0
        step = min(0.38, 1.4 / max(1, capacity - 1))
        return (index - (capacity - 1) / 2) * step

    async def _sync_client_position(self, client: ClientConnection, *, exclude_self: bool = False) -> None:
        """Send one client's current position/posture to self and same-location peers."""

        packet = self._position_packet_for(client)
        if not exclude_self:
            await self._send(client.websocket, packet)
        await self._broadcast_location(client.location_id, packet, exclude=client.websocket)

    async def _clear_hand_connections(self, client: ClientConnection) -> None:
        """Release hand state involving one client and sync affected live users."""

        changed: list[ClientConnection] = []
        if client.hand_held_by_id is not None:
            client.hand_held_by_id = None
            changed.append(client)
        for other in self.clients.values():
            if other.id == client.id:
                continue
            if other.hand_held_by_id != client.id:
                continue
            other.hand_held_by_id = None
            changed.append(other)
        for changed_client in changed:
            if changed_client.websocket in self.clients:
                await self._sync_client_position(changed_client)

    async def _stand_client_from_furniture(
        self, client: ClientConnection, item: WorldItem | None = None
    ) -> bool:
        """Stand a seated client up and broadcast the posture change."""

        if not client.seated_item_id:
            return False
        label = item.title if item is not None else "the furniture"
        client.seated_item_id = None
        client.seated_offset = 0.0
        client.posture = "standing"
        await self._sync_client_position(client)
        await self._broadcast_location(
            client.location_id,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=f"{client.nickname} gets up from {label}.",
                system=True,
            ),
            exclude=client.websocket,
        )
        await self._send_item_result(
            client, True, "use", f"You get up from {label}.", item.id if item else None
        )
        return True

    async def _sit_client_on_furniture(
        self,
        client: ClientConnection,
        item: WorldItem,
        *,
        automatic: bool = False,
        posture: str = "sitting",
    ) -> bool:
        """Place a client on an available furniture item when capacity allows."""

        if not self._is_seatable_item(item):
            return False
        capacity = self._seating_capacity(item)
        if capacity <= 0:
            await self._send_item_result(
                client, False, "use", f"{item.title} is not available for sitting.", item.id
            )
            return True
        occupants = [
            occupant
            for occupant in self._seated_clients_for_item(item.id)
            if occupant.id != client.id
        ]
        if len(occupants) >= capacity:
            await self._send_item_result(
                client, False, "use", f"{item.title} is full.", item.id
            )
            return True
        client.x = item.x
        client.y = item.y
        client.posture = "lying" if posture == "lying" else "sitting"
        client.seated_item_id = item.id
        client.seated_offset = self._seat_offset_for_index(len(occupants), capacity)
        now_ms = self.item_service.now_ms()
        client.last_position_update_ms = now_ms
        client.movement_window_index = self._movement_window_index(now_ms)
        client.movement_window_steps_used = 0
        self._persist_client_position(client)
        await self._sync_client_position(client)
        if client.posture == "lying":
            verb = "lies down on"
        else:
            verb = "gently settles onto" if automatic else "sits on"
        await self._broadcast_location(
            item.locationId,
            BroadcastChatMessagePacket(
                type="chat_message",
                message=f"{client.nickname} {verb} {item.title}.",
                system=True,
            ),
            exclude=client.websocket,
        )
        self_message = (
            f"You gently fall into a relaxed sitting position on {item.title}."
            if automatic
            else f"You lie down on {item.title}."
            if client.posture == "lying"
            else f"You sit on {item.title}."
        )
        await self._send_item_result(client, True, "use", self_message, item.id)
        return True

    @staticmethod
    def _posture_mode_for_item(item: WorldItem) -> str:
        """Resolve the supported posture mode for one furniture-like item."""

        posture = str(item.params.get("postureMode", "")).strip().lower()
        if posture in {"sit", "lie", "sit_lie"}:
            return posture
        kind = str(
            item.params.get("furnitureKind")
            or item.params.get("objectKind")
            or item.type
        ).strip().lower()
        if kind == "bed":
            return "sit_lie"
        return "sit"

    async def _handle_furniture_posture_use(
        self, client: ClientConnection, item: WorldItem, *, automatic: bool = False
    ) -> bool:
        """Toggle or enter furniture posture for seatable items."""

        posture_mode = self._posture_mode_for_item(item)
        if client.seated_item_id == item.id:
            if posture_mode == "sit_lie" and client.posture == "sitting":
                client.posture = "lying"
                await self._sync_client_position(client)
                await self._broadcast_location(
                    item.locationId,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"{client.nickname} lies down on {item.title}.",
                        system=True,
                    ),
                    exclude=client.websocket,
                )
                await self._send_item_result(
                    client, True, "use", f"You lie down on {item.title}.", item.id
                )
                return True
            return await self._stand_client_from_furniture(client, item)
        if client.seated_item_id:
            await self._send_item_result(
                client, False, "use", "Stand up before moving to another seat.", item.id
            )
            return True
        if not self._is_seatable_item(item):
            return False
        distance = max(abs(item.x - client.x), abs(item.y - client.y))
        if distance > 1:
            await self._send_item_result(
                client, False, "use", f"Move closer to {item.title} before sitting.", item.id
            )
            return True
        next_posture = "lying" if posture_mode == "lie" else "sitting"
        return await self._sit_client_on_furniture(
            client, item, automatic=automatic, posture=next_posture
        )

    async def _move_to_named_user(
        self, client: ClientConnection, target_name: str, exact: bool
    ) -> None:
        """Move a client to or near a named same-location user."""

        target = self._find_location_user_by_name(client, target_name)
        if not target or target.id == client.id:
            command = "teleportto" if exact else "walkto"
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"Usage: /{command} <user>",
                    system=True,
                ),
            )
            return
        next_x, next_y = (target.x, target.y) if exact else self._adjacent_square_near_user(client, target)
        now_ms = self.item_service.now_ms()
        path = [(next_x, next_y)] if exact else self._path_to_square(client.x, client.y, next_x, next_y)
        if not path:
            path = [(next_x, next_y)]
        for step_x, step_y in path:
            old_x = client.x
            old_y = client.y
            client.x = step_x
            client.y = step_y
            client.seated_item_id = None
            client.seated_offset = 0.0
            client.posture = "standing"
            client.last_position_update_ms = now_ms
            self._persist_client_position(client, force=True)
            position_packet = self._position_packet_for(client)
            await self._send(client.websocket, position_packet)
            await self._broadcast_location(client.location_id, position_packet, exclude=client.websocket)
            await self._update_carried_items_after_client_move(
                client, old_x=old_x, old_y=old_y, now_ms=now_ms
            )
        action_id = "teleportto" if exact else "walkto"
        sound = "/sounds/teleport.ogg" if exact else "/sounds/reactions/walk_to.mp3"
        message = (
            f"{client.nickname} teleports to {target.nickname}."
            if exact
            else f"{client.nickname} walks up to {target.nickname}."
        )
        await self._broadcast_location(
            client.location_id,
            SocialActionPacket(
                type="social_action",
                actionId=action_id,
                actorId=client.id,
                actorNickname=client.nickname,
                targetId=target.id,
                targetNickname=target.nickname,
                message=message,
                sound=sound,
                x=client.x,
                y=client.y,
                range=12,
            ),
        )
        if exact:
            await self._broadcast_location(
                client.location_id,
                BroadcastTeleportCompletePacket(
                    type="teleport_complete",
                    id=client.id,
                    x=client.x,
                    y=client.y,
                ),
                exclude=client.websocket,
            )

    async def _handle_admin_packet(
        self, client: ClientConnection, packet: ClientPacket
    ) -> bool:
        """Handle role/user administration packets with permission checks."""

        if not isinstance(
            packet,
            (
                NtfyPreferencesGetPacket,
                NtfyPreferencesUpdatePacket,
                AdminRolesListPacket,
                AdminRoleCreatePacket,
                AdminRoleUpdatePermissionsPacket,
                AdminRoleDeletePacket,
                AdminUsersListPacket,
                AdminPlatformOverviewPacket,
                AdminNotificationsListPacket,
                AdminNotificationMarkReadPacket,
                AdminBlindSoftwareSyncPacket,
                AdminAmbienceCatalogPacket,
                AdminLocationAmbienceSetPacket,
                AdminUserSetRolePacket,
                AdminUserBanPacket,
                AdminUserUnbanPacket,
                AdminUserDeletePacket,
            ),
        ):
            return False

        async def deny(action: AdminActionName, message: str) -> None:
            await self._send_admin_action_result(
                client, ok=False, action=action, message=message
            )

        if isinstance(packet, (AdminAmbienceCatalogPacket, AdminLocationAmbienceSetPacket)):
            if not self._client_has_permission(client, "server.manage_settings"):
                await deny("location_ambience_set", "Not authorized.")
                return True
            catalog_path = Path(__file__).resolve().parents[1] / "config" / "ambience_catalog.json"
            try:
                catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
                catalog_sounds = [AdminAmbienceSoundSummary.model_validate(entry) for entry in catalog_data["sounds"]]
            except (OSError, KeyError, TypeError, ValueError) as exc:
                LOGGER.error("Unable to load ambience catalog: %s", exc)
                await deny("location_ambience_set", "The ambience catalog could not be loaded.")
                return True
            sounds_by_id = {entry.id: entry for entry in catalog_sounds}
            if isinstance(packet, AdminAmbienceCatalogPacket):
                locations = []
                for location in WORLD_LOCATIONS:
                    item = self.item_service.items.get(f"seed-location-ambience-{location.id}")
                    sound_id = str(item.params.get("ambienceSoundId") or "") if item else ""
                    locations.append(AdminAmbienceLocationSummary(
                        id=location.id,
                        name=location.name,
                        currentSoundId=sound_id,
                        currentSoundLabel=(sounds_by_id[sound_id].label if sound_id in sounds_by_id else ""),
                    ))
                await self._send(client.websocket, AdminAmbienceCatalogResultPacket(
                    type="admin_ambience_catalog", locations=locations, sounds=catalog_sounds
                ))
                return True
            if packet.locationId not in WORLD_LOCATION_BY_ID:
                await deny("location_ambience_set", "Unknown world location.")
                return True
            sound = sounds_by_id.get(packet.soundId)
            if sound is None:
                await deny("location_ambience_set", "Unknown ambience sound.")
                return True
            item = self.item_service.items.get(f"seed-location-ambience-{packet.locationId}")
            if item is None:
                await deny("location_ambience_set", "That location ambience control is unavailable.")
                return True
            item.params.update({
                "enabled": True,
                "emitSound": sound.url,
                "emitVolume": 50,
                "ambienceScope": "location",
                "ambienceName": sound.label,
                "ambiencePriority": 100,
                "ambienceSoundId": sound.id,
                "ambienceLoopStartSeconds": sound.loopStartSeconds,
                "ambienceLoopEndSeconds": sound.loopEndSeconds,
            })
            item.emitSound = sound.url
            item.updatedBy = client.user_id or "admin"
            item.updatedByName = client.nickname
            item.updatedAt = int(time.time() * 1000)
            item.version += 1
            self._request_state_save()
            await self._broadcast_item(item)
            await self._send_admin_action_result(
                client, ok=True, action="location_ambience_set",
                message=f"{WORLD_LOCATION_BY_ID[packet.locationId].name} now uses {sound.label}.",
            )
            return True

        if isinstance(packet, (NtfyPreferencesGetPacket, NtfyPreferencesUpdatePacket)):
            if not client.user_id:
                return True
            if isinstance(packet, NtfyPreferencesUpdatePacket):
                preferences = self.auth_service.update_ntfy_preferences(
                    client.user_id,
                    enabled=packet.enabled,
                    rotate_topic=packet.rotateTopic,
                )
                result_message = "ntfy notification settings saved."
            else:
                preferences = self.auth_service.get_ntfy_preferences(client.user_id)
                result_message = ""
            topic = str(preferences["topic"])
            base_url = self.ntfy_publisher.base_url
            await self._send(
                client.websocket,
                NtfyPreferencesResultPacket(
                    type="ntfy_preferences",
                    enabled=bool(preferences["enabled"]),
                    configured=self.ntfy_publisher.configured,
                    topic=topic,
                    subscriptionUrl=f"{base_url}/{topic}" if base_url and topic else "",
                    message=result_message,
                ),
            )
            return True

        if isinstance(packet, AdminRolesListPacket):
            if not (
                self._client_has_permission(client, "role.manage")
                or self._client_has_permission(client, "user.change_role")
            ):
                await deny("role_update_permissions", "Not authorized.")
                return True
            roles = [
                AdminRoleSummary.model_validate(role)
                for role in self.auth_service.list_roles_with_counts()
            ]
            await self._send(
                client.websocket,
                AdminRolesListResultPacket(
                    type="admin_roles_list",
                    roles=roles,
                    permissionKeys=self.auth_service.list_all_permissions(),
                    permissionTooltips=self.auth_service.list_all_permission_descriptions(),
                ),
            )
            return True

        if isinstance(packet, AdminUsersListPacket):
            if not (
                self._client_has_permission(client, "user.change_role")
                or self._client_has_permission(client, "user.ban_unban")
                or self._client_has_permission(client, "account.delete.any")
            ):
                await deny("user_set_role", "Not authorized.")
                return True
            users = self.auth_service.list_users_for_admin()
            if packet.action == "ban":
                users = [
                    entry for entry in users if str(entry.get("status")) == "active"
                ]
            elif packet.action == "unban":
                users = [
                    entry for entry in users if str(entry.get("status")) == "disabled"
                ]
            user_summaries = [AdminUserSummary.model_validate(entry) for entry in users]
            await self._send(
                client.websocket,
                AdminUsersListResultPacket(
                    type="admin_users_list", users=user_summaries
                ),
            )
            return True

        if isinstance(packet, AdminPlatformOverviewPacket):
            if packet.scope == "platform" and not self._client_has_permission(
                client, "server.manage_settings"
            ):
                await deny("platform_overview", "Not authorized.")
                return True
            if packet.scope == "owned_content" and not (
                client.authenticated and client.user_id
            ):
                await deny("platform_overview", "Sign in to monitor owned content.")
                return True
            all_items = list(self.item_service.items.values())
            service_items = [item for item in all_items if item.type == "service_link"]
            owned_items = [
                item for item in all_items if client.user_id and item.createdBy == client.user_id
            ]
            summary_items = service_items if packet.scope == "platform" else owned_items
            links = [
                AdminPlatformLinkSummary(
                    itemId=item.id,
                    title=item.title,
                    kind=str(
                        item.params.get("serviceKind", item.type)
                        if item.type == "service_link"
                        else item.type
                    ),
                    locationId=item.locationId,
                    x=item.x,
                    y=item.y,
                    url=str(item.params.get("url") or "") or None,
                    author=str(item.params.get("softwareAuthor") or "") or None,
                    verificationStatus=str(
                        item.params.get("verificationStatus") or ""
                    )
                    or None,
                    ownerName=item.createdByName or None,
                    ownedByCurrentUser=bool(
                        client.user_id and item.createdBy == client.user_id
                    ),
                )
                for item in sorted(
                    summary_items,
                    key=lambda entry: (
                        entry.locationId,
                        entry.x,
                        entry.y,
                        entry.title.casefold(),
                    ),
                )[:20]
            ]
            await self._send(
                client.websocket,
                AdminPlatformOverviewResultPacket(
                    type="admin_platform_overview",
                    scope=packet.scope,
                    serverVersion=self.server_version,
                    expectedClientRevision=self._current_expected_client_revision() or None,
                    connectedUsers=len(self.clients),
                    itemCount=len(self.item_service.items),
                    serviceLinkCount=len(service_items),
                    ownedContentCount=len(owned_items),
                    links=links,
                ),
            )
            return True

        if isinstance(packet, AdminNotificationsListPacket):
            await self._send_admin_notifications(client, scope=packet.scope)
            return True

        if isinstance(packet, AdminNotificationMarkReadPacket):
            if not client.user_id:
                await deny("notifications_mark_read", "Sign in to manage notifications.")
                return True
            include_admin = packet.scope == "admin"
            if include_admin and not self._client_has_permission(
                client, "notifications.read.any"
            ):
                await deny("notifications_mark_read", "Not authorized.")
                return True
            changed = self.notification_service.mark_read(
                user_id=client.user_id,
                notification_id=packet.notificationId,
                include_admin=include_admin,
            )
            await self._send_admin_action_result(
                client,
                ok=True,
                action="notifications_mark_read",
                message=f"Marked {changed} notification{'s' if changed != 1 else ''} read.",
            )
            return True

        if isinstance(packet, AdminBlindSoftwareSyncPacket):
            if not self._client_has_permission(client, "server.manage_settings"):
                await deny("blindsoftware_admin_sync", "Not authorized.")
                return True
            changed = await self._sync_blind_productions_billboards_once()
            await self._add_notification(
                kind="blindsoftware.admin",
                title="BlindSoftware admin sync complete",
                message=f"Refreshed BlindSoftware admin integrations; {len(changed)} billboard item{'s' if len(changed) != 1 else ''} changed.",
                actor_user_id=client.user_id,
            )
            await self._send_admin_action_result(
                client,
                ok=True,
                action="blindsoftware_admin_sync",
                message=f"BlindSoftware admin sync complete. {len(changed)} billboard item{'s' if len(changed) != 1 else ''} changed.",
            )
            return True

        if isinstance(packet, AdminRoleCreatePacket):
            if not self._client_has_permission(client, "role.manage"):
                await deny("role_create", "Not authorized.")
                return True
            try:
                created = self.auth_service.create_role(packet.name)
            except AuthError as exc:
                await deny("role_create", str(exc))
                return True
            LOGGER.info(
                "role created actor=%s role=%s", client.user_id, created["name"]
            )
            await self._send_admin_action_result(
                client,
                ok=True,
                action="role_create",
                message=f"Created role {created['name']}.",
            )
            return True

        if isinstance(packet, AdminRoleUpdatePermissionsPacket):
            if not self._client_has_permission(client, "role.manage"):
                await deny("role_update_permissions", "Not authorized.")
                return True
            affected_user_ids = self.auth_service.list_connected_user_ids_for_role(
                packet.role
            )
            try:
                assigned = self.auth_service.update_role_permissions(
                    packet.role, packet.permissions
                )
            except AuthError as exc:
                await deny("role_update_permissions", str(exc))
                return True
            LOGGER.info(
                "role permissions updated actor=%s role=%s permission_count=%d",
                client.user_id,
                packet.role,
                len(assigned),
            )
            await self._sync_permissions_for_user_ids(affected_user_ids)
            await self._send_admin_action_result(
                client,
                ok=True,
                action="role_update_permissions",
                message=f"Updated permissions for {packet.role}.",
            )
            return True

        if isinstance(packet, AdminRoleDeletePacket):
            if not self._client_has_permission(client, "role.manage"):
                await deny("role_delete", "Not authorized.")
                return True
            try:
                affected_usernames, replacement = self.auth_service.delete_role(
                    packet.role, packet.replacementRole
                )
            except AuthError as exc:
                await deny("role_delete", str(exc))
                return True
            affected_ids = [
                user_id
                for username in affected_usernames
                for user_id in [self.auth_service.get_user_id_by_username(username)]
                if user_id is not None
            ]
            await self._sync_permissions_for_user_ids(affected_ids)
            LOGGER.info(
                "role deleted actor=%s role=%s replacement=%s affected=%d",
                client.user_id,
                packet.role,
                replacement,
                len(affected_usernames),
            )
            await self._send_admin_action_result(
                client,
                ok=True,
                action="role_delete",
                message=f"Deleted role {packet.role}; reassigned {len(affected_usernames)} users to {replacement}.",
            )
            return True

        if isinstance(packet, AdminUserSetRolePacket):
            if not self._client_has_permission(client, "user.change_role"):
                await deny("user_set_role", "Not authorized.")
                return True
            target_id = self.auth_service.get_user_id_by_username(packet.username)
            try:
                username = self.auth_service.set_user_role(
                    packet.username, packet.role, actor_user_id=client.user_id
                )
            except AuthError as exc:
                await deny("user_set_role", str(exc))
                return True
            if target_id:
                await self._sync_permissions_for_user_ids([target_id])
            LOGGER.info(
                "user role changed actor=%s target=%s role=%s",
                client.user_id,
                username,
                packet.role,
            )
            await self._send_admin_action_result(
                client,
                ok=True,
                action="user_set_role",
                message=f"Set role for {username} to {packet.role}.",
            )
            return True

        if isinstance(packet, AdminUserBanPacket):
            if not self._client_has_permission(client, "user.ban_unban"):
                await deny("user_ban", "Not authorized.")
                return True
            target_id = self.auth_service.get_user_id_by_username(packet.username)
            try:
                username = self.auth_service.set_user_status(
                    packet.username, "disabled"
                )
            except AuthError as exc:
                await deny("user_ban", str(exc))
                return True
            if target_id:
                await self._sync_permissions_for_user_ids([target_id])
                for active in list(self.clients.values()):
                    if active.user_id != target_id:
                        continue
                    await self._send(
                        active.websocket,
                        AuthResultPacket(
                            type="auth_result", ok=False, message="Account is disabled."
                        ),
                    )
                    await active.websocket.close()
            LOGGER.info("user banned actor=%s target=%s", client.user_id, username)
            await self._send_admin_action_result(
                client,
                ok=True,
                action="user_ban",
                message=f"Banned {username}.",
            )
            return True

        if isinstance(packet, AdminUserUnbanPacket):
            if not self._client_has_permission(client, "user.ban_unban"):
                await deny("user_unban", "Not authorized.")
                return True
            target_id = self.auth_service.get_user_id_by_username(packet.username)
            try:
                username = self.auth_service.set_user_status(packet.username, "active")
            except AuthError as exc:
                await deny("user_unban", str(exc))
                return True
            if target_id:
                await self._sync_permissions_for_user_ids([target_id])
            LOGGER.info("user unbanned actor=%s target=%s", client.user_id, username)
            await self._send_admin_action_result(
                client,
                ok=True,
                action="user_unban",
                message=f"Unbanned {username}.",
            )
            return True

        if isinstance(packet, AdminUserDeletePacket):
            if not self._client_has_permission(client, "account.delete.any"):
                await deny("user_delete", "Not authorized.")
                return True
            target_id = self.auth_service.get_user_id_by_username(packet.username)
            try:
                username = self.auth_service.delete_user(
                    packet.username, actor_user_id=client.user_id
                )
            except AuthError as exc:
                await deny("user_delete", str(exc))
                return True
            if target_id:
                for active in list(self.clients.values()):
                    if active.user_id != target_id:
                        continue
                    await self._send(
                        active.websocket,
                        AuthResultPacket(
                            type="auth_result", ok=False, message="Account deleted."
                        ),
                    )
                    await active.websocket.close()
            LOGGER.info("user deleted actor=%s target=%s", client.user_id, username)
            await self._send_admin_action_result(
                client,
                ok=True,
                action="user_delete",
                message=f"Deleted account {username}.",
            )
            return True

        return True

    async def _handle_message(self, client: ClientConnection, raw_message: str) -> None:
        """Decode, validate, and route one inbound client packet."""

        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            PACKET_LOGGER.warning("non-json packet from id=%s", client.id)
            return

        try:
            packet = CLIENT_PACKET_ADAPTER.validate_python(payload)
        except ValidationError as exc:
            PACKET_LOGGER.warning("invalid packet from id=%s: %s", client.id, exc)
            return

        # Test-harness compatibility: some unit tests inject clients directly into
        # `server.clients` without running auth handshake packets.
        if not client.authenticated and client.websocket in self.clients:
            client.authenticated = True
            client.user_id = client.user_id or client.id
            client.username = client.username or client.nickname
            client.role = "admin"
            client.permissions = set(self.auth_service.list_all_permissions())

        if await self._handle_auth_packet(client, packet):
            return
        if not client.authenticated:
            await self._send(
                client.websocket,
                AuthResultPacket(
                    type="auth_result",
                    ok=False,
                    message="Authenticate before sending gameplay actions.",
                ),
            )
            return

        if isinstance(packet, WelcomeReadyPacket):
            await self._activate_authenticated_client(client)
            return

        if isinstance(packet, PingPacket):
            await self._send(
                client.websocket,
                PongPacket(type="pong", clientSentAt=packet.clientSentAt),
            )
            return

        if not client.world_ready:
            PACKET_LOGGER.info(
                "ignoring pre-ready packet id=%s type=%s", client.id, packet.type
            )
            return

        if await self._handle_admin_packet(client, packet):
            return

        if isinstance(packet, ChangeLocationPacket):
            await self._change_client_location(client, packet.locationId)
            return

        if isinstance(packet, UpdatePositionPacket):
            if not self._is_in_bounds(packet.x, packet.y, client.location_id):
                PACKET_LOGGER.warning(
                    "out-of-bounds position ignored id=%s x=%d y=%d grid_size=%d",
                    client.id,
                    packet.x,
                    packet.y,
                    self.grid_size,
                )
                await self._send(
                    client.websocket,
                    self._position_packet_for(client),
                )
                return
            if client.seated_item_id and packet.x == client.x and packet.y == client.y:
                await self._send(client.websocket, self._position_packet_for(client))
                return
            now_ms = self.item_service.now_ms()
            requested_delta = max(abs(packet.x - client.x), abs(packet.y - client.y))
            if not self._consume_movement_budget(client, now_ms, requested_delta):
                remaining = max(
                    0,
                    self.movement_max_steps_per_tick
                    - client.movement_window_steps_used,
                )
                PACKET_LOGGER.warning(
                    "position rate limit ignored id=%s from=%d,%d to=%d,%d requested_delta=%d remaining_budget=%d window=%d",
                    client.id,
                    client.x,
                    client.y,
                    packet.x,
                    packet.y,
                    requested_delta,
                    remaining,
                    client.movement_window_index,
                )
                await self._send(
                    client.websocket,
                    self._position_packet_for(client),
                )
                return
            old_x = client.x
            old_y = client.y
            previous_seated_item_id = client.seated_item_id
            previous_seated_item = (
                self.items.get(previous_seated_item_id)
                if previous_seated_item_id
                else None
            )
            client.x = packet.x
            client.y = packet.y
            client.seated_item_id = None
            client.seated_offset = 0.0
            client.posture = "standing"
            client.last_position_update_ms = now_ms
            self._persist_client_position(client)
            await self._send(
                client.websocket,
                self._position_packet_for(client),
            )
            await self._broadcast_location(
                client.location_id,
                self._position_packet_for(client),
                exclude=client.websocket,
            )
            if previous_seated_item_id:
                label = (
                    previous_seated_item.title
                    if previous_seated_item is not None
                    else "the furniture"
                )
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"You get up from {label}.",
                        system=True,
                    ),
                )
                await self._broadcast_location(
                    client.location_id,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"{client.nickname} gets up from {label}.",
                        system=True,
                    ),
                    exclude=client.websocket,
                )
            await self._update_carried_items_after_client_move(
                client, old_x=old_x, old_y=old_y, now_ms=now_ms
            )
            return

        if isinstance(packet, TeleportCompletePacket):
            if not self._is_in_bounds(packet.x, packet.y, client.location_id):
                PACKET_LOGGER.warning(
                    "out-of-bounds teleport ignored id=%s x=%d y=%d grid_size=%d",
                    client.id,
                    packet.x,
                    packet.y,
                    self.grid_size,
                )
                await self._send(
                    client.websocket,
                    BroadcastPositionPacket(
                        type="update_position", id=client.id, x=client.x, y=client.y
                    ),
                )
                return

            old_x = client.x
            old_y = client.y
            client.x = packet.x
            client.y = packet.y
            client.seated_item_id = None
            client.seated_offset = 0.0
            client.posture = "standing"
            now_ms = self.item_service.now_ms()
            client.last_position_update_ms = now_ms
            self._persist_client_position(client, force=True)
            await self._send(
                client.websocket,
                self._position_packet_for(client),
            )
            await self._broadcast_location(
                client.location_id,
                self._position_packet_for(client),
                exclude=client.websocket,
            )
            await self._update_carried_items_after_client_move(
                client, old_x=old_x, old_y=old_y, now_ms=now_ms
            )
            await self._broadcast_location(
                client.location_id,
                BroadcastTeleportCompletePacket(
                    type="teleport_complete",
                    id=client.id,
                    x=client.x,
                    y=client.y,
                ),
                exclude=client.websocket,
            )
            return

        if isinstance(packet, UpdateNicknamePacket):
            if not self._client_has_permission(client, "profile.update_nickname"):
                await self._send(
                    client.websocket,
                    NicknameResultPacket(
                        type="nickname_result",
                        accepted=False,
                        requestedNickname=packet.nickname,
                        effectiveNickname=client.nickname,
                        reason="Not authorized to change nickname.",
                    ),
                )
                return
            requested_nickname = packet.nickname.strip()
            if not requested_nickname:
                await self._send(
                    client.websocket,
                    NicknameResultPacket(
                        type="nickname_result",
                        accepted=False,
                        requestedNickname=packet.nickname,
                        effectiveNickname=client.nickname,
                        reason="Nickname is required.",
                    ),
                )
                return
            old_nickname = client.nickname
            if requested_nickname == old_nickname:
                await self._send(
                    client.websocket,
                    NicknameResultPacket(
                        type="nickname_result",
                        accepted=True,
                        requestedNickname=requested_nickname,
                        effectiveNickname=client.nickname,
                    ),
                )
                return
            if self._is_nickname_taken(requested_nickname, exclude_client_id=client.id):
                await self._send(
                    client.websocket,
                    NicknameResultPacket(
                        type="nickname_result",
                        accepted=False,
                        requestedNickname=requested_nickname,
                        effectiveNickname=client.nickname,
                        reason="Nickname already in use.",
                    ),
                )
                return
            client.nickname = requested_nickname
            if client.user_id:
                self.auth_service.set_last_nickname(client.user_id, client.nickname)
            if old_nickname == "user...":
                LOGGER.info("user login id=%s nickname=%s", client.id, client.nickname)
            else:
                LOGGER.info(
                    "nickname change id=%s old=%s new=%s",
                    client.id,
                    old_nickname,
                    client.nickname,
                )
            await self._send(
                client.websocket,
                NicknameResultPacket(
                    type="nickname_result",
                    accepted=True,
                    requestedNickname=requested_nickname,
                    effectiveNickname=client.nickname,
                ),
            )
            await self._broadcast_location(
                client.location_id,
                BroadcastNicknamePacket(
                    type="update_nickname", id=client.id, nickname=client.nickname
                ),
                exclude=client.websocket,
            )
            if old_nickname == "user...":
                await self._broadcast_location(
                    client.location_id,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"{client.nickname} has logged in.",
                        system=True,
                    ),
                    exclude=client.websocket,
                )
            else:
                await self._broadcast_location(
                    client.location_id,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"{old_nickname} is now known as {client.nickname}.",
                        system=True,
                    ),
                    exclude=client.websocket,
                )
            self_message = (
                f"Welcome. Logged in as {client.nickname}."
                if old_nickname == "user..."
                else f"You are now known as {client.nickname}."
            )
            await self._send(
                client.websocket,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=self_message,
                    system=True,
                ),
            )
            return

        if isinstance(packet, UserActionPacket):
            await self._handle_user_action(client, packet)
            return

        if isinstance(packet, ChatMessagePacket):
            if not self._client_has_permission(client, "chat.send"):
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="You are not allowed to send chat messages.",
                        system=True,
                    ),
                )
                return
            if await self._handle_chat_command(client, packet.message):
                return
            await self._broadcast_location(
                client.location_id,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=packet.message,
                    senderId=client.id,
                    senderNickname=client.nickname,
                    system=False,
                ),
            )
            return

        if isinstance(packet, DirectMessagePacket):
            if not self._client_has_permission(client, "chat.send"):
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="You are not allowed to send chat messages.",
                        system=True,
                    ),
                )
                return
            target = next(
                (
                    other
                    for other in self.clients.values()
                    if other.id == packet.targetId
                    and other.authenticated
                    and other.location_id == client.location_id
                ),
                None,
            )
            if target is None:
                await self._send(
                    client.websocket,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message="That user is not available for direct messages.",
                        system=True,
                    ),
                )
                return
            await self._send(
                target.websocket,
                DirectMessageBroadcastPacket(
                    type="direct_message",
                    message=packet.message,
                    senderId=client.id,
                    senderNickname=client.nickname,
                    targetId=target.id,
                    targetNickname=target.nickname,
                ),
            )
            if target.user_id:
                await self._add_notification(
                    kind="direct_message",
                    title=f"Direct message from {client.nickname}",
                    message=packet.message,
                    target_user_id=target.user_id,
                    actor_user_id=client.user_id,
                )
            await self._send(
                client.websocket,
                DirectMessageBroadcastPacket(
                    type="direct_message",
                    message=packet.message,
                    senderId=client.id,
                    senderNickname=client.nickname,
                    targetId=target.id,
                    targetNickname=target.nickname,
                    outgoing=True,
                ),
            )
            return

        if isinstance(packet, ItemAddPacket):
            if not self._client_has_permission(client, "item.create"):
                await self._send_item_result(
                    client, False, "add", "Not authorized to create items."
                )
                return
            if not is_known_item_type(packet.itemType):
                await self._send_item_result(client, False, "add", "Unknown item type.")
                return
            item = self.item_service.default_item(client, packet.itemType)
            self._apply_item_creation_verification(client, item)
            self.item_service.add_item(item)
            await self._broadcast_item(item)
            self._request_state_save()
            LOGGER.info(
                "item created by=%s item_id=%s type=%s title=%s x=%d y=%d",
                client.nickname,
                item.id,
                item.type,
                item.title,
                item.x,
                item.y,
            )
            item_text = f"{item.title} ({self._item_type_label(item)})"
            await self._broadcast_location(
                client.location_id,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"{client.nickname} placed {item_text} at {item.x}, {item.y}.",
                    system=True,
                ),
                exclude=client.websocket,
            )
            await self._send_item_result(
                client,
                True,
                "add",
                f"You placed {item_text} at {item.x}, {item.y}.",
                item.id,
            )
            return

        if isinstance(packet, ItemPickupPacket):
            pickup_item = self.items.get(packet.itemId)
            if not pickup_item:
                await self._send_item_result(client, False, "pickup", "Item not found.")
                return
            move_as_surface = pickup_item.type == "furniture"
            linked_items = self._linked_relocation_items(
                pickup_item, include_attached=packet.moveAttached or move_as_surface
            )
            linked_ids = {item.id for item in linked_items}
            carried_items = self.item_service.carried_items_for_client(client.id)
            combined_carried = {
                item.id: item for item in [*carried_items, *linked_items]
            }
            if self._carried_load_count(list(combined_carried.values())) > MAX_CARRIED_ITEMS_PER_CLIENT:
                await self._send_item_result(
                    client,
                    False,
                    "pickup",
                    f"You can carry up to {MAX_CARRIED_ITEMS_PER_CLIENT} items at once.",
                    pickup_item.id,
                )
                return
            pickup_error = self._validate_linked_pickup(
                client, pickup_item, linked_items
            )
            if pickup_error:
                await self._send_item_result(
                    client,
                    False,
                    "pickup",
                    pickup_error,
                    pickup_item.id,
                )
                return
            root_x = pickup_item.x
            root_y = pickup_item.y
            now_ms = self.item_service.now_ms()
            actor_id, actor_name = self._item_updated_actor(client)
            for item in linked_items:
                moves_with_surface = self._item_surface_moves_with_linked_set(
                    item, linked_ids
                )
                item.carrierId = client.id
                item.x = client.x + (item.x - root_x)
                item.y = client.y + (item.y - root_y)
                if self._item_can_sit_on_surface(item) and not moves_with_surface:
                    item.params = self._normalize_surface_location_params(
                        item, placement="carried"
                    )
                    item.version += 1
                item.updatedAt = now_ms
                item.updatedBy = actor_id
                item.updatedByName = actor_name
                await self._broadcast_item(item)
            self._request_state_save()
            item_text = f"{pickup_item.title} ({self._item_type_label(pickup_item)})"
            linked_label = self._linked_relocation_label(linked_items)
            await self._broadcast_location(
                client.location_id,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"{client.nickname} picked up {item_text}"
                    + (
                        f" with {len(linked_items) - 1} linked part"
                        f"{'s' if len(linked_items) != 2 else ''}."
                        if len(linked_items) > 1
                        else "."
                    ),
                    system=True,
                ),
                exclude=client.websocket,
            )
            await self._send_item_result(
                client,
                True,
                "pickup",
                f"Picked up {linked_label}.",
                pickup_item.id,
            )
            return

        if isinstance(packet, ItemDropPacket):
            drop_item = self.items.get(packet.itemId)
            if not drop_item:
                await self._send_item_result(client, False, "drop", "Item not found.")
                return
            if drop_item.carrierId != client.id:
                await self._send_item_result(
                    client,
                    False,
                    "drop",
                    "You are not carrying that item.",
                    drop_item.id,
                )
                return
            if packet.targetSurfaceId:
                target = self.items.get(packet.targetSurfaceId)
                if target is None or target.type != "furniture":
                    await self._send_item_result(
                        client, False, "drop", "Surface not found.", drop_item.id
                    )
                    return
                if not self._item_can_sit_on_surface(drop_item):
                    await self._send_item_result(
                        client,
                        False,
                        "drop",
                        "That item cannot be placed on furniture.",
                        drop_item.id,
                    )
                    return
                if (
                    target.locationId != client.location_id
                    or target.carrierId is not None
                    or target.x != client.x
                    or target.y != client.y
                ):
                    await self._send_item_result(
                        client, False, "drop", "Surface is not on your square.", drop_item.id
                    )
                    return
                if not self._surface_has_open_slot(
                    target, excluding_ids={drop_item.id}
                ):
                    await self._send_item_result(
                        client,
                        False,
                        "drop",
                        f"{target.title} has no open surface space.",
                        drop_item.id,
                    )
                    return
                now_ms = self.item_service.now_ms()
                actor_id, actor_name = self._item_updated_actor(client)
                drop_item.carrierId = None
                drop_item.locationId = target.locationId
                drop_item.x = target.x
                drop_item.y = target.y
                drop_item.params = self._normalize_surface_location_params(
                    drop_item,
                    placement=self._surface_placement_value(target),
                    surface_id=target.id,
                    surface_title=target.title,
                    surface_order=self._next_surface_order(
                        target, excluding_ids={drop_item.id}
                    ),
                )
                if self._auto_link_radio_component_to_nearby_group(drop_item):
                    drop_item.version += 1
                if await self._sync_dropped_radio_with_playing_group(drop_item):
                    drop_item.version += 1
                drop_item.updatedAt = now_ms
                drop_item.updatedBy = actor_id
                drop_item.updatedByName = actor_name
                drop_item.version += 1
                self._request_state_save()
                await self._broadcast_item(drop_item)
                await self._broadcast_location(
                    drop_item.locationId,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=f"{client.nickname} places {drop_item.title} on {target.title}.",
                        system=True,
                    ),
                    exclude=client.websocket,
                )
                await self._send_item_result(
                    client,
                    True,
                    "drop",
                    f"You place {drop_item.title} on {target.title}.",
                    drop_item.id,
                )
                return
            move_as_surface = drop_item.type == "furniture"
            linked_items = [
                item
                for item in self._linked_relocation_items(
                    drop_item, include_attached=packet.moveAttached or move_as_surface
                )
                if item.carrierId == client.id
            ] or [drop_item]
            drop_error = self._validate_linked_drop(
                client, drop_item, linked_items, packet.x, packet.y
            )
            if drop_error:
                await self._send_item_result(
                    client,
                    False,
                    "drop",
                    drop_error,
                    drop_item.id,
                )
                return
            root_x = drop_item.x
            root_y = drop_item.y
            now_ms = self.item_service.now_ms()
            actor_id, actor_name = self._item_updated_actor(client)
            linked_ids = {item.id for item in linked_items}
            changed_items: dict[str, WorldItem] = {}
            for item in linked_items:
                moves_with_surface = self._item_surface_moves_with_linked_set(
                    item, linked_ids
                )
                offset_x = item.x - root_x
                offset_y = item.y - root_y
                item.carrierId = None
                item.x = packet.x + offset_x
                item.y = packet.y + offset_y
                if self._item_can_sit_on_surface(item) and not moves_with_surface:
                    item.params = self._normalize_surface_location_params(
                        item, placement="floor"
                    )
                    item.version += 1
                if self._auto_link_radio_component_to_nearby_group(item):
                    item.version += 1
                if await self._sync_dropped_radio_with_playing_group(item):
                    item.version += 1
                item.updatedAt = now_ms
                item.updatedBy = actor_id
                item.updatedByName = actor_name
                changed_items[item.id] = item
            for item in await self._auto_place_dropped_items_on_surfaces(
                linked_items,
                now_ms=now_ms,
                actor_id=actor_id,
                actor_name=actor_name,
            ):
                changed_items[item.id] = item
            self._request_state_save()
            for item in changed_items.values():
                await self._broadcast_item(item)
            item_text = f"{drop_item.title} ({self._item_type_label(drop_item)})"
            linked_label = self._linked_relocation_label(linked_items)
            await self._broadcast_location(
                client.location_id,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"{client.nickname} dropped {item_text}"
                    + (
                        f" with {len(linked_items) - 1} linked part"
                        f"{'s' if len(linked_items) != 2 else ''}"
                        if len(linked_items) > 1
                        else ""
                    )
                    + f" at {drop_item.x}, {drop_item.y}.",
                    system=True,
                ),
                exclude=client.websocket,
            )
            await self._send_item_result(
                client,
                True,
                "drop",
                f"Dropped {linked_label} at {drop_item.x}, {drop_item.y}.",
                drop_item.id,
            )
            return

        if isinstance(packet, ItemDeletePacket):
            delete_item = self.items.get(packet.itemId)
            if not delete_item:
                await self._send_item_result(client, False, "delete", "Item not found.")
                return
            if delete_item.carrierId and delete_item.carrierId != client.id:
                await self._send_item_result(
                    client,
                    False,
                    "delete",
                    "Item is being carried by another user.",
                    delete_item.id,
                )
                return
            if delete_item.carrierId is None and (
                delete_item.x != client.x or delete_item.y != client.y
            ):
                await self._send_item_result(
                    client,
                    False,
                    "delete",
                    "Item is not on your square.",
                    delete_item.id,
                )
                return
            can_delete_any = self._client_has_permission(client, "item.delete.any")
            can_delete_own = self._client_has_permission(
                client, "item.delete.own"
            ) and self._owns_item(client, delete_item)
            if not can_delete_any and not can_delete_own:
                await self._send_item_result(
                    client,
                    False,
                    "delete",
                    "Not authorized to delete this item.",
                    delete_item.id,
                )
                return
            LOGGER.info(
                "item deleted by=%s item_id=%s type=%s title=%s",
                client.nickname,
                delete_item.id,
                delete_item.type,
                delete_item.title,
            )
            self._cancel_piano_playback(delete_item.id)
            recording_state = self.piano_recording_state_by_item.pop(
                delete_item.id, None
            )
            if recording_state is not None:
                auto_stop_task = recording_state.get("autoStopTask")
                if (
                    isinstance(auto_stop_task, asyncio.Task)
                    and not auto_stop_task.done()
                ):
                    auto_stop_task.cancel()
            song_id = str(delete_item.params.get("songId", "")).strip()
            if song_id and song_id in self.item_service.piano_songs:
                self.item_service.piano_songs.pop(song_id, None)
                self.item_service.save_piano_songs()
            self.item_service.remove_item(delete_item.id)
            self.item_last_use_ms.pop(delete_item.id, None)
            await self._broadcast_location(
                delete_item.locationId,
                ItemRemovePacket(type="item_remove", itemId=delete_item.id)
            )
            self._request_state_save()
            item_text = f"{delete_item.title} ({self._item_type_label(delete_item)})"
            await self._broadcast_location(
                delete_item.locationId,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"{client.nickname} deleted {item_text}.",
                    system=True,
                ),
                exclude=client.websocket,
            )
            await self._send_item_result(
                client, True, "delete", f"You deleted {item_text}.", delete_item.id
            )
            return

        if isinstance(packet, ItemTransferTargetsPacket):
            transfer_targets_item = self.items.get(packet.itemId)
            if not transfer_targets_item:
                await self._send_item_result(
                    client, False, "transfer", "Item not found."
                )
                return
            if transfer_targets_item.carrierId:
                await self._send_item_result(
                    client,
                    False,
                    "transfer",
                    "Item cannot be transferred while carried.",
                    transfer_targets_item.id,
                )
                return
            if (
                transfer_targets_item.x != client.x
                or transfer_targets_item.y != client.y
            ):
                await self._send_item_result(
                    client,
                    False,
                    "transfer",
                    "Item is not on your square.",
                    transfer_targets_item.id,
                )
                return
            can_transfer_any = self._client_has_permission(client, "item.transfer.any")
            can_transfer_own = self._client_has_permission(
                client, "item.transfer.own"
            ) and self._owns_item(client, transfer_targets_item)
            if not can_transfer_any and not can_transfer_own:
                await self._send_item_result(
                    client,
                    False,
                    "transfer",
                    "Not authorized to transfer this item.",
                    transfer_targets_item.id,
                )
                return
            users = self.auth_service.list_users_for_admin()
            connected_user_ids = {
                other.user_id
                for other in self.clients.values()
                if other.authenticated and other.user_id
            }
            targets = [
                ItemTransferTargetSummary(
                    userId=str(entry["id"]),
                    username=str(entry["username"]),
                    online=str(entry.get("id")) in connected_user_ids,
                )
                for entry in users
                if str(entry.get("status")) == "active"
                and str(entry["id"]) != transfer_targets_item.createdBy
            ]
            await self._send(
                client.websocket,
                ItemTransferTargetsResultPacket(
                    type="item_transfer_targets",
                    itemId=transfer_targets_item.id,
                    targets=targets,
                ),
            )
            return

        if isinstance(packet, ItemTransferPacket):
            transfer_item = self.items.get(packet.itemId)
            if not transfer_item:
                await self._send_item_result(
                    client, False, "transfer", "Item not found."
                )
                return
            if transfer_item.carrierId:
                await self._send_item_result(
                    client,
                    False,
                    "transfer",
                    "Item cannot be transferred while carried.",
                    transfer_item.id,
                )
                return
            if transfer_item.x != client.x or transfer_item.y != client.y:
                await self._send_item_result(
                    client,
                    False,
                    "transfer",
                    "Item is not on your square.",
                    transfer_item.id,
                )
                return
            can_transfer_any = self._client_has_permission(client, "item.transfer.any")
            can_transfer_own = self._client_has_permission(
                client, "item.transfer.own"
            ) and self._owns_item(client, transfer_item)
            if not can_transfer_any and not can_transfer_own:
                await self._send_item_result(
                    client,
                    False,
                    "transfer",
                    "Not authorized to transfer this item.",
                    transfer_item.id,
                )
                return
            target_user_id = str(packet.targetUserId).strip()
            if not target_user_id:
                await self._send_item_result(
                    client,
                    False,
                    "transfer",
                    "Target user is not available.",
                    transfer_item.id,
                )
                return
            if transfer_item.createdBy == target_user_id:
                await self._send_item_result(
                    client,
                    False,
                    "transfer",
                    "Item already belongs to that user.",
                    transfer_item.id,
                )
                return
            target = next(
                (
                    other
                    for other in self.clients.values()
                    if other.authenticated and other.user_id == target_user_id
                ),
                None,
            )
            target_username = (
                target.username
                if target and target.username
                else target.nickname
                if target
                else self.auth_service.get_username_by_id(target_user_id)
                or target_user_id
            )
            transfer_item.createdBy = target_user_id
            transfer_item.createdByName = target_username
            transfer_item.updatedAt = self.item_service.now_ms()
            actor_id, actor_name = self._item_updated_actor(client)
            transfer_item.updatedBy = actor_id
            transfer_item.updatedByName = actor_name
            transfer_item.version += 1
            await self._broadcast_item(transfer_item)
            self._request_state_save()
            item_text = (
                f"{transfer_item.title} ({self._item_type_label(transfer_item)})"
            )
            await self._broadcast_location(
                transfer_item.locationId,
                BroadcastChatMessagePacket(
                    type="chat_message",
                    message=f"{client.nickname} transferred {item_text} to {target_username}.",
                    system=True,
                ),
                exclude=client.websocket,
            )
            await self._send_item_result(
                client,
                True,
                "transfer",
                f"You transferred {item_text} to {target_username}.",
                transfer_item.id,
            )
            await self._add_notification(
                kind="item.transfer",
                title=f"{item_text} transferred to you",
                message=f"{client.nickname} transferred {item_text} to you.",
                target_user_id=target_user_id,
                actor_user_id=client.user_id,
            )
            return

        if isinstance(packet, ItemUsePacket):
            if not self._client_has_permission(client, "item.use"):
                await self._send_item_result(
                    client, False, "use", "Not authorized to use items."
                )
                return
            use_item = self.items.get(packet.itemId)
            if not use_item:
                await self._send_item_result(client, False, "use", "Item not found.")
                return
            if use_item.carrierId not in (None, client.id):
                await self._send_item_result(
                    client, False, "use", "Item is not available.", use_item.id
                )
                return
            seatable_use = use_item.carrierId is None and self._is_seatable_item(use_item)
            if use_item.carrierId is None and not seatable_use and (
                use_item.x != client.x or use_item.y != client.y
            ):
                await self._send_item_result(
                    client, False, "use", "Item is not on your square.", use_item.id
                )
                return
            if seatable_use:
                if await self._handle_furniture_posture_use(client, use_item):
                    return
            if not await self._ensure_item_verified_for_use(client, use_item, "use"):
                return
            if await self._handle_radio_remote_use(client, use_item, sync_all=False):
                return
            if await self._handle_tv_remote_use(client, use_item, sync_all=False):
                return
            if await self._handle_house_keeper_use(client, use_item, deep_scan=False):
                return
            if use_item.type == "service_link" and self._linked_house_alarm(use_item):
                if not self._has_house_entry_access(client, use_item):
                    await self._deny_guarded_house_entry(client, use_item)
                    return
            if use_item.type == "ecrypto_bank":
                await self._send_item_result(
                    client,
                    True,
                    "use",
                    self._ecrypto_bank_use_text(client, use_item),
                    use_item.id,
                )
                return
            if (
                self._is_raywonder_studio_entry_door(use_item)
                and str(use_item.params.get("doorState", "unlocked")).strip().lower()
                == "locked"
            ):
                if self._has_valid_studio_invite(client):
                    self._studio_entry_invites.pop(client.id, None)
                    await self._send_item_result(
                        client,
                        True,
                        "use",
                        "You open the studio door and step inside.",
                        use_item.id,
                    )
                    await self._change_client_location(
                        client, RAYWONDER_STUDIO_LOCATION_ID
                    )
                    return
                await self._knock_on_raywonder_studio_door(client, use_item)
                return
            unlock_key = self._find_unlock_key_for(client, use_item)
            unlocked_with_key_message = ""
            if unlock_key is not None:
                use_item.params = {**use_item.params, "doorState": "unlocked"}
                use_item.updatedAt = self.item_service.now_ms()
                actor_id, actor_name = self._item_updated_actor(client)
                use_item.updatedBy = actor_id
                use_item.updatedByName = actor_name
                self._request_state_save()
                await self._broadcast_item(use_item)
                unlocked_with_key_message = (
                    f"{use_item.title} unlocks with {unlock_key.title}. "
                )
            handler = get_item_type_handler(use_item.type)
            now_ms = self.item_service.now_ms()
            cooldown_ms = get_item_use_cooldown_ms(use_item.type)
            last_use_ms = self.item_last_use_ms.get(use_item.id)
            if last_use_ms is not None and now_ms - last_use_ms < cooldown_ms:
                remaining_ms = cooldown_ms - (now_ms - last_use_ms)
                remaining_seconds = max(0.1, round(remaining_ms / 1000, 1))
                await self._send_item_result(
                    client,
                    False,
                    "use",
                    f"{use_item.title} is on cooldown for {remaining_seconds:.1f} s.",
                    use_item.id,
                )
                return
            try:
                if use_item.type == "house_alarm":
                    credential = str(packet.credential or "")
                    access_result = evaluate_house_alarm_access(
                        use_item,
                        client.nickname,
                        credential,
                        client.username or "",
                    )
                    setup_allowed = bool(client.user_id) and (
                        use_item.createdBy == client.user_id
                        or (client.username or "").strip().casefold()
                        in {
                            value.strip().casefold()
                            for value in str(use_item.params.get("authorizedUsernames") or "").split(",")
                            if value.strip()
                        }
                    )
                    use_result = use_house_alarm_with_credential(
                        use_item,
                        client.nickname,
                        credential,
                        self._format_clock_display_time,
                        client.username or "",
                        setup_allowed,
                    )
                    if access_result in {"authorized", "resident", "guest", "disarm"}:
                        for candidate in self.items.values():
                            if str(candidate.params.get("accessAlarmItemId") or "").strip() == use_item.id:
                                self._house_entry_invites[(client.id, candidate.id)] = time.monotonic() + 120.0
                    if access_result in {"authorized", "resident", "guest"}:
                        asyncio.create_task(
                            self._complete_house_alarm_entry(
                                client=client,
                                alarm=use_item,
                                access_result=access_result,
                            )
                        )
                    elif access_result in {"denied", "duress"}:
                        await self._notify_house_entry_event(
                            use_item,
                            client,
                            (
                                f"{client.nickname} requested access at "
                                f"{use_item.params.get('houseName') or 'the house'}. "
                                f"Use /allow {client.nickname} to let them in or "
                                f"/deny {client.nickname} to keep them outside."
                            ),
                        )
                else:
                    use_result = handler.use(
                        use_item, client.nickname, self._format_clock_display_time
                    )
            except ValueError as exc:
                await self._send_item_result(
                    client, False, "use", str(exc), use_item.id
                )
                return

            if use_result.updated_params is not None:
                try:
                    previous_params = dict(use_item.params)
                    use_item.params = handler.validate_update(
                        use_item, {**use_item.params, **use_result.updated_params}
                    )
                except ValueError as exc:
                    await self._send_item_result(
                        client, False, "use", str(exc), use_item.id
                    )
                    return
                await self._resolve_radio_playback_before_broadcast(use_item)
                self._sync_radio_play_started_at(use_item, previous_params, now_ms)
                use_item.updatedAt = now_ms
                actor_id, actor_name = self._item_updated_actor(client)
                use_item.updatedBy = actor_id
                use_item.updatedByName = actor_name
                self._request_state_save()
                await self._broadcast_item(use_item)
                if (
                    self._is_tv_media_item(use_item)
                    and previous_params.get("enabled") is False
                    and use_item.params.get("enabled") is not False
                ):
                    await self._reconcile_radios_for_active_tv(
                        use_item, client, play_started_at=now_ms
                    )

            self.item_last_use_ms[use_item.id] = now_ms
            if use_result.others_message:
                await self._broadcast_location(
                    use_item.locationId,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=use_result.others_message,
                        system=True,
                    ),
                    exclude=client.websocket,
                )
            use_sound = use_result.sound or self._resolve_item_use_sound(use_item)
            if use_sound:
                sound_x, sound_y = self._get_item_sound_source_position(use_item)
                sound_range = self._get_item_emit_range(use_item)
                await self._broadcast_location(
                    use_item.locationId,
                    ItemUseSoundPacket(
                        type="item_use_sound",
                        itemId=use_item.id,
                        sound=use_sound,
                        x=sound_x,
                        y=sound_y,
                        range=sound_range,
                    )
                )
            if use_item.type == "clock":
                await self._broadcast_clock_announcement(
                    use_item, top_of_hour=False, alarm=False
                )
            if use_item.type == "piano":
                await self._send_piano_status(
                    client,
                    item_id=use_item.id,
                    event="use_mode_entered",
                    recording_state="idle",
                )
            await self._send_item_result(
                client,
                True,
                "use",
                f"{unlocked_with_key_message}{use_result.self_message}",
                use_item.id,
            )
            if use_item.type in PLACE_TARGET_ITEM_TYPES:
                await self._repair_community_locations(broadcast=True)
            if self._should_broadcast_game_launch(use_item):
                await self._broadcast_location(
                    use_item.locationId,
                    ItemGameLaunchPacket(
                        type="item_game_launch",
                        itemId=use_item.id,
                        title=use_item.title,
                        url=str(use_item.params.get("url", "")).strip(),
                        actorId=client.id,
                        actorNickname=client.nickname,
                        x=use_item.x,
                        y=use_item.y,
                    ),
                    exclude=client.websocket,
                )
            if use_item.type == "service_link":
                target_location = self._resolve_service_link_target_location(
                    use_item, client.location_id
                )
                if target_location:
                    await self._change_client_location(client, target_location)
                    return
            target_location = self._resolve_place_target_location(use_item)
            if target_location:
                await self._change_client_location(client, target_location)
                return
            if (
                use_result.delayed_self_message is not None
                and use_result.delayed_others_message is not None
            ):
                asyncio.create_task(
                    self._broadcast_wheel_result_after_delay(
                        client=client,
                        self_message=use_result.delayed_self_message,
                        others_message=use_result.delayed_others_message,
                    )
                )
            return

        if isinstance(packet, ItemSecondaryUsePacket):
            if not self._client_has_permission(client, "item.use"):
                await self._send_item_result(
                    client, False, "secondary_use", "Not authorized to use items."
                )
                return
            secondary_item = self.items.get(packet.itemId)
            if not secondary_item:
                await self._send_item_result(
                    client, False, "secondary_use", "Item not found."
                )
                return
            if secondary_item.carrierId not in (None, client.id):
                await self._send_item_result(
                    client,
                    False,
                    "secondary_use",
                    "Item is not available.",
                    secondary_item.id,
                )
                return
            if secondary_item.carrierId is None and (
                secondary_item.x != client.x or secondary_item.y != client.y
            ):
                await self._send_item_result(
                    client,
                    False,
                    "secondary_use",
                    "Item is not on your square.",
                    secondary_item.id,
                )
                return
            if not await self._ensure_item_verified_for_use(
                client, secondary_item, "secondary_use"
            ):
                return
            if await self._handle_radio_remote_use(
                client, secondary_item, sync_all=True
            ):
                return
            if await self._handle_tv_remote_use(
                client, secondary_item, sync_all=True
            ):
                return
            if await self._handle_house_keeper_use(
                client, secondary_item, deep_scan=True
            ):
                return
            if secondary_item.type == "ecrypto_bank":
                target_location = str(
                    secondary_item.params.get("targetLocation") or ""
                ).strip()
                await self._send_item_result(
                    client,
                    True,
                    "secondary_use",
                    self._ecrypto_bank_help_text(client, secondary_item),
                    secondary_item.id,
                )
                if target_location:
                    await self._change_client_location(
                        client, self._normalize_world_location_id(target_location)
                    )
                return
            handler = get_item_type_handler(secondary_item.type)
            if handler.secondary_use is None:
                await self._send_item_result(
                    client,
                    False,
                    "secondary_use",
                    f"No secondary action for {secondary_item.title}.",
                    secondary_item.id,
                )
                return
            try:
                secondary_result = handler.secondary_use(
                    secondary_item, client.nickname, self._format_clock_display_time
                )
            except ValueError as exc:
                await self._send_item_result(
                    client, False, "secondary_use", str(exc), secondary_item.id
                )
                return
            if secondary_result.updated_params is not None:
                try:
                    previous_params = dict(secondary_item.params)
                    secondary_item.params = handler.validate_update(
                        secondary_item,
                        {**secondary_item.params, **secondary_result.updated_params},
                    )
                except ValueError as exc:
                    await self._send_item_result(
                        client, False, "secondary_use", str(exc), secondary_item.id
                    )
                    return
                await self._resolve_radio_playback_before_broadcast(secondary_item)
                now_ms = self.item_service.now_ms()
                self._sync_radio_play_started_at(
                    secondary_item, previous_params, now_ms
                )
                secondary_item.updatedAt = now_ms
                actor_id, actor_name = self._item_updated_actor(client)
                secondary_item.updatedBy = actor_id
                secondary_item.updatedByName = actor_name
                secondary_item.version += 1
                self._request_state_save()
                await self._broadcast_item(secondary_item)
            if secondary_result.others_message.strip():
                await self._broadcast_location(
                    secondary_item.locationId,
                    BroadcastChatMessagePacket(
                        type="chat_message",
                        message=secondary_result.others_message,
                        system=True,
                    ),
                    exclude=client.websocket,
                )
            await self._send_item_result(
                client,
                True,
                "secondary_use",
                secondary_result.self_message,
                secondary_item.id,
            )
            return

        if isinstance(packet, MediaCastPacket):
            target = self.items.get(packet.targetItemId)
            target_kind = str(target.params.get("objectKind", "")).strip().lower() if target else ""
            valid_target = target is not None and target.locationId == client.location_id and (
                target.type == "radio_station" or target_kind == "tv"
            )
            if not valid_target:
                await self._send_item_result(client, False, "use", "That cast receiver is not available here.", packet.targetItemId)
                return
            state_packet = MediaCastStatePacket(
                type="media_cast_state",
                casterId=client.id,
                casterNickname=client.nickname,
                targetItemId=packet.targetItemId,
                active=packet.active,
                mediaKind=packet.mediaKind,
                deviceName=packet.deviceName.strip(),
                stationCode=packet.stationCode.strip(),
                stationName=packet.stationName.strip(),
                title=packet.title.strip(),
                artist=packet.artist.strip(),
            )
            room_casts = self._active_media_casts.setdefault(client.location_id, {})
            if packet.active:
                room_casts[client.id] = state_packet
            else:
                room_casts.pop(client.id, None)
                if not room_casts:
                    self._active_media_casts.pop(client.location_id, None)
            await self._broadcast_location(client.location_id, state_packet)
            await self._send_item_result(
                client,
                True,
                "use",
                f"Cast {'started' if packet.active else 'stopped'} on {target.title}.",
                target.id,
            )
            return

        if isinstance(packet, ItemRemoteControlPacket):
            if not self._client_has_permission(client, "item.use"):
                await self._send_item_result(
                    client, False, "use", "Not authorized to use items."
                )
                return
            remote_item = self.items.get(packet.itemId)
            if not remote_item:
                await self._send_item_result(client, False, "use", "Item not found.")
                return
            if await self._handle_tv_remote_control(
                client, remote_item, packet.action
            ):
                return
            if await self._handle_radio_remote_control(
                client, remote_item, packet.action
            ):
                return
            await self._send_item_result(
                client,
                False,
                "use",
                f"{remote_item.title} is not a radio remote.",
                remote_item.id,
            )
            return

        if isinstance(packet, ItemInteractPacket):
            await self._handle_item_interact(client, packet)
            return

        if isinstance(packet, ItemPianoNotePacket):
            if not self._client_has_permission(client, "item.use"):
                return
            piano_item = self.items.get(packet.itemId)
            if not piano_item or piano_item.type != "piano":
                return
            if piano_item.carrierId not in (None, client.id):
                return
            if piano_item.carrierId is None and (
                piano_item.x != client.x or piano_item.y != client.y
            ):
                return
            active_keys = self.active_piano_keys_by_client.setdefault(client.id, set())
            if packet.on:
                if (
                    packet.keyId not in active_keys
                    and len(active_keys) >= MAX_ACTIVE_PIANO_KEYS_PER_CLIENT
                ):
                    return
                active_keys.add(packet.keyId)
            else:
                active_keys.discard(packet.keyId)
            recording_state = self.piano_recording_state_by_item.get(piano_item.id)
            if (
                recording_state
                and recording_state.get("ownerClientId") == client.id
                and recording_state.get("paused") is not True
            ):
                elapsed_ms = max(
                    0,
                    min(
                        PIANO_RECORDING_MAX_MS,
                        self._recording_elapsed_ms(recording_state),
                    ),
                )
                events = recording_state.get("events")
                if (
                    isinstance(events, list)
                    and len(events) < PIANO_RECORDING_MAX_EVENTS
                ):
                    instrument = (
                        str(piano_item.params.get("instrument", "piano"))
                        .strip()
                        .lower()
                    )
                    voice_mode = (
                        str(piano_item.params.get("voiceMode", "poly")).strip().lower()
                    )
                    if voice_mode not in {"poly", "mono"}:
                        voice_mode = "poly"
                    attack = (
                        int(piano_item.params.get("attack", 15))
                        if isinstance(piano_item.params.get("attack", 15), (int, float))
                        else 15
                    )
                    decay = (
                        int(piano_item.params.get("decay", 45))
                        if isinstance(piano_item.params.get("decay", 45), (int, float))
                        else 45
                    )
                    release = (
                        int(piano_item.params.get("release", 35))
                        if isinstance(
                            piano_item.params.get("release", 35), (int, float)
                        )
                        else 35
                    )
                    brightness = (
                        int(piano_item.params.get("brightness", 55))
                        if isinstance(
                            piano_item.params.get("brightness", 55), (int, float)
                        )
                        else 55
                    )
                    emit_range = (
                        int(piano_item.params.get("emitRange", 15))
                        if isinstance(
                            piano_item.params.get("emitRange", 15), (int, float)
                        )
                        else 15
                    )
                    events.append(
                        {
                            "t": elapsed_ms,
                            "keyId": packet.keyId[:32],
                            "midi": packet.midi,
                            "on": packet.on,
                            "instrument": instrument,
                            "voiceMode": voice_mode,
                            "attack": max(0, min(100, attack)),
                            "decay": max(0, min(100, decay)),
                            "release": max(0, min(100, release)),
                            "brightness": max(0, min(100, brightness)),
                            "emitRange": max(5, min(20, emit_range)),
                        }
                    )
                if elapsed_ms >= PIANO_RECORDING_MAX_MS:
                    await self._finalize_piano_recording(
                        piano_item.id, notify_owner=True
                    )
            await self._broadcast_item_piano_note(
                piano_item,
                sender_id=client.id,
                key_id=packet.keyId,
                midi=packet.midi,
                on=packet.on,
                exclude=client.websocket,
            )
            return

        if isinstance(packet, ItemPianoRecordingPacket):
            if not self._client_has_permission(client, "item.use"):
                await self._send_item_result(
                    client, False, "use", "Not authorized to use items."
                )
                return
            recording_item = self.items.get(packet.itemId)
            if not recording_item or recording_item.type != "piano":
                await self._send_item_result(client, False, "use", "Piano not found.")
                return
            if recording_item.carrierId not in (None, client.id):
                await self._send_item_result(
                    client, False, "use", "Piano is not available.", recording_item.id
                )
                return
            if recording_item.carrierId is None and (
                recording_item.x != client.x or recording_item.y != client.y
            ):
                await self._send_item_result(
                    client,
                    False,
                    "use",
                    "Piano is not on your square.",
                    recording_item.id,
                )
                return

            if packet.action == "toggle_record":
                existing = self.piano_recording_state_by_item.get(recording_item.id)
                if existing and existing.get("ownerClientId") != client.id:
                    await self._send_item_result(
                        client,
                        False,
                        "use",
                        "This piano is already recording.",
                        recording_item.id,
                    )
                    return
                if existing and existing.get("ownerClientId") == client.id:
                    if existing.get("paused") is True:
                        existing["paused"] = False
                        existing["lastResumeMonotonic"] = time.monotonic()
                        await self._send_piano_status(
                            client,
                            item_id=recording_item.id,
                            event="record_resumed",
                            recording_state="recording",
                        )
                        await self._send_item_result(
                            client, True, "use", "Recording resumed.", recording_item.id
                        )
                    else:
                        existing["elapsedMs"] = self._recording_elapsed_ms(existing)
                        existing["paused"] = True
                        existing.pop("lastResumeMonotonic", None)
                        await self._send_piano_status(
                            client,
                            item_id=recording_item.id,
                            event="record_paused",
                            recording_state="paused",
                        )
                        await self._send_item_result(
                            client, True, "use", "Recording paused.", recording_item.id
                        )
                    return
                self._cancel_piano_playback(recording_item.id)
                new_recording_state: PianoRecordingSession = {
                    "ownerClientId": client.id,
                    "elapsedMs": 0,
                    "paused": False,
                    "lastResumeMonotonic": time.monotonic(),
                    "events": [],
                }
                self.piano_recording_state_by_item[recording_item.id] = (
                    new_recording_state
                )
                auto_stop_task = asyncio.create_task(
                    self._auto_stop_piano_recording(recording_item.id)
                )
                new_recording_state["autoStopTask"] = auto_stop_task
                await self._send_piano_status(
                    client,
                    item_id=recording_item.id,
                    event="record_started",
                    recording_state="recording",
                )
                await self._send_item_result(
                    client, True, "use", "Recording started.", recording_item.id
                )
                return

            if packet.action == "stop_record":
                existing = self.piano_recording_state_by_item.get(recording_item.id)
                if existing and existing.get("ownerClientId") != client.id:
                    await self._send_item_result(
                        client,
                        False,
                        "use",
                        "This piano is already recording.",
                        recording_item.id,
                    )
                    return
                if existing and existing.get("ownerClientId") == client.id:
                    await self._finalize_piano_recording(
                        recording_item.id, notify_owner=True
                    )
                    return
                await self._send_piano_status(
                    client,
                    item_id=recording_item.id,
                    event="record_stopped",
                    recording_state="idle",
                )
                await self._send_item_result(
                    client, True, "use", "Recording stopped.", recording_item.id
                )
                return

            if packet.action == "playback":
                if recording_item.id in self.piano_recording_state_by_item:
                    await self._send_item_result(
                        client,
                        False,
                        "use",
                        "Stop recording before playback.",
                        recording_item.id,
                    )
                    return
                song_id = str(recording_item.params.get("songId", "")).strip()
                has_song = (
                    isinstance(self.item_service.piano_songs.get(song_id), dict)
                    if song_id
                    else False
                )
                if not has_song:
                    await self._send_item_result(
                        client,
                        False,
                        "use",
                        "No recording saved on this piano.",
                        recording_item.id,
                    )
                    return
                self._cancel_piano_playback(recording_item.id)
                playback_task = asyncio.create_task(
                    self._start_piano_playback(recording_item)
                )
                self.piano_playback_tasks_by_item[recording_item.id] = playback_task
                await self._send_piano_status(
                    client,
                    item_id=recording_item.id,
                    event="playback_started",
                    recording_state="playback",
                )
                await self._send_item_result(
                    client, True, "use", "Playback started.", recording_item.id
                )
                return

            if packet.action == "stop_playback":
                self._cancel_piano_playback(recording_item.id)
                await self._send_piano_status(
                    client,
                    item_id=recording_item.id,
                    event="playback_stopped",
                    recording_state="idle",
                )
                await self._send_item_result(
                    client, True, "use", "Playback stopped.", recording_item.id
                )
                return
            return

        if isinstance(packet, ItemUpdatePacket):
            update_item = self.items.get(packet.itemId)
            if not update_item:
                await self._send_item_result(client, False, "update", "Item not found.")
                return
            if update_item.carrierId not in (None, client.id):
                await self._send_item_result(
                    client,
                    False,
                    "update",
                    "Item is not available for editing.",
                    update_item.id,
                )
                return
            if update_item.carrierId is None and (
                update_item.x != client.x or update_item.y != client.y
            ):
                await self._send_item_result(
                    client,
                    False,
                    "update",
                    "Item is not on your square.",
                    update_item.id,
                )
                return
            can_edit_any = self._client_has_permission(client, "item.edit.any")
            can_edit_own = self._client_has_permission(
                client, "item.edit.own"
            ) and self._owns_item(client, update_item)
            if not can_edit_any and not can_edit_own:
                await self._send_item_result(
                    client,
                    False,
                    "update",
                    "Not authorized to edit this item.",
                    update_item.id,
                )
                return
            previous_title = update_item.title
            previous_furniture_kind = (
                update_item.params.get("furnitureKind")
                if update_item.type == "furniture"
                else None
            )
            title_changed = False
            if packet.title is not None:
                title = packet.title.strip()
                if not title:
                    await self._send_item_result(
                        client,
                        False,
                        "update",
                        "Title cannot be empty.",
                        update_item.id,
                    )
                    return
                update_item.title = title[:80]
                title_changed = update_item.title != previous_title
            if packet.params:
                previous_params = dict(update_item.params)
                next_params = {**update_item.params, **packet.params}
                handler = get_item_type_handler(update_item.type)
                try:
                    next_params = handler.validate_update(update_item, next_params)
                except ValueError as exc:
                    await self._send_item_result(
                        client, False, "update", str(exc), update_item.id
                    )
                    return
                update_item.params = next_params
                if update_item.type == "room":
                    target_location_id = self._normalize_world_location_id(
                        update_item.params.get("targetLocation")
                    )
                    room_location = self._get_world_location(target_location_id)
                    width = int(update_item.params.get("widthSquares", room_location.width))
                    height = int(update_item.params.get("depthSquares", room_location.height))
                    self._location_dimension_overrides[target_location_id] = (
                        max(1, min(self.grid_size, width)),
                        max(1, min(self.grid_size, height)),
                    )
                    await self._broadcast_location(
                        target_location_id,
                        WorldConfigUpdatePacket(
                            type="world_config_update",
                            locationId=target_location_id,
                            width=min(self.grid_size, width),
                            height=min(self.grid_size, height),
                        ),
                    )
                auto_linked = self._auto_link_radio_component_to_nearby_group(
                    update_item
                )
                if auto_linked:
                    update_item.params = handler.validate_update(
                        update_item, update_item.params
                    )
                await self._resolve_radio_playback_before_broadcast(update_item)
                if auto_linked:
                    await self._sync_dropped_radio_with_playing_group(update_item)
                self._sync_radio_play_started_at(
                    update_item, previous_params, self.item_service.now_ms()
                )
                await self._sync_radio_speakers_from_primary(update_item, client)
                if (
                    update_item.type == "furniture"
                    and "furnitureKind" in packet.params
                    and packet.title is None
                    and self._is_generic_furniture_title(
                        previous_title, previous_furniture_kind
                    )
                ):
                    next_kind_title = (
                        str(update_item.params.get("furnitureKind") or "furniture")
                        .replace("_", " ")
                        .strip()
                    )
                    if next_kind_title and update_item.title != next_kind_title:
                        update_item.title = next_kind_title[:80]
                        title_changed = True
            now_ms = self.item_service.now_ms()
            actor_id, actor_name = self._item_updated_actor(client)
            dependent_surface_updates: list[WorldItem] = []
            if title_changed:
                for dependent in self._surface_dependents_for(
                    update_item.id, self.items
                ):
                    if dependent.id == update_item.id:
                        continue
                    if dependent.params.get("surfaceTitle") == update_item.title:
                        continue
                    dependent.params["surfaceTitle"] = update_item.title
                    dependent.updatedAt = now_ms
                    dependent.updatedBy = actor_id
                    dependent.updatedByName = actor_name
                    dependent.version += 1
                    dependent_surface_updates.append(dependent)
            update_item.updatedAt = now_ms
            update_item.updatedBy = actor_id
            update_item.updatedByName = actor_name
            update_item.version += 1
            await self._broadcast_item(update_item)
            for dependent in dependent_surface_updates:
                await self._broadcast_item(dependent)
            self._request_state_save()
            await self._send_item_result(
                client, True, "update", f"Updated {update_item.title}.", update_item.id
            )
            return

        if isinstance(packet, SpeakPacket):
            if not self._client_has_permission(client, "chat.send"):
                return
            if not isinstance(packet.audioUrl, str) or not packet.audioUrl.startswith(
                VOICE_URL_PREFIX
            ):
                PACKET_LOGGER.info(
                    "speak rejected bad audioUrl sender=%s", client.id
                )
                return
            filename = packet.audioUrl[len(VOICE_URL_PREFIX) :]
            resolved = voice_file_path(filename)
            if resolved is None:
                PACKET_LOGGER.info(
                    "speak rejected missing audio file sender=%s", client.id
                )
                return
            await self._broadcast_location(
                client.location_id,
                AgentVoicePacket(
                    type="agent_voice",
                    senderId=client.id,
                    senderNickname=client.nickname,
                    audioUrl=packet.audioUrl,
                    x=client.x,
                    y=client.y,
                    range=packet.range,
                ),
            )
            return

        if not self._client_has_permission(client, "voice.send"):
            return
        if not isinstance(packet, SignalPacket):
            return
        target = self._find_by_id(packet.targetId)
        if not target:
            PACKET_LOGGER.info(
                "signal target not found sender=%s target=%s",
                client.id,
                packet.targetId,
            )
            return

        await self._send(
            target.websocket,
            ForwardSignalPacket(
                type="signal",
                senderId=client.id,
                senderNickname=client.nickname,
                x=client.x,
                y=client.y,
                sdp=packet.sdp,
                ice=packet.ice,
            ),
        )

    async def _broadcast(
        self, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        """Broadcast one packet to all clients except an optional websocket."""

        recipients = [
            websocket for websocket in self.clients if websocket is not exclude
        ]
        if not recipients:
            return
        await asyncio.gather(
            *(self._send(websocket, packet) for websocket in recipients)
        )

    async def _send(self, websocket: ServerConnection, packet: object) -> None:
        """Send one packet to one websocket, swallowing per-client send failures."""

        try:
            if hasattr(packet, "model_dump"):
                data = packet.model_dump(exclude_none=True)
            else:
                data = packet
            await websocket.send(json.dumps(data))
        except (
            Exception
        ) as exc:  # intentionally broad to keep server alive per client error
            LOGGER.debug("send failure: %s", exc)

    def _find_by_id(self, client_id: str) -> ClientConnection | None:
        """Resolve a client id to an active connection."""

        for client in self.clients.values():
            if client.id == client_id:
                return client
        return None

    @staticmethod
    def _build_ssl_context(cert: str | None, key: str | None) -> ssl.SSLContext | None:
        """Create TLS server context when cert/key are configured."""

        if not cert or not key:
            return None
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=Path(cert), keyfile=Path(key))
        return context


def run() -> None:
    """CLI entrypoint for running the signaling server process."""

    parser = argparse.ArgumentParser(description="chgrid signaling server")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--ssl-cert", default=None)
    parser.add_argument("--ssl-key", default=None)
    parser.add_argument("--allow-insecure-ws", action="store_true", default=None)
    parser.add_argument("--bootstrap-admin", action="store_true", default=False)
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    if config_path and not config_path.exists() and args.config == "config.toml":
        config_path = None
    config = load_config(config_path)

    host = args.host or config.server.bind_ip
    port = args.port or config.server.port
    allow_insecure_ws = config.network.allow_insecure_ws
    if args.allow_insecure_ws is True:
        allow_insecure_ws = True

    ssl_cert = (
        args.ssl_cert if args.ssl_cert is not None else config.tls.cert_file or None
    )
    ssl_key = args.ssl_key if args.ssl_key is not None else config.tls.key_file or None
    state_file_value = config.storage.state_file.strip()
    state_file: Path | None = None
    if state_file_value:
        base_dir = config_path.parent if config_path is not None else Path.cwd()
        state_file = Path(state_file_value)
        if not state_file.is_absolute():
            state_file = base_dir / state_file

    if not allow_insecure_ws and (not ssl_cert or not ssl_key):
        raise SystemExit(
            "TLS is required when insecure ws is disabled. Set tls.cert_file/tls.key_file in config.toml."
        )

    auth_secret = os.getenv("CHGRID_AUTH_SECRET", "").strip()
    if not auth_secret:
        raise SystemExit("CHGRID_AUTH_SECRET is required.")
    host_origin = os.getenv("CHGRID_HOST_ORIGIN", "").strip()
    if not host_origin:
        raise SystemExit("CHGRID_HOST_ORIGIN is required.")
    try:
        host_origin = normalize_origin(host_origin, field_name="CHGRID_HOST_ORIGIN")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    auth_db_value = config.auth.db_file.strip()
    if not auth_db_value:
        raise SystemExit("auth.db_file must not be empty.")
    auth_base_dir = config_path.parent if config_path is not None else Path.cwd()
    auth_db_path = Path(auth_db_value)
    if not auth_db_path.is_absolute():
        auth_db_path = auth_base_dir / auth_db_path
    auth_db_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, config.logging.level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.bootstrap_admin:
        auth_service = AuthService(
            db_path=auth_db_path,
            token_hash_secret=auth_secret,
            password_min_length=config.auth.password_min_length,
            password_max_length=config.auth.password_max_length,
            username_min_length=config.auth.username_min_length,
            username_max_length=config.auth.username_max_length,
        )
        try:
            print(
                "Username rules: "
                f"{auth_service.username_min_length}-{auth_service.username_max_length} chars, "
                "lowercase letters, numbers, underscore, dash."
            )
            print(
                "Password rules: "
                f"{auth_service.password_min_length}-{auth_service.password_max_length} chars."
            )
            if auth_service.has_admin():
                print("An admin account already exists.")
                return

            def prompt_create_admin() -> bool:
                while True:
                    username = input("Admin username: ").strip()
                    normalized_username = auth_service._normalize_username(username)
                    try:
                        auth_service._validate_username(normalized_username)
                    except AuthError as exc:
                        print(f"Invalid username: {exc}")
                        continue

                    password = getpass("Admin password: ")
                    try:
                        auth_service._validate_password(password)
                    except AuthError as exc:
                        print(f"Invalid password: {exc}")
                        continue

                    password_confirm = getpass("Re-enter admin password: ")
                    if password != password_confirm:
                        print("Passwords do not match.")
                        continue

                    email = input("Admin email (optional): ").strip() or None
                    try:
                        created = auth_service.bootstrap_admin(
                            normalized_username, password, email=email
                        )
                        print(f"Admin created: {created.username}")
                        return True
                    except AuthError as exc:
                        print(f"Could not create admin: {exc}")
                        if auth_service.has_admin():
                            return False

            def prompt_promote_existing_admin() -> bool:
                users = auth_service.list_users_for_admin()
                if not users:
                    print("No existing users found; create a new admin instead.")
                    return False
                print("Existing users:")
                for user in users:
                    print(f"  - {user['username']} ({user['role']}, {user['status']})")
                while True:
                    username = input("Existing username to promote: ").strip()
                    if not username:
                        print("Username is required.")
                        continue
                    try:
                        normalized = auth_service._normalize_username(username)
                        auth_service.set_user_role(normalized, "admin")
                        print(f"Admin promoted: {normalized}")
                        return True
                    except AuthError as exc:
                        print(f"Could not promote user: {exc}")

            if auth_service.list_users_for_admin():
                print("No admin account found. Choose bootstrap mode:")
                print("  1) Promote existing account to admin")
                print("  2) Create new admin account")
                while True:
                    choice = input("Select [1/2]: ").strip()
                    if choice == "1":
                        if prompt_promote_existing_admin():
                            break
                        print("Falling back to new admin creation.")
                        if prompt_create_admin():
                            break
                        continue
                    if choice == "2":
                        if prompt_create_admin():
                            break
                        continue
                    print("Please select 1 or 2.")
            else:
                prompt_create_admin()
        finally:
            auth_service.close()
        return
    server = SignalingServer(
        host,
        port,
        ssl_cert,
        ssl_key,
        auth_db_path=auth_db_path,
        auth_token_hash_secret=auth_secret,
        password_min_length=config.auth.password_min_length,
        password_max_length=config.auth.password_max_length,
        username_min_length=config.auth.username_min_length,
        username_max_length=config.auth.username_max_length,
        max_message_size=config.network.max_message_bytes,
        state_file=state_file,
        grid_size=config.world.grid_size,
        state_save_debounce_ms=config.storage.state_save_debounce_ms,
        state_save_max_delay_ms=config.storage.state_save_max_delay_ms,
        host_origin=host_origin,
        base_path=config.server.base_path,
        grid_name=config.server.grid_name,
        welcome_message=config.server.welcome_message,
    )
    asyncio.run(server.start())
