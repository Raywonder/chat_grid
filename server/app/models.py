"""Pydantic packet and entity models shared across server message handling."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BasePacket(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str


class SignalPacket(BasePacket):
    type: Literal["signal"]
    targetId: str
    sdp: dict | None = None
    ice: dict | None = None


class UpdatePositionPacket(BasePacket):
    type: Literal["update_position"]
    x: int
    y: int


class ChangeLocationPacket(BasePacket):
    type: Literal["change_location"]
    locationId: str = Field(min_length=1, max_length=64)


class TeleportCompletePacket(BasePacket):
    type: Literal["teleport_complete"]
    x: int
    y: int


class UpdateNicknamePacket(BasePacket):
    type: Literal["update_nickname"]
    nickname: str = Field(min_length=1, max_length=32)


class ChatMessagePacket(BasePacket):
    type: Literal["chat_message"]
    message: str = Field(min_length=1, max_length=500)


class DirectMessagePacket(BasePacket):
    type: Literal["direct_message"]
    targetId: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=500)


class UserActionPacket(BasePacket):
    """A contextual user-to-user action selected from the focused-user menu."""

    type: Literal["user_action"]
    actionId: Literal[
        "hug",
        "cuddle",
        "kiss",
        "tap_shoulder",
        "announce_focus",
        "wave",
        "high_five",
        "fist_bump",
        "handshake",
        "hold_hands",
        "cheer",
        "clap",
        "laugh",
        "smile",
        "wink",
        "nod",
        "shake_head",
        "bow",
        "dance",
        "spin",
        "jump",
        "shrug",
        "facepalm",
        "gasp",
        "sigh",
        "blush",
        "cry",
        "yawn",
        "apologize",
        "forgive",
        "comfort",
        "pat_back",
        "poke",
        "boop",
        "salute",
        "point",
        "thumbs_up",
        "heart",
        "sparkle",
        "celebrate",
        "tease",
        "playful_smack",
        "whisper",
        "listen",
        "sit_with",
        "step_back",
        "take_left_hand",
        "take_right_hand",
        "release_hand",
    ]
    targetId: str = Field(min_length=1, max_length=128)


class AuthRegisterPacket(BasePacket):
    type: Literal["auth_register"]
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    email: str | None = Field(default=None, max_length=320)


class AuthLoginPacket(BasePacket):
    type: Literal["auth_login"]
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AuthResumePacket(BasePacket):
    type: Literal["auth_resume"]
    sessionToken: str = Field(min_length=1, max_length=512)


class AuthExternalPacket(BasePacket):
    type: Literal["auth_external"]
    assertion: str = Field(min_length=1, max_length=8192)


class AuthLogoutPacket(BasePacket):
    type: Literal["auth_logout"]


class NtfyPreferencesGetPacket(BasePacket):
    """Request the signed-in identity's ntfy preference metadata."""

    type: Literal["ntfy_preferences_get"]


class NtfyPreferencesUpdatePacket(BasePacket):
    """Enable/disable ntfy delivery and optionally rotate the private topic."""

    type: Literal["ntfy_preferences_update"]
    enabled: bool
    rotateTopic: bool = False


class FlexPbxDialingPreferencesGetPacket(BasePacket):
    """Request the signed-in user's verified FlexPBX dialing settings."""

    type: Literal["flexpbx_dialing_preferences_get"]


class FlexPbxDialingPreferencesUpdatePacket(BasePacket):
    """Update convenience settings without granting PBX authorization."""

    type: Literal["flexpbx_dialing_preferences_update"]
    enabled: bool
    prefixes: list[str] = Field(default_factory=lambda: ["9"], max_length=8)


class FlexPbxDialingPreferencesPacket(BasePacket):
    """Server-owned FlexPBX eligibility and dialing preferences."""

    type: Literal["flexpbx_dialing_preferences"]
    verified: bool
    extension: str = ""
    outboundAllowed: bool = False
    enabled: bool = False
    prefixes: list[str] = Field(default_factory=lambda: ["9"])
    message: str = ""


class WelcomeReadyPacket(BasePacket):
    type: Literal["welcome_ready"]


class AdminRolesListPacket(BasePacket):
    type: Literal["admin_roles_list"]


class AdminRoleCreatePacket(BasePacket):
    type: Literal["admin_role_create"]
    name: str = Field(min_length=1, max_length=32)


class AdminRoleUpdatePermissionsPacket(BasePacket):
    type: Literal["admin_role_update_permissions"]
    role: str = Field(min_length=1, max_length=32)
    permissions: list[str]


