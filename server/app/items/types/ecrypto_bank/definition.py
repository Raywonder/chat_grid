"""eCrypto bank item static metadata and defaults."""

from __future__ import annotations

LABEL = "eCrypto bank"
TOOLTIP = "A bank-style service counter for each user's eCrypto wallet, balances, transfers, deposits, and related actions."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "bankName",
    "serviceScope",
    "targetLocation",
    "url",
    "description",
    "accessNote",
)
CAPABILITIES: tuple[str, ...] = ("editable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = "sounds/ambience/ecrypto_bank_lobby.ogg?v=20260714-ecrypto-bank"
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 12
DIRECTIONAL = False
DEFAULT_TITLE = "eCrypto bank"
DEFAULT_PARAMS: dict = {
    "bankName": "Crypto eCrypto Bank",
    "enabled": True,
    "serviceScope": "wallets_transfers",
    "emitRange": 10,
    "emitVolume": 42,
    "emitSoundSpeed": 50,
    "emitSoundTempo": 50,
    "emitInitialDelay": 0,
    "emitLoopDelay": 0,
    "url": "",
    "targetLocation": "ecrypto_bank_lobby",
    "description": "A town service point for user eCrypto activity.",
    "accessNote": "Use this bank for wallet, balance, transfer, deposit, withdrawal, and eCrypto account tasks when those services are connected.",
    "emitSound": "sounds/ambience/ecrypto_bank_lobby.ogg?v=20260714-ecrypto-bank",
}
PARAM_KEYS: tuple[str, ...] = (
    "bankName",
    "enabled",
    "serviceScope",
    "emitRange",
    "emitVolume",
    "emitSoundSpeed",
    "emitSoundTempo",
    "emitInitialDelay",
    "emitLoopDelay",
    "url",
    "targetLocation",
    "description",
    "accessNote",
    "emitSound",
)
SERVICE_SCOPE_OPTIONS: tuple[str, ...] = (
    "wallets",
    "wallets_transfers",
    "deposits_withdrawals",
    "full_service",
    "information_only",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {"valueType": "text", "tooltip": "Display name for this bank item.", "maxLength": 80},
    "bankName": {"valueType": "text", "tooltip": "Bank or service counter name.", "maxLength": 120},
    "enabled": {"valueType": "boolean", "tooltip": "Turns this bank service item on or off."},
    "serviceScope": {
        "valueType": "list",
        "tooltip": "What eCrypto work this bank counter represents.",
        "options": list(SERVICE_SCOPE_OPTIONS),
    },
    "emitRange": {
        "valueType": "number",
        "tooltip": "Maximum distance in squares for the bank lobby ambience.",
        "range": {"min": 1, "max": 20, "step": 1},
    },
    "emitVolume": {
        "valueType": "number",
        "tooltip": "Bank lobby ambience volume percent.",
        "range": {"min": 0, "max": 100, "step": 1},
    },
    "emitSoundSpeed": {
        "valueType": "number",
        "tooltip": "Playback speed/pitch percent for the bank ambience. 50 is normal.",
        "range": {"min": 0, "max": 100, "step": 0.1},
    },
    "emitSoundTempo": {
        "valueType": "number",
        "tooltip": "Playback tempo percent for the bank ambience. 50 is normal.",
        "range": {"min": 0, "max": 100, "step": 0.1},
    },
    "emitInitialDelay": {
        "valueType": "number",
        "tooltip": "Delay in seconds before bank ambience starts.",
        "range": {"min": 0, "max": 300, "step": 0.1},
    },
    "emitLoopDelay": {
        "valueType": "number",
        "tooltip": "Delay in seconds between each bank ambience playback.",
        "range": {"min": 0, "max": 300, "step": 0.1},
    },
    "url": {"valueType": "text", "tooltip": "Optional internal or public URL for the eCrypto service.", "maxLength": 2048},
    "targetLocation": {
        "valueType": "text",
        "tooltip": "Optional walk-in bank lobby location opened by secondary use.",
        "maxLength": 80,
    },
    "description": {"valueType": "text", "tooltip": "Short bank description.", "maxLength": 360},
    "accessNote": {"valueType": "text", "tooltip": "Instructions or boundaries for using this eCrypto bank.", "maxLength": 500},
    "emitSound": {
        "valueType": "sound",
        "tooltip": "Looping bank lobby ambience. Filename assumes sounds folder, or use full URL.",
        "maxLength": 2048,
    },
}
