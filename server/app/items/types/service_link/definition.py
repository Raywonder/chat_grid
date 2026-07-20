"""Interactive link item static metadata and defaults."""

from __future__ import annotations

LABEL = "link"
TOOLTIP = (
    "Represents one app, game, site, station hub, service, portal, or tool "
    "you can inspect and use."
)
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "serviceKind",
    "url",
    "targetLocation",
    "portalDestinationMode",
    "portalLocationPool",
    "doorState",
    "requiredKeyId",
    "keyLocationHint",
    "portalState",
    "portalOpenSeconds",
    "portalClosedSeconds",
    "softwareAuthor",
    "verificationStatus",
    "verificationAvailableAt",
    "description",
    "launchMessage",
    "enabled",
    "emitRange",
    "emitVolume",
    "emitSoundSpeed",
    "emitSoundTempo",
    "emitInitialDelay",
    "emitLoopDelay",
    "useSound",
    "emitSound",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 12
DIRECTIONAL = False
DEFAULT_TITLE = "link"
DEFAULT_PARAMS: dict = {
    "serviceKind": "service",
    "url": "",
    "description": "",
    "launchMessage": "",
    "targetLocation": "",
    "portalDestinationMode": "random",
    "portalLocationPool": "",
    "doorState": "unlocked",
    "requiredKeyId": "",
    "keyLocationHint": "",
    "portalState": "open",
    "portalOpenSeconds": 0,
    "portalClosedSeconds": 0,
    "softwareAuthor": "",
    "verificationStatus": "author_verified",
    "verificationAvailableAt": 0,
    "enabled": True,
    "emitRange": 12,
    "emitVolume": 100,
    "emitSoundSpeed": 50,
    "emitSoundTempo": 50,
    "emitInitialDelay": 0,
    "emitLoopDelay": 0,
    "useSound": "",
    "emitSound": "",
}
PARAM_KEYS: tuple[str, ...] = (
    "serviceKind",
    "url",
    "targetLocation",
    "portalDestinationMode",
    "portalLocationPool",
    "doorState",
    "requiredKeyId",
    "keyLocationHint",
    "portalState",
    "portalOpenSeconds",
    "portalClosedSeconds",
    "softwareAuthor",
    "verificationStatus",
    "verificationAvailableAt",
    "description",
    "launchMessage",
    "enabled",
    "emitRange",
    "emitVolume",
    "emitSoundSpeed",
    "emitSoundTempo",
    "emitInitialDelay",
    "emitLoopDelay",
    "useSound",
    "emitSound",
)

SERVICE_KIND_OPTIONS: tuple[str, ...] = (
    "app",
    "door",
    "game",
    "house",
    "room",
    "service",
    "site",
    "station",
    "tool",
    "portal",
)

