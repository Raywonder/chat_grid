"""Cabin item static metadata and defaults."""

from __future__ import annotations

LABEL = "cabin"
TOOLTIP = "A small cabin or retreat marker."
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
EMIT_RANGE = 12
DIRECTIONAL = False
DEFAULT_TITLE = "cabin"
DEFAULT_PARAMS: dict = {
    "placeName": "Cabin",
    "ownerName": "",
    "doorState": "unlocked",
    "targetLocation": "",
    "description": "A small cabin or retreat.",
    "zoneNotes": "front door, sleeping area, hearth, kitchen nook",
    "welcomeMessage": "You enter the cabin.",
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
    "title": {"valueType": "text", "tooltip": "Display name for this cabin.", "maxLength": 80},
    "placeName": {"valueType": "text", "tooltip": "Cabin name.", "maxLength": 80},
    "ownerName": {"valueType": "text", "tooltip": "Optional owner or group.", "maxLength": 80},
    "doorState": {"valueType": "list", "tooltip": "Whether this cabin can be entered.", "options": ["unlocked", "locked"]},
    "targetLocation": {"valueType": "text", "tooltip": "Optional Endiginous location id entered when this cabin is used.", "maxLength": 64},
    "description": {"valueType": "text", "tooltip": "Short cabin description.", "maxLength": 360},
    "zoneNotes": {"valueType": "text", "tooltip": "Useful areas inside or around the cabin.", "maxLength": 500},
    "welcomeMessage": {"valueType": "text", "tooltip": "Spoken when the unlocked cabin is used.", "maxLength": 240},
}
