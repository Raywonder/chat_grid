"""QR code item static metadata and defaults."""

from __future__ import annotations

LABEL = "QR code"
TOOLTIP = "A scannable or speakable QR code marker for links, text, contacts, Wi-Fi notes, payments, or eCrypto references."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "qrLabel",
    "payloadKind",
    "payload",
    "description",
    "enabled",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 8
DIRECTIONAL = False
DEFAULT_TITLE = "QR code"
DEFAULT_PARAMS: dict = {
    "qrLabel": "QR code",
    "payloadKind": "url",
    "payload": "",
    "description": "",
    "enabled": True,
}
PARAM_KEYS: tuple[str, ...] = (
    "qrLabel",
    "payloadKind",
    "payload",
    "description",
    "enabled",
)
PAYLOAD_KIND_OPTIONS: tuple[str, ...] = (
    "url",
    "text",
    "contact",
    "wifi",
    "payment",
    "ecrypto",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {"valueType": "text", "tooltip": "Display name for this QR item.", "maxLength": 80},
    "qrLabel": {"valueType": "text", "tooltip": "Human label spoken before the QR payload.", "maxLength": 80},
    "payloadKind": {
        "valueType": "list",
        "tooltip": "What the QR payload represents.",
        "options": list(PAYLOAD_KIND_OPTIONS),
    },
    "payload": {"valueType": "text", "tooltip": "The QR code payload or destination text.", "maxLength": 2048},
    "description": {"valueType": "text", "tooltip": "Short explanation for this QR code.", "maxLength": 240},
    "enabled": {"valueType": "boolean", "tooltip": "Turns this QR code on or off."},
}
