"""Service/app item static metadata and defaults."""

from __future__ import annotations

LABEL = "service"
TOOLTIP = "Represents one app, site, station hub, or hosted service you can inspect and use."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "serviceKind",
    "url",
    "description",
    "launchMessage",
    "enabled",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 12
DIRECTIONAL = False
DEFAULT_TITLE = "service"
DEFAULT_PARAMS: dict = {
    "serviceKind": "service",
    "url": "",
    "description": "",
    "launchMessage": "",
    "enabled": True,
}
PARAM_KEYS: tuple[str, ...] = (
    "serviceKind",
    "url",
    "description",
    "launchMessage",
    "enabled",
)

SERVICE_KIND_OPTIONS: tuple[str, ...] = (
    "app",
    "game",
    "service",
    "site",
    "station",
    "tool",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Display name spoken and shown for this service item.",
        "maxLength": 80,
    },
    "serviceKind": {
        "valueType": "list",
        "tooltip": "What kind of service this item represents.",
        "options": list(SERVICE_KIND_OPTIONS),
    },
    "url": {
        "valueType": "text",
        "tooltip": "Public or site-relative URL for this service, when it has one.",
        "maxLength": 2048,
    },
    "description": {
        "valueType": "text",
        "tooltip": "Short description spoken when inspecting or using the service.",
        "maxLength": 240,
    },
    "launchMessage": {
        "valueType": "text",
        "tooltip": "Optional custom message spoken when this service is used.",
        "maxLength": 240,
    },
    "enabled": {
        "valueType": "boolean",
        "tooltip": "Turns this service item on or off.",
    },
}
