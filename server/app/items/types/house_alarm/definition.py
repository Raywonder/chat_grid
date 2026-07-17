"""House alarm item static metadata and defaults."""

from __future__ import annotations

LABEL = "house alarm"
TOOLTIP = "A buyable home alarm panel with voiced prompts, siren state, and notification-hook fields for house security."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "alarmName",
    "houseName",
    "ownerName",
    "alarmMode",
    "armedState",
    "codeMode",
    "residentCode",
    "guestCode",
    "disarmCode",
    "duressCode",
    "codeHint",
    "authorizedNames",
    "authorizedUsernames",
    "entryPrompt",
    "alertPrompt",
    "allowPrompt",
    "denyPrompt",
    "notificationMode",
    "ntfyTopic",
    "waNotifyTarget",
    "description",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = "sounds/notify.ogg"
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 14
DIRECTIONAL = False
DEFAULT_TITLE = "alarm panel"
ALARM_MODE_OPTIONS: tuple[str, ...] = ("monitor", "entry_guard", "privacy")
ARMED_STATE_OPTIONS: tuple[str, ...] = ("disarmed", "armed_home", "armed_away", "triggered")
CODE_MODE_OPTIONS: tuple[str, ...] = ("off", "guest", "disarm", "guest_disarm")
NOTIFICATION_MODE_OPTIONS: tuple[str, ...] = ("in_grid", "ntfy", "whatsapp", "ntfy_whatsapp")
DEFAULT_PARAMS: dict = {
    "alarmName": "House alarm",
    "houseName": "My house",
    "ownerName": "",
    "alarmMode": "entry_guard",
    "armedState": "armed_home",
    "codeMode": "off",
    "residentCode": "",
    "accessSetupComplete": False,
    "accessMethod": "account",
    "enrolledUsername": "",
    "guestCode": "",
    "disarmCode": "",
    "duressCode": "",
    "codeHint": "",
    "authorizedNames": "",
    "authorizedUsernames": "",
    "entryPrompt": "Please wait while the house checks whether someone can let you in.",
    "alertPrompt": "House alarm. Someone is at the door.",
    "allowPrompt": "Access allowed. Opening the door.",
    "denyPrompt": "Access denied. Please wait outside.",
    "notificationMode": "in_grid",
    "ntfyTopic": "",
    "waNotifyTarget": "",
    "description": "A voice-enabled house security panel.",
}
PARAM_KEYS: tuple[str, ...] = (
    "alarmName",
    "houseName",
    "ownerName",
    "alarmMode",
    "armedState",
    "codeMode",
    "residentCode",
    "accessSetupComplete",
    "accessMethod",
    "enrolledUsername",
    "guestCode",
    "disarmCode",
    "duressCode",
    "codeHint",
    "authorizedNames",
    "authorizedUsernames",
    "entryPrompt",
    "alertPrompt",
    "allowPrompt",
    "denyPrompt",
    "notificationMode",
    "ntfyTopic",
    "waNotifyTarget",
    "description",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Short display name spoken and shown for this alarm panel.",
        "maxLength": 80,
    },
    "alarmName": {
        "valueType": "text",
        "label": "Alarm name",
        "tooltip": "Name of this alarm system.",
        "maxLength": 80,
    },
    "houseName": {
        "valueType": "text",
        "label": "House name",
        "tooltip": "House this alarm protects.",
        "maxLength": 80,
    },
    "ownerName": {
        "valueType": "text",
        "label": "Owner name",
        "tooltip": "Optional owner or family name for alerts.",
        "maxLength": 80,
    },
    "alarmMode": {
        "valueType": "list",
        "label": "Alarm mode",
        "tooltip": "Monitor only, entry guard, or privacy-focused access control.",
        "options": list(ALARM_MODE_OPTIONS),
    },
    "armedState": {
        "valueType": "list",
        "label": "Armed state",
        "tooltip": "Whether the alarm is disarmed, armed, or actively triggered.",
        "options": list(ARMED_STATE_OPTIONS),
    },
    "codeMode": {
        "valueType": "list",
        "label": "Code mode",
        "tooltip": "Whether in-world keypad codes are off, guest-only, disarm-only, or both. Do not store real home-security secrets here.",
        "options": list(CODE_MODE_OPTIONS),
    },
    "residentCode": {
        "valueType": "text",
        "label": "Resident keypad code",
        "tooltip": "Optional in-world resident entry code enrolled during first-use setup. Never use a real security code.",
        "maxLength": 16,
    },
    "guestCode": {
        "valueType": "text",
        "label": "Guest code",
        "tooltip": "Optional in-world guest entry code. Use only game/test codes, not real security codes.",
        "maxLength": 16,
    },
    "disarmCode": {
        "valueType": "text",
        "label": "Disarm code",
        "tooltip": "Optional in-world code that disarms this alarm panel. Use only game/test codes, not real security codes.",
        "maxLength": 16,
    },
    "duressCode": {
        "valueType": "text",
        "label": "Duress code",
        "tooltip": "Optional in-world code that appears to allow access while still alerting nearby owners.",
        "maxLength": 16,
    },
    "codeHint": {
        "valueType": "text",
        "label": "Code hint",
        "tooltip": "Optional safe hint visitors can hear without revealing the actual code.",
        "maxLength": 120,
    },
    "authorizedNames": {
        "valueType": "text",
        "label": "Authorized names",
        "tooltip": "Comma-separated names that should be treated as already allowed.",
        "maxLength": 240,
    },
    "authorizedUsernames": {
        "valueType": "text",
        "label": "Authorized account usernames",
        "tooltip": "Comma-separated signed-in account usernames allowed through guarded doors. Display names alone are not secure identity.",
        "maxLength": 240,
    },
    "entryPrompt": {
        "valueType": "text",
        "label": "Entry prompt",
        "tooltip": "Voiced text visitors hear when the alarm is armed.",
        "maxLength": 240,
    },
    "alertPrompt": {
        "valueType": "text",
        "label": "Alert prompt",
        "tooltip": "Voiced/in-grid alert text when someone is at the door.",
        "maxLength": 240,
    },
    "allowPrompt": {
        "valueType": "text",
        "label": "Allow prompt",
        "tooltip": "Voiced text for allowed entry.",
        "maxLength": 240,
    },
    "denyPrompt": {
        "valueType": "text",
        "label": "Deny prompt",
        "tooltip": "Voiced text for denied entry.",
        "maxLength": 240,
    },
    "notificationMode": {
        "valueType": "list",
        "label": "Notification mode",
        "tooltip": "Current notification hook mode. External modes are configuration fields until ntfy/WA plugins are wired.",
        "options": list(NOTIFICATION_MODE_OPTIONS),
    },
    "ntfyTopic": {
        "valueType": "text",
        "label": "ntfy topic",
        "tooltip": "Optional ntfy topic name for future real-time push hooks. Do not store secrets here.",
        "maxLength": 120,
        "visibleWhen": {"notificationMode": "!in_grid"},
    },
    "waNotifyTarget": {
        "valueType": "text",
        "label": "WA notify target",
        "tooltip": "Optional approved WhatsApp target label for future OpenClaw notification hooks.",
        "maxLength": 120,
        "visibleWhen": {"notificationMode": "!in_grid"},
    },
    "description": {
        "valueType": "text",
        "tooltip": "Short spoken description.",
        "maxLength": 240,
    },
}