class AdminRoleDeletePacket(BasePacket):
    type: Literal["admin_role_delete"]
    role: str = Field(min_length=1, max_length=32)
    replacementRole: str = Field(min_length=1, max_length=32)


class AdminUsersListPacket(BasePacket):
    type: Literal["admin_users_list"]
    action: Literal["set_role", "ban", "unban", "delete_account"] | None = None


class AdminPlatformOverviewPacket(BasePacket):
    type: Literal["admin_platform_overview"]
    scope: Literal["platform", "owned_content"] = "platform"


class AdminNotificationsListPacket(BasePacket):
    type: Literal["admin_notifications_list"]
    scope: Literal["own", "admin"] = "own"


class AdminNotificationMarkReadPacket(BasePacket):
    type: Literal["admin_notification_mark_read"]
    scope: Literal["own", "admin"] = "own"
    notificationId: str | None = Field(default=None, max_length=128)


class AdminBlindSoftwareSyncPacket(BasePacket):
    type: Literal["admin_blindsoftware_sync"]


class AdminAmbienceCatalogPacket(BasePacket):
    """Request the location and FX ambience assignment catalog."""

    type: Literal["admin_ambience_catalog"]


class AdminLocationAmbienceSetPacket(BasePacket):
    """Assign one approved FX ambience loop to one world location."""

    type: Literal["admin_location_ambience_set"]
    locationId: str = Field(min_length=1, max_length=64)
    soundId: str = Field(min_length=1, max_length=96)


class AdminUserSetRolePacket(BasePacket):
    type: Literal["admin_user_set_role"]
    username: str = Field(min_length=1, max_length=128)
    role: str = Field(min_length=1, max_length=32)


class AdminUserBanPacket(BasePacket):
    type: Literal["admin_user_ban"]
    username: str = Field(min_length=1, max_length=128)


class AdminUserUnbanPacket(BasePacket):
    type: Literal["admin_user_unban"]
    username: str = Field(min_length=1, max_length=128)


class AdminUserDeletePacket(BasePacket):
    type: Literal["admin_user_delete"]
    username: str = Field(min_length=1, max_length=128)


class PingPacket(BasePacket):
    type: Literal["ping"]
    clientSentAt: int


class ItemAddPacket(BasePacket):
    type: Literal["item_add"]
    itemType: str = Field(min_length=1)


class ItemPickupPacket(BasePacket):
    type: Literal["item_pickup"]
    itemId: str
    moveAttached: bool = False


class ItemDropPacket(BasePacket):
    type: Literal["item_drop"]
    itemId: str
    x: int
    y: int
    moveAttached: bool = False
    targetSurfaceId: str | None = None


class ItemDeletePacket(BasePacket):
    type: Literal["item_delete"]
    itemId: str


class ItemTransferPacket(BasePacket):
    type: Literal["item_transfer"]
    itemId: str
    targetUserId: str


class ItemTransferTargetsPacket(BasePacket):
    type: Literal["item_transfer_targets"]
    itemId: str


class ItemUsePacket(BasePacket):
    type: Literal["item_use"]
    itemId: str
    credential: str | None = None


class ItemSecondaryUsePacket(BasePacket):
    type: Literal["item_secondary_use"]
    itemId: str


class ItemRemoteControlPacket(BasePacket):
    type: Literal["item_remote_control"]
    itemId: str
    action: Literal[
        "station_next",
        "station_previous",
        "station_first",
        "station_last",
        "volume_up",
        "volume_down",
        "power_toggle",
        "info",
    ]


class MediaCastPacket(BasePacket):
    """Start or stop a user-owned WebRTC cast to an in-world receiver."""

    type: Literal["media_cast"]
    targetItemId: str
    active: bool
    mediaKind: Literal["audio", "video"] = "audio"
    deviceName: str = Field(default="", max_length=80)
    stationCode: str = Field(default="", max_length=24)
    stationName: str = Field(default="", max_length=120)
    title: str = Field(default="", max_length=240)
    artist: str = Field(default="", max_length=160)


class WorldPhonePacket(BasePacket):
    """Control an owned in-world phone without exposing PBX credentials."""

    type: Literal["world_phone"]
    itemId: str
    action: Literal["dial", "answer", "hangup", "contacts", "set_audio_mode"]
    target: str = Field(default="", max_length=80)
    audioMode: Literal["ear_left", "ear_right", "speaker", "local_only"] = "ear_left"


class ItemInteractPacket(BasePacket):
    type: Literal["item_interact"]
    itemId: str
    targetItemId: str | None = None
    action: Literal[
        "place_on",
        "shove_off",
        "repair",
        "replace",
        "move_surface_left",
        "move_surface_right",
    ]


