"""Shed item static metadata and defaults."""

from __future__ import annotations

LABEL = "shed"
TOOLTIP = "A small storage or utility shed marker."
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
DEFAULT_TITLE = "shed"
DEFAULT_PARAMS: dict = {
    "placeName": "Shed",
    "ownerName": "",
    "doorState": "unlocked",
    "targetLocation": "",
    "description": "A small storage shed.",
    "zoneNotes": "front door, tools, storage shelves",
    "welcomeMessage": "You open the shed.",
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
    "title": {"valueType": "text", "tooltip": "Display name for this shed.", "maxLength": 80},
    "placeName": {"valueType": "text", "tooltip": "Shed name.", "maxLength": 80},
    "ownerName": {"valueType": "text", "tooltip": "Optional owner or group.", "maxLength": 80},
    "doorState": {"valueType": "list", "tooltip": "Whether this shed can be entered.", "options": ["unlocked", "locked"]},
    "targetLocation": {"valueType": "text", "tooltip": "Optional Chat Grid location id entered when this shed is used.", "maxLength": 64},
    "description": {"valueType": "text", "tooltip": "Short shed description.", "maxLength": 360},
    "zoneNotes": {"valueType": "text", "tooltip": "Useful areas inside or around the shed.", "maxLength": 500},
    "welcomeMessage": {"valueType": "text", "tooltip": "Spoken when the unlocked shed is used.", "maxLength": 240},
}
