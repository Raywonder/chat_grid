"""Counter item static metadata and defaults."""

from __future__ import annotations

LABEL = "counter"
TOOLTIP = "Simple incrementing counter."
EDITABLE_PROPERTIES: tuple[str, ...] = ("title", "value")
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 15
DIRECTIONAL = False
DEFAULT_TITLE = "counter"
DEFAULT_PARAMS: dict = {"value": 0}
PARAM_KEYS: tuple[str, ...] = ("value",)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {"valueType": "text", "tooltip": "Display name.", "maxLength": 80},
    "value": {
        "valueType": "number",
        "tooltip": "Current value.",
        "range": {"min": 0, "max": 9999, "step": 1},
    },
}
