"""Portable eCrypto wallet item static metadata and defaults."""

from __future__ import annotations

LABEL = "eCrypto wallet"
TOOLTIP = (
    "A portable crypto wallet object a user can pick up, carry, drop, inspect, "
    "or use as an in-world wallet marker."
)
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "walletName",
    "networkMode",
    "chain",
    "address",
    "walletLabel",
    "custodyMode",
    "description",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 8
DIRECTIONAL = False
DEFAULT_TITLE = "eCrypto wallet"
DEFAULT_PARAMS: dict = {
    "walletName": "Pocket eCrypto wallet",
    "networkMode": "test",
    "chain": "ecrypto-test",
    "address": "",
    "walletLabel": "",
    "custodyMode": "carried",
    "description": "A portable wallet marker you can carry on the grid.",
    "enabled": True,
}
PARAM_KEYS: tuple[str, ...] = (
    "walletName",
    "networkMode",
    "chain",
    "address",
    "walletLabel",
    "custodyMode",
    "description",
    "enabled",
)
NETWORK_MODE_OPTIONS: tuple[str, ...] = ("test", "real")
CUSTODY_MODE_OPTIONS: tuple[str, ...] = ("carried", "account_link", "cold_storage", "watch_only")

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {"valueType": "text", "tooltip": "Display name for this wallet item.", "maxLength": 80},
    "walletName": {"valueType": "text", "tooltip": "Name spoken for this portable wallet.", "maxLength": 120},
    "networkMode": {
        "valueType": "list",
        "tooltip": "Whether this wallet marker represents test-chain or real-chain details.",
        "options": list(NETWORK_MODE_OPTIONS),
    },
    "chain": {"valueType": "text", "tooltip": "Chain identifier, such as ecrypto-test or bitcoin.", "maxLength": 80},
    "address": {"valueType": "text", "tooltip": "Optional wallet address or account pointer.", "maxLength": 240},
    "walletLabel": {"valueType": "text", "tooltip": "Optional short label for the wallet address.", "maxLength": 120},
    "custodyMode": {
        "valueType": "list",
        "tooltip": "How this in-world wallet should be treated.",
        "options": list(CUSTODY_MODE_OPTIONS),
    },
    "description": {"valueType": "text", "tooltip": "Short wallet description.", "maxLength": 360},
    "enabled": {"valueType": "boolean", "tooltip": "Turns this wallet marker on or off."},
}
