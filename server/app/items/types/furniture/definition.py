"""Furniture item static metadata and defaults."""

from __future__ import annotations

LABEL = "furniture"
TOOLTIP = "Tables, chairs, beds, shelves, counters, and other house surfaces people can use or place things on."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "furnitureKind",
    "material",
    "style",
    "condition",
    "supportsObjects",
    "surfaceSlots",
    "seatingCapacity",
    "postureMode",
    "surfaceNote",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 10
DIRECTIONAL = False
DEFAULT_TITLE = "table"
FURNITURE_KIND_OPTIONS: tuple[str, ...] = (
    "table",
    "chair",
    "couch",
    "bench",
    "desk",
    "shelf",
    "counter",
    "cabinet",
    "bed",
    "nightstand",
    "dresser",
    "plant_stand",
    "rug",
)
MATERIAL_OPTIONS: tuple[str, ...] = (
    "wood",
    "glass",
    "metal",
    "stone",
    "fabric",
    "plastic",
    "mixed",
)
CONDITION_OPTIONS: tuple[str, ...] = ("new", "good", "worn", "damaged", "broken")
POSTURE_MODE_OPTIONS: tuple[str, ...] = ("none", "sit", "lie", "sit_lie", "lean")
DEFAULT_PARAMS: dict = {
    "furnitureKind": "table",
    "material": "wood",
    "style": "warm home",
    "condition": "good",
    "supportsObjects": True,
    "surfaceSlots": 4,
    "seatingCapacity": 0,
    "postureMode": "none",
    "surfaceNote": "A steady surface for everyday things.",
}
PARAM_KEYS: tuple[str, ...] = (
    "furnitureKind",
    "material",
    "style",
    "condition",
    "supportsObjects",
    "surfaceSlots",
    "seatingCapacity",
    "postureMode",
    "surfaceNote",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Display name spoken and shown for this furniture.",
        "maxLength": 80,
    },
    "furnitureKind": {
        "valueType": "list",
        "label": "Furniture kind",
        "tooltip": "Physical furniture role.",
        "options": list(FURNITURE_KIND_OPTIONS),
    },
    "material": {
        "valueType": "list",
        "tooltip": "Main material used for texture and breakage flavor.",
        "options": list(MATERIAL_OPTIONS),
    },
    "style": {
        "valueType": "text",
        "tooltip": "Short style or mood description.",
        "maxLength": 120,
    },
    "condition": {
        "valueType": "list",
        "tooltip": "Current furniture condition.",
        "options": list(CONDITION_OPTIONS),
    },
    "supportsObjects": {
        "valueType": "boolean",
        "label": "Supports objects",
        "tooltip": "Whether house objects can be placed on this furniture.",
    },
    "surfaceSlots": {
        "valueType": "number",
        "label": "Surface slots",
        "tooltip": "How many house objects can sit on this surface.",
        "range": {"min": 0, "max": 20, "step": 1},
        "visibleWhen": {"supportsObjects": True},
    },
    "postureMode": {
        "valueType": "list",
        "label": "Posture mode",
        "tooltip": "Whether people can sit, lie, or lean here.",
        "options": list(POSTURE_MODE_OPTIONS),
    },
    "seatingCapacity": {
        "valueType": "number",
        "label": "Seating capacity",
        "tooltip": "How many people can sit here at the same time. Use 0 for display-only furniture.",
        "range": {"min": 0, "max": 6, "step": 1},
        "visibleWhen": {"postureMode": "sit"},
    },
    "surfaceNote": {
        "valueType": "text",
        "label": "Surface note",
        "tooltip": "Spoken detail for what belongs here.",
        "maxLength": 240,
    },
}
