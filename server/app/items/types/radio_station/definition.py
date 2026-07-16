"""Radio item static metadata and defaults."""

from __future__ import annotations

LABEL = "radio"
TOOLTIP = "Can play stations from the Internet. Tune multiple to the same station and they will sync up."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "streamUrl",
    "stationIndex",
    "enabled",
    "speakerRole",
    "linkedMediaGroup",
    "syncWithPrimary",
    "itemVisibility",
    "stationSwitchSound",
    "mediaVolume",
    "mediaChannel",
    "mediaEffect",
    "mediaEffectValue",
    "facing",
    "emitRange",
    "surfaceId",
    "surfaceTitle",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 10
DIRECTIONAL = True
DEFAULT_TITLE = "radio"
DEFAULT_PARAMS: dict = {
    "streamUrl": "",
    "playbackUrl": "",
    "enabled": True,
    "stationIndex": 0,
    "stationPresets": [],
    "mediaVolume": 50,
    "mediaChannel": "stereo",
    "mediaEffect": "off",
    "mediaEffectValue": 50,
    "speakerRole": "primary",
    "linkedMediaGroup": "",
    "syncWithPrimary": False,
    "itemVisibility": "shown",
    "stationSwitchSound": "",
    "stationName": "",
    "nowPlaying": "",
    "playStartedAt": 0,
    "facing": 0,
    "emitRange": 10,
    "surfaceId": "",
    "surfaceTitle": "",
    "surfaceOrder": 0,
}
PARAM_KEYS: tuple[str, ...] = (
    "streamUrl",
    "playbackUrl",
    "enabled",
    "stationIndex",
    "stationPresets",
    "mediaVolume",
    "mediaChannel",
    "mediaEffect",
    "mediaEffectValue",
    "speakerRole",
    "linkedMediaGroup",
    "syncWithPrimary",
    "itemVisibility",
    "stationSwitchSound",
    "stationName",
    "nowPlaying",
    "playStartedAt",
    "facing",
    "emitRange",
    "surfaceId",
    "surfaceTitle",
    "surfaceOrder",
)

CHANNEL_OPTIONS: tuple[str, ...] = ("stereo", "mono", "left", "right")
SPEAKER_ROLE_OPTIONS: tuple[str, ...] = (
    "primary",
    "sub",
    "low",
    "mid",
    "high",
    "high_low_bass",
)
VISIBILITY_OPTIONS: tuple[str, ...] = ("shown", "quiet")
EFFECT_OPTIONS: tuple[str, ...] = (
    "reverb",
    "echo",
    "flanger",
    "high_pass",
    "low_pass",
    "off",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Display name spoken and shown for this item.",
        "maxLength": 80,
    },
    "streamUrl": {
        "valueType": "text",
        "tooltip": "Audio stream URL or supported station page used by this radio.",
        "maxLength": 2048,
    },
    "playbackUrl": {
        "valueType": "text",
        "tooltip": "Server-resolved playback URL for supported station pages.",
    },
    "enabled": {
        "valueType": "boolean",
        "tooltip": "Power switch for this radio.",
    },
    "stationIndex": {
        "valueType": "number",
        "label": "Station knob",
        "tooltip": "Station preset number. Use left/right here or Shift+Enter on the radio to tune.",
        "range": {"min": 0, "max": 99, "step": 1},
    },
    "stationPresets": {
        "valueType": "text",
        "label": "Station presets",
        "tooltip": "Server-managed station preset list for bundled radios.",
    },
    "mediaVolume": {
        "valueType": "number",
        "tooltip": "Playback media volume percent for this radio or speaker. Values above 100 can boost a quiet speaker.",
        "range": {"min": 0, "max": 1000, "step": 1},
    },
    "mediaChannel": {
        "valueType": "list",
        "tooltip": "Select how the station audio channels are rendered.",
        "options": list(CHANNEL_OPTIONS),
    },
    "mediaEffect": {
        "valueType": "list",
        "tooltip": "Select the active radio effect.",
        "options": list(EFFECT_OPTIONS),
    },
    "mediaEffectValue": {
        "valueType": "number",
        "tooltip": "Amount for the selected effect.",
        "range": {"min": 0, "max": 100, "step": 0.1},
        "visibleWhen": {"mediaEffect": "!off"},
    },
    "speakerRole": {
        "valueType": "list",
        "label": "Speaker role",
        "tooltip": "Audio filter role for this linked media item.",
        "options": list(SPEAKER_ROLE_OPTIONS),
    },
    "linkedMediaGroup": {
        "valueType": "text",
        "label": "Linked media group",
        "tooltip": "Shared group name used to sync related primary, sub, low, mid, and high media items. In the browser, Enter opens nearby linked speaker systems so users do not have to type the group key.",
        "maxLength": 80,
    },
    "syncWithPrimary": {
        "valueType": "boolean",
        "label": "Sync with primary",
        "tooltip": "Use the primary item in this linked group as the shared media source.",
        "visibleWhen": {"linkedMediaGroup": "!"},
    },
    "itemVisibility": {
        "valueType": "list",
        "label": "Item visibility",
        "tooltip": "Quiet items stay playable but are omitted from ordinary nearby item lists.",
        "options": list(VISIBILITY_OPTIONS),
    },
    "stationSwitchSound": {
        "valueType": "text",
        "label": "Station switch sound",
        "tooltip": "Optional sound file played when this radio tunes to a station.",
        "maxLength": 2048,
    },
    "stationName": {
        "valueType": "text",
        "tooltip": "Detected station name from stream metadata.",
    },
    "nowPlaying": {
        "valueType": "text",
        "tooltip": "Detected current track/title from stream metadata.",
    },
    "facing": {
        "valueType": "number",
        "tooltip": "Facing direction in degrees used for directional emit.",
        "range": {"min": 0, "max": 360, "step": 1},
        "visibleWhen": {"directional": True},
    },
    "emitRange": {
        "valueType": "number",
        "tooltip": "Maximum distance in squares for this radio's emitted audio.",
        "range": {"min": 5, "max": 20, "step": 1},
    },
    "surfaceId": {
        "valueType": "text",
        "label": "Surface id",
        "tooltip": "Server-managed id of the shelf, table, counter, or other surface holding this radio.",
        "maxLength": 80,
    },
    "surfaceTitle": {
        "valueType": "text",
        "label": "Surface title",
        "tooltip": "Server-managed display name of the surface holding this radio.",
        "maxLength": 120,
    },
    "surfaceOrder": {
        "valueType": "number",
        "label": "Surface order",
        "tooltip": "Server-managed left-to-right or shelf order for radios sitting on the same surface.",
        "range": {"min": 0, "max": 20, "step": 1},
    },
}
