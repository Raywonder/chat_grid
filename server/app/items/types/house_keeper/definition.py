"""House keeper item static metadata and defaults."""

from __future__ import annotations

LABEL = "house keeper"
TOOLTIP = "A small opt-in house helper agent that checks in-world house items and can repair common modeled problems such as radios not working."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "keeperName",
    "houseName",
    "repairMode",
    "backgroundChecksEnabled",
    "checkIntervalHours",
    "targetKinds",
    "authorizedNames",
    "voicePrompt",
    "description",
    "lastAutoCheckAt",
    "lastAutoCheckSummary",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = "sounds/actions/ui-confirm.mp3"
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 10
DIRECTIONAL = False
DEFAULT_TITLE = "house keeper"
REPAIR_MODE_OPTIONS: tuple[str, ...] = ("inspect", "auto_repair")
DEFAULT_PARAMS: dict = {
    "keeperName": "House keeper",
    "houseName": "My house",
    "repairMode": "auto_repair",
    "backgroundChecksEnabled": True,
    "checkIntervalHours": 6,
    "targetKinds": "radio, object",
    "authorizedNames": "",
    "voicePrompt": "I can check house radios and household items when someone asks.",
    "description": "A small helper agent for in-world house repairs.",
    "lastAutoCheckAt": 0,
    "lastAutoCheckSummary": "",
}
PARAM_KEYS: tuple[str, ...] = (
    "keeperName",
    "houseName",
    "repairMode",
    "backgroundChecksEnabled",
    "checkIntervalHours",
    "targetKinds",
    "authorizedNames",
    "voicePrompt",
    "description",
    "lastAutoCheckAt",
    "lastAutoCheckSummary",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Short display name spoken and shown for this helper.",
        "maxLength": 80,
    },
    "keeperName": {
        "valueType": "text",
        "label": "Keeper name",
        "tooltip": "Name this little house keeper answers to.",
        "maxLength": 80,
    },
    "houseName": {
        "valueType": "text",
        "label": "House name",
        "tooltip": "House or room this keeper looks after.",
        "maxLength": 80,
    },
    "repairMode": {
        "valueType": "list",
        "label": "Repair mode",
        "tooltip": "Inspect reports issues; auto repair fixes common in-world item state when used.",
        "options": list(REPAIR_MODE_OPTIONS),
    },
    "backgroundChecksEnabled": {
        "valueType": "boolean",
        "label": "Background checks",
        "tooltip": "Allow this keeper to run quiet in-world checks on its schedule.",
    },
    "checkIntervalHours": {
        "valueType": "number",
        "label": "Check interval hours",
        "tooltip": "How many hours between quiet in-world keeper checks.",
        "range": {"min": 1, "max": 168, "step": 1},
    },
    "targetKinds": {
        "valueType": "text",
        "label": "Target kinds",
        "tooltip": "Comma-separated in-world things this keeper can check, such as radio and object.",
        "maxLength": 160,
    },
    "authorizedNames": {
        "valueType": "text",
        "label": "Authorized names",
        "tooltip": "Optional comma-separated names allowed to ask this keeper for repairs. Blank means anyone in the room may ask.",
        "maxLength": 240,
    },
    "voicePrompt": {
        "valueType": "text",
        "label": "Voice prompt",
        "tooltip": "Short spoken helper prompt.",
        "maxLength": 240,
    },
    "description": {
        "valueType": "text",
        "tooltip": "Short spoken description.",
        "maxLength": 240,
    },
    "lastAutoCheckAt": {
        "valueType": "number",
        "label": "Last auto check",
        "tooltip": "Server-managed Unix millisecond timestamp for the last scheduled keeper check.",
        "range": {"min": 0, "max": 9999999999999, "step": 1},
    },
    "lastAutoCheckSummary": {
        "valueType": "text",
        "label": "Last auto check summary",
        "tooltip": "Server-managed summary of the most recent scheduled keeper check.",
        "maxLength": 240,
    },
}