class ItemPianoNotePacket(BasePacket):
    type: Literal["item_piano_note"]
    itemId: str
    keyId: str = Field(min_length=1, max_length=32)
    midi: int = Field(ge=0, le=127)
    on: bool


class ItemPianoRecordingPacket(BasePacket):
    type: Literal["item_piano_recording"]
    itemId: str
    action: Literal["toggle_record", "playback", "stop_playback", "stop_record"]


class ItemUpdatePacket(BasePacket):
    type: Literal["item_update"]
    itemId: str
    title: str | None = Field(default=None, max_length=80)
    params: dict | None = None


class WorldConfigUpdatePacket(BasePacket):
    """Broadcast an authoritative room-bound change to listeners already inside it."""

    type: Literal["world_config_update"]
    locationId: str
    width: int = Field(ge=1, le=41)
    height: int = Field(ge=1, le=41)


class MediaCastStatePacket(BasePacket):
    """Room-scoped metadata describing the currently active cast stream."""

    type: Literal["media_cast_state"]
    casterId: str
    casterNickname: str
    targetItemId: str
    active: bool
    mediaKind: Literal["audio", "video"] = "audio"
    deviceName: str = ""
    stationCode: str = ""
    stationName: str = ""
    title: str = ""
    artist: str = ""


class WorldPhoneStatePacket(BasePacket):
    """Authoritative state for an in-world phone call/device."""

    type: Literal["world_phone_state"]
    itemId: str
    ownerId: str
    ownerNickname: str
    extension: str
    deviceSide: Literal["left", "right", "front"]
    audioMode: Literal["ear_left", "ear_right", "speaker", "local_only"]
    status: Literal["idle", "ringing", "connected", "ended", "failed"]
    target: str = ""
    message: str = ""


class SpeakPacket(BasePacket):
    """Companion-to-server request to broadcast a spatial agent voice clip.

    The companion synthesizes audio via an external TTS provider, stores the
    resulting MP3 in the shared ``runtime/voice/`` directory, and sends this
    packet with a same-origin ``audioUrl``.  The server validates the URL
    and broadcasts an ``AgentVoicePacket`` to clients in the same location.
    """

    type: Literal["speak"]
    audioUrl: str = Field(min_length=1, max_length=512)
    x: int
    y: int
    range: int = Field(default=20, ge=1, le=100)


ClientPacket = (
    SignalPacket
    | UpdatePositionPacket
    | ChangeLocationPacket
    | TeleportCompletePacket
    | UpdateNicknamePacket
    | ChatMessagePacket
    | DirectMessagePacket
    | UserActionPacket
    | AuthRegisterPacket
    | AuthLoginPacket
    | AuthResumePacket
    | AuthExternalPacket
    | AuthLogoutPacket
    | NtfyPreferencesGetPacket
    | NtfyPreferencesUpdatePacket
    | FlexPbxDialingPreferencesGetPacket
    | FlexPbxDialingPreferencesUpdatePacket
    | WelcomeReadyPacket
    | AdminRolesListPacket
    | AdminRoleCreatePacket
    | AdminRoleUpdatePermissionsPacket
    | AdminRoleDeletePacket
    | AdminUsersListPacket
    | AdminPlatformOverviewPacket
    | AdminNotificationsListPacket
    | AdminNotificationMarkReadPacket
    | AdminBlindSoftwareSyncPacket
    | AdminAmbienceCatalogPacket
    | AdminLocationAmbienceSetPacket
    | AdminUserSetRolePacket
    | AdminUserBanPacket
    | AdminUserUnbanPacket
    | AdminUserDeletePacket
    | PingPacket
    | ItemAddPacket
    | ItemPickupPacket
    | ItemDropPacket
    | ItemDeletePacket
    | ItemTransferPacket
    | ItemTransferTargetsPacket
    | ItemUsePacket
    | ItemSecondaryUsePacket
    | ItemRemoteControlPacket
    | MediaCastPacket
    | WorldPhonePacket
    | ItemInteractPacket
    | ItemPianoNotePacket
    | ItemPianoRecordingPacket
    | ItemUpdatePacket
    | WorldConfigUpdatePacket
    | SpeakPacket
)


class RemoteUser(BaseModel):
    id: str
    userId: str | None = None
    nickname: str
    locationId: str = "city"
    x: int
    y: int
    posture: Literal["standing", "sitting", "lying"] = "standing"
    seatedItemId: str | None = None
    seatedOffset: float = 0.0
    handHeldById: str | None = None


