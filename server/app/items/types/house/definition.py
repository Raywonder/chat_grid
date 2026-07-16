"""House item static metadata and defaults."""

from __future__ import annotations

LABEL = "house"
TOOLTIP = (
    "A placeable front door people can build, name, lock, unlock, "
    "and use as their own house marker."
)
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "houseName",
    "ownerName",
    "doorState",
    "targetLocation",
    "requiredKeyId",
    "keyLocationHint",
    "description",
    "welcomeMessage",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = "sounds/teleport_start.ogg"
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 12
DIRECTIONAL = False
DEFAULT_TITLE = "house"
DEFAULT_PARAMS: dict = {
    "houseName": "My house",
    "ownerName": "",
    "doorState": "unlocked",
    "targetLocation": "",
    "requiredKeyId": "",
    "keyLocationHint": "",
    "description": "A user-built house.",
    "welcomeMessage": "Welcome home.",
}
PARAM_KEYS: tuple[str, ...] = (
    "houseName",
    "ownerName",
    "doorState",
    "targetLocation",
    "requiredKeyId",
    "keyLocationHint",
    "description",
    "welcomeMessage",
)

DOOR_STATE_OPTIONS: tuple[str, ...] = ("unlocked", "locked")

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Short display name spoken and shown for this house item.",
        "maxLength": 80,
    },
    "houseName": {
        "valueType": "text",
        "label": "House name",
        "tooltip": "Name of the house people see and hear.",
        "maxLength": 80,
    },
    "ownerName": {
        "valueType": "text",
        "label": "Owner name",
        "tooltip": "Optional owner or family name for this house.",
        "maxLength": 80,
    },
    "doorState": {
        "valueType": "list",
        "label": "Door state",
        "tooltip": (
            "Locked houses announce that the door is locked; "
            "unlocked houses welcome visitors."
        ),
        "options": list(DOOR_STATE_OPTIONS),
    },
    "targetLocation": {
        "valueType": "text",
        "label": "Interior location",
        "tooltip": (
            "Optional Chat Grid location id entered when this house door is used. "
            "Blank creates a connected house interior automatically."
        ),
        "maxLength": 64,
    },
    "requiredKeyId": {
        "valueType": "text",
        "label": "Required key id",
        "tooltip": "Optional key id required to unlock this locked house door.",
        "maxLength": 80,
        "visibleWhen": {"doorState": "locked"},
    },
    "keyLocationHint": {
        "valueType": "text",
        "label": "Key location hint",
        "tooltip": "Optional spoken hint for where the matching key might be.",
        "maxLength": 160,
        "visibleWhen": {"doorState": "locked"},
    },
    "description": {
        "valueType": "text",
        "tooltip": "Short description spoken when someone checks the house.",
        "maxLength": 240,
    },
    "welcomeMessage": {
        "valueType": "text",
        "label": "Welcome message",
        "tooltip": "Message spoken when someone uses an unlocked house.",
        "maxLength": 240,
    },
}
