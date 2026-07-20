"""Shack item static metadata and defaults."""

from __future__ import annotations

LABEL = "shack"
TOOLTIP = "A small rough shelter or simple outbuilding marker."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "placeName",
    "ownerName",
    "doorState",
    "targetLocation",
    "description",
    "zoneNotes",
    "welcomeMessage",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = "sounds/door_soft_loop.ogg"
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 10
DIRECTIONAL = False
DEFAULT_TITLE = "shack"
DEFAULT_PARAMS: dict = {
    "placeName": "Shack",
    "ownerName": "",
    "doorState": "unlocked",
    "targetLocation": "",
    "description": "A small simple shack.",
    "zoneNotes": "front door, open floor, storage corner",
    "welcomeMessage": "You step into the shack.",
}
PARAM_KEYS: tuple[str, ...] = (
    "placeName",
    "ownerName",
    "doorState",
    "targetLocation",
    "description",
    "zoneNotes",
    "welcomeMessage",
)
PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {"valueType": "text", "tooltip": "Display name for this shack.", "maxLength": 80},
    "placeName": {"valueType": "text", "tooltip": "Shack name.", "maxLength": 80},
    "ownerName": {"valueType": "text", "tooltip": "Optional owner or group.", "maxLength": 80},
    "doorState": {"valueType": "list", "tooltip": "Whether this shack can be entered.", "options": ["unlocked", "locked"]},
    "targetLocation": {"valueType": "text", "tooltip": "Optional Endiginous location id entered when this shack is used.", "maxLength": 64},
    "description": {"valueType": "text", "tooltip": "Short shack description.", "maxLength": 360},
    "zoneNotes": {"valueType": "text", "tooltip": "Useful areas inside or around the shack.", "maxLength": 500},
    "welcomeMessage": {"valueType": "text", "tooltip": "Spoken when the unlocked shack is used.", "maxLength": 240},
}
