"""Dice item static metadata and defaults."""

from __future__ import annotations

LABEL = "dice"
TOOLTIP = "Great for drinking games or boredom."
EDITABLE_PROPERTIES: tuple[str, ...] = ("title", "sides", "number")
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND = "sounds/roll.ogg"
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 15
DIRECTIONAL = False
DEFAULT_TITLE = "Dice"
DEFAULT_PARAMS: dict = {"sides": 6, "number": 2}
PARAM_KEYS: tuple[str, ...] = ("sides", "number")

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Display name spoken and shown for this item.",
        "maxLength": 80,
    },
    "sides": {
        "valueType": "number",
        "tooltip": "Number of sides on each die.",
        "range": {"min": 1, "max": 100, "step": 1},
    },
    "number": {
        "valueType": "number",
        "tooltip": "How many dice to roll per use.",
        "range": {"min": 1, "max": 100, "step": 1},
    },
}
