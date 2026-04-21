"""Wheel item static metadata and defaults."""

from __future__ import annotations

LABEL = "wheel"
TOOLTIP = "Spin to win fabulous prizes."
EDITABLE_PROPERTIES: tuple[str, ...] = ("title", "spaces")
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND = "sounds/spin.ogg"
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 4000
EMIT_RANGE = 15
DIRECTIONAL = False
DEFAULT_TITLE = "wheel"
DEFAULT_PARAMS: dict = {"spaces": "yes, no"}
PARAM_KEYS: tuple[str, ...] = ("spaces",)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Display name spoken and shown for this item.",
        "maxLength": 80,
    },
    "spaces": {
        "valueType": "text",
        "tooltip": "Comma-delimited list of wheel spaces. Example: yes, no, maybe.",
        "maxLength": 4000,
    },
}
