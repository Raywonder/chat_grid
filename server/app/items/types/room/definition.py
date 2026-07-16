"""Room item static metadata and defaults."""

from __future__ import annotations

LABEL = "room"
TOOLTIP = "A room marker, including one-room studio apartment layouts with named zones in the same room."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "placeName",
    "ownerName",
    "roomLayout",
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
DEFAULT_TITLE = "room"
DEFAULT_PARAMS: dict = {
    "placeName": "Room",
    "ownerName": "",
    "roomLayout": "single_room_studio",
    "doorState": "unlocked",
    "targetLocation": "",
    "description": "A configurable room.",
    "zoneNotes": "bed corner, kitchen corner, bathroom corner, closet corner, living area, front door",
    "welcomeMessage": "You enter the room.",
}
PARAM_KEYS: tuple[str, ...] = (
    "placeName",
    "ownerName",
    "roomLayout",
    "doorState",
    "targetLocation",
    "description",
    "zoneNotes",
    "welcomeMessage",
)
ROOM_LAYOUT_OPTIONS: tuple[str, ...] = (
    "single_room_studio",
    "open_plan",
    "bedroom",
    "bathroom",
    "kitchen",
    "living_room",
    "closet",
    "utility",
    "custom",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {"valueType": "text", "tooltip": "Display name spoken and shown for this room.", "maxLength": 80},
    "placeName": {"valueType": "text", "tooltip": "Room name.", "maxLength": 80},
    "ownerName": {"valueType": "text", "tooltip": "Optional room owner or group.", "maxLength": 80},
    "roomLayout": {
        "valueType": "list",
        "tooltip": "Room layout model. Single-room studio keeps all zones inside one room.",
        "options": list(ROOM_LAYOUT_OPTIONS),
    },
    "doorState": {
        "valueType": "list",
        "tooltip": "Whether this room entrance can currently be entered.",
        "options": ["unlocked", "locked"],
    },
    "targetLocation": {
        "valueType": "text",
        "tooltip": "Optional Chat Grid location id entered when this room is used.",
        "maxLength": 64,
    },
    "description": {"valueType": "text", "tooltip": "Short room description.", "maxLength": 360},
    "zoneNotes": {
        "valueType": "text",
        "tooltip": "Named zones inside this room, such as bed corner, kitchen corner, bathroom corner, closet, living area, and front door.",
        "maxLength": 500,
    },
    "welcomeMessage": {"valueType": "text", "tooltip": "Spoken when the unlocked room is used.", "maxLength": 240},
}