class WelcomePacket(BasePacket):
    type: Literal["welcome"]
    id: str
    player: RemoteUser
    users: list[RemoteUser]
    items: list[dict] | None = None
    worldConfig: dict | None = None
    uiDefinitions: dict | None = None
    serverInfo: dict | None = None
    auth: dict | None = None


class AuthRequiredPacket(BasePacket):
    type: Literal["auth_required"]
    message: str
    authPolicy: dict | None = None
    gridName: str | None = None
    welcomeMessage: str | None = None
    releaseVersion: str | None = None
    expectedClientRevision: str | None = None
    serverVersion: str | None = None


class AuthResultPacket(BasePacket):
    type: Literal["auth_result"]
    ok: bool
    message: str
    sessionToken: str | None = None
    username: str | None = None
    role: str | None = None
    permissions: list[str] | None = None
    adminMenuActions: list[dict[str, str]] | None = None
    nickname: str | None = None
    authPolicy: dict | None = None


class NtfyPreferencesResultPacket(BasePacket):
    """Server-backed ntfy settings reusable by web and future native clients."""

    type: Literal["ntfy_preferences"]
    enabled: bool
    configured: bool
    topic: str = ""
    subscriptionUrl: str = ""
    message: str = ""


class AuthPermissionsPacket(BasePacket):
    type: Literal["auth_permissions"]
    role: str
    permissions: list[str]
    adminMenuActions: list[dict[str, str]] | None = None


class UserLeftPacket(BasePacket):
    type: Literal["user_left"]
    id: str


class BroadcastPositionPacket(BasePacket):
    type: Literal["update_position"]
    id: str
    locationId: str | None = None
    x: int
    y: int
    posture: Literal["standing", "sitting", "lying"] = "standing"
    seatedItemId: str | None = None
    seatedOffset: float = 0.0
    handHeldById: str | None = None


class LocationChangedPacket(BasePacket):
    type: Literal["location_changed"]
    id: str
    userId: str | None = None
    nickname: str | None = None
    locationId: str
    locationName: str
    x: int
    y: int


class BroadcastTeleportCompletePacket(BasePacket):
    type: Literal["teleport_complete"]
    id: str
    x: int
    y: int


class BroadcastNicknamePacket(BasePacket):
    type: Literal["update_nickname"]
    id: str
    nickname: str


class ForwardSignalPacket(BasePacket):
    type: Literal["signal"]
    senderId: str
    senderNickname: str
    locationId: str | None = None
    x: int
    y: int
    sdp: dict | None = None
    ice: dict | None = None


class BroadcastChatMessagePacket(BasePacket):
    type: Literal["chat_message"]
    message: str
    senderId: str | None = None
    senderNickname: str | None = None
    system: bool = False
    action: bool = False


class DirectMessageBroadcastPacket(BasePacket):
    type: Literal["direct_message"]
    message: str
    senderId: str
    senderNickname: str
    targetId: str
    targetNickname: str
    outgoing: bool = False


class SocialActionPacket(BasePacket):
    type: Literal["social_action"]
    actionId: str
    actorId: str
    actorNickname: str
    targetId: str | None = None
    targetNickname: str | None = None
    message: str
    sound: str | None = None
    x: int
    y: int
    range: int | None = None


class UserActionResultPacket(BasePacket):
    type: Literal["user_action_result"]
    ok: bool
    actionId: str
    message: str
    targetId: str | None = None


class PongPacket(BasePacket):
    type: Literal["pong"]
    clientSentAt: int


class NicknameResultPacket(BasePacket):
    type: Literal["nickname_result"]
    accepted: bool
    requestedNickname: str
    effectiveNickname: str
    reason: str | None = None


class WorldItem(BaseModel):
    id: str
    type: str = Field(min_length=1)
    title: str
    locationId: str = "city"
    x: int
    y: int
    createdBy: str
    createdByName: str
    updatedBy: str
    updatedByName: str
    createdAt: int
    updatedAt: int
    version: int
    capabilities: list[str]
    useSound: str | None = None
    emitSound: str | None = None
    params: dict
    carrierId: str | None = None
    display: dict[str, str] | None = None


class PersistedWorldItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    type: str = Field(min_length=1)
    title: str
    locationId: str = "city"
    x: int
    y: int
    createdBy: str
    createdByName: str | None = None
    updatedBy: str | None = None
    updatedByName: str | None = None
    createdAt: int
    updatedAt: int
    version: int
    params: dict
    carrierId: str | None = None


class ItemUpsertPacket(BasePacket):
    type: Literal["item_upsert"]
    item: WorldItem


class ItemRemovePacket(BasePacket):
    type: Literal["item_remove"]
    itemId: str