DOOR_STATE_OPTIONS: tuple[str, ...] = ("unlocked", "locked")
PORTAL_STATE_OPTIONS: tuple[str, ...] = ("open", "closed")
PORTAL_DESTINATION_MODE_OPTIONS: tuple[str, ...] = ("random", "static")
VERIFICATION_STATUS_OPTIONS: tuple[str, ...] = (
    "unverified",
    "community_verified",
    "author_verified",
    "staff_verified",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Display name spoken and shown for this link item.",
        "maxLength": 80,
    },
    "serviceKind": {
        "valueType": "list",
        "tooltip": "What kind of link this item represents.",
        "options": list(SERVICE_KIND_OPTIONS),
    },
    "url": {
        "valueType": "text",
        "tooltip": "Public or site-relative URL for this link, when it has one.",
        "maxLength": 2048,
    },
    "targetLocation": {
        "valueType": "text",
        "tooltip": (
            "Optional Endiginous location id or room to enter when this link "
            "or door is used."
        ),
        "maxLength": 64,
    },
    "portalDestinationMode": {
        "valueType": "list",
        "tooltip": "Whether this portal chooses a random map destination or always uses targetLocation.",
        "options": list(PORTAL_DESTINATION_MODE_OPTIONS),
        "visibleWhen": {"serviceKind": "portal"},
    },
    "portalLocationPool": {
        "valueType": "text",
        "tooltip": "Optional comma-separated location ids a random portal may choose from.",
        "maxLength": 512,
        "visibleWhen": {"serviceKind": "portal"},
    },
    "doorState": {
        "valueType": "list",
        "tooltip": "Whether this door or room entrance can currently be entered.",
        "options": list(DOOR_STATE_OPTIONS),
    },
    "requiredKeyId": {
        "valueType": "text",
        "tooltip": "Optional key id required to unlock this locked door.",
        "maxLength": 80,
        "visibleWhen": {"doorState": "locked"},
    },
    "keyLocationHint": {
        "valueType": "text",
        "tooltip": "Optional spoken hint for where the matching key might be.",
        "maxLength": 160,
        "visibleWhen": {"doorState": "locked"},
    },
    "portalState": {
        "valueType": "list",
        "tooltip": "Whether this portal is currently open or closed.",
        "options": list(PORTAL_STATE_OPTIONS),
        "visibleWhen": {"serviceKind": "portal"},
    },
    "portalOpenSeconds": {
        "valueType": "number",
        "tooltip": "Seconds this portal stays open before closing. Set 0 for no timed cycle.",
        "range": {"min": 0, "max": 86400, "step": 1},
        "visibleWhen": {"serviceKind": "portal"},
    },
    "portalClosedSeconds": {
        "valueType": "number",
        "tooltip": "Seconds this portal stays closed before opening. Set 0 for no timed cycle.",
        "range": {"min": 0, "max": 86400, "step": 1},
        "visibleWhen": {"serviceKind": "portal"},
    },
    "softwareAuthor": {
        "valueType": "text",
        "tooltip": "Author, publisher, or project owner credited for this software.",
        "maxLength": 120,
    },
    "verificationStatus": {
        "valueType": "list",
        "tooltip": "Catalog trust marker for this software entry.",
        "options": list(VERIFICATION_STATUS_OPTIONS),
    },
    "verificationAvailableAt": {
        "valueType": "number",
        "tooltip": "Server timestamp when an unverified user-created link becomes usable.",
        "range": {"min": 0, "max": 9999999999999, "step": 1},
    },
    "description": {
        "valueType": "text",
        "tooltip": "Short description spoken when inspecting or using the link.",
        "maxLength": 240,
    },
    "launchMessage": {
        "valueType": "text",
        "tooltip": "Optional custom message spoken when this link is used.",
        "maxLength": 240,
    },
    "enabled": {
        "valueType": "boolean",
        "tooltip": "Turns this link item on or off.",
    },
    "emitRange": {
        "valueType": "number",
        "tooltip": "Maximum distance in squares for this link's emitted sound.",
        "range": {"min": 1, "max": 20, "step": 1},
    },
    "emitVolume": {
        "valueType": "number",
        "tooltip": "Emitted sound volume percent.",
        "range": {"min": 0, "max": 100, "step": 1},
    },
    "emitSoundSpeed": {
        "valueType": "number",
        "tooltip": "Playback speed/pitch percent for emitted sound. 50 is normal.",
        "range": {"min": 0, "max": 100, "step": 0.1},
    },
    "emitSoundTempo": {
        "valueType": "number",
        "tooltip": "Playback tempo percent for emitted sound. 50 is normal.",
        "range": {"min": 0, "max": 100, "step": 0.1},
    },
    "emitInitialDelay": {
        "valueType": "number",
        "tooltip": "Delay in seconds before emitted audio starts after this link is enabled.",
        "range": {"min": 0, "max": 300, "step": 0.1},
    },
    "emitLoopDelay": {
        "valueType": "number",
        "tooltip": "Delay in seconds between each emitted playback.",
        "range": {"min": 0, "max": 300, "step": 0.1},
    },
    "useSound": {
        "valueType": "sound",
        "tooltip": "Sound played when this link, door, house, or portal is used.",
        "maxLength": 2048,
    },
    "emitSound": {
        "valueType": "sound",
        "tooltip": "Looping proximity sound emitted from this link on the grid.",
        "maxLength": 2048,
    },
}