class ItemActionResultPacket(BasePacket):
    type: Literal["item_action_result"]
    ok: bool
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
    ]
    message: str
    itemId: str | None = None


class ItemTransferTargetSummary(BaseModel):
    userId: str
    username: str
    online: bool


class ItemTransferTargetsResultPacket(BasePacket):
    type: Literal["item_transfer_targets"]
    itemId: str
    targets: list[ItemTransferTargetSummary]


class ItemUseSoundPacket(BasePacket):
    type: Literal["item_use_sound"]
    itemId: str
    sound: str
    x: int
    y: int
    range: int | None = None


class ItemGameLaunchPacket(BasePacket):
    type: Literal["item_game_launch"]
    itemId: str
    title: str
    url: str
    actorId: str
    actorNickname: str
    x: int
    y: int


class ItemClockAnnouncePacket(BasePacket):
    type: Literal["item_clock_announce"]
    itemId: str
    sounds: list[str]
    x: int
    y: int
    range: int | None = None


class ItemPianoNoteBroadcastPacket(BasePacket):
    type: Literal["item_piano_note"]
    itemId: str
    senderId: str
    keyId: str
    midi: int
    on: bool
    instrument: str
    voiceMode: str
    octave: int
    attack: int
    decay: int
    release: int
    brightness: int
    x: int
    y: int
    emitRange: int


class ItemPianoStatusPacket(BasePacket):
    type: Literal["item_piano_status"]
    itemId: str
    event: Literal[
        "use_mode_entered",
        "record_started",
        "record_paused",
        "record_resumed",
        "record_stopped",
        "playback_started",
        "playback_stopped",
    ]
    recordingState: Literal["idle", "recording", "paused", "playback"] | None = None


class AdminRoleSummary(BaseModel):
    id: int
    name: str
    isSystem: bool
    userCount: int
    permissions: list[str]


class AdminRolesListResultPacket(BasePacket):
    type: Literal["admin_roles_list"]
    roles: list[AdminRoleSummary]
    permissionKeys: list[str]
    permissionTooltips: dict[str, str] | None = None


class AdminUserSummary(BaseModel):
    id: str
    username: str
    role: str
    status: Literal["active", "disabled"]


class AdminUsersListResultPacket(BasePacket):
    type: Literal["admin_users_list"]
    users: list[AdminUserSummary]


class AdminPlatformLinkSummary(BaseModel):
    itemId: str
    title: str
    kind: str
    locationId: str
    x: int
    y: int
    url: str | None = None
    author: str | None = None
    verificationStatus: str | None = None
    ownerName: str | None = None
    ownedByCurrentUser: bool = False


class AdminPlatformOverviewResultPacket(BasePacket):
    type: Literal["admin_platform_overview"]
    scope: Literal["platform", "owned_content"] = "platform"
    serverVersion: str
    expectedClientRevision: str | None = None
    connectedUsers: int
    itemCount: int
    serviceLinkCount: int
    ownedContentCount: int = 0
    links: list[AdminPlatformLinkSummary]


class AdminNotificationSummary(BaseModel):
    id: str
    createdAt: int
    kind: str
    title: str
    message: str
    targetUserId: str | None = None
    actorUserId: str | None = None
    read: bool = False


class AdminNotificationsListResultPacket(BasePacket):
    type: Literal["admin_notifications_list"]
    scope: Literal["own", "admin"] = "own"
    unreadCount: int
    notifications: list[AdminNotificationSummary]


class AdminAmbienceSoundSummary(BaseModel):
    id: str
    label: str
    category: str
    url: str
    sourceFilename: str
    durationSeconds: float
    loopStartSeconds: float
    loopEndSeconds: float
    seamCrossfadeSeconds: float


class AdminAmbienceLocationSummary(BaseModel):
    id: str
    name: str
    currentSoundId: str = ""
    currentSoundLabel: str = ""


class AdminAmbienceCatalogResultPacket(BasePacket):
    type: Literal["admin_ambience_catalog"]
    locations: list[AdminAmbienceLocationSummary]
    sounds: list[AdminAmbienceSoundSummary]


class AgentVoicePacket(BasePacket):
    """Server-to-client spatial agent voice broadcast with a same-origin audio URL."""

    type: Literal["agent_voice"]
    senderId: str = Field(min_length=1, max_length=128)
    senderNickname: str = Field(min_length=1, max_length=64)
    audioUrl: str = Field(min_length=1, max_length=512)
    x: int
    y: int
    range: int = Field(default=20, ge=1, le=100)


class AdminActionResultPacket(BasePacket):
    type: Literal["admin_action_result"]
    ok: bool
    action: Literal[
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
    message: str
