"""Widget item static metadata and defaults."""

from __future__ import annotations

LABEL = "widget"
TOOLTIP = "A basic item. Make it a beacon or whatever you want."
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "enabled",
    "directional",
    "facing",
    "emitRange",
    "emitVolume",
    "emitSoundSpeed",
    "emitSoundTempo",
    "emitInitialDelay",
    "emitLoopDelay",
    "emitEffect",
    "emitEffectValue",
    "ambienceScope",
    "ambienceName",
    "ambiencePriority",
    "useSound",
    "emitSound",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 15
DIRECTIONAL = False
DEFAULT_TITLE = "widget"
DEFAULT_PARAMS: dict = {
    "enabled": True,
    "directional": False,
    "facing": 0,
    "emitRange": 15,
    "emitVolume": 100,
    "emitSoundSpeed": 50,
    "emitSoundTempo": 50,
    "emitInitialDelay": 0,
    "emitLoopDelay": 0,
    "emitEffect": "off",
    "emitEffectValue": 50,
    "ambienceScope": "tile",
    "ambienceName": "",
    "ambiencePriority": 50,
    "useSound": "",
    "emitSound": "",
}
PARAM_KEYS: tuple[str, ...] = (
    "enabled",
    "directional",
    "facing",
    "emitRange",
    "emitVolume",
    "emitSoundSpeed",
    "emitSoundTempo",
    "emitInitialDelay",
    "emitLoopDelay",
    "emitEffect",
    "emitEffectValue",
    "ambienceScope",
    "ambienceName",
    "ambiencePriority",
    "useSound",
    "emitSound",
)
EFFECT_OPTIONS: tuple[str, ...] = (
    "reverb",
    "echo",
    "flanger",
    "high_pass",
    "low_pass",
    "off",
)
AMBIENCE_SCOPE_OPTIONS: tuple[str, ...] = ("tile", "location", "off")

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Display name spoken and shown for this item.",
        "maxLength": 80,
    },
    "enabled": {"valueType": "boolean", "tooltip": "Turns this widget on or off."},
    "directional": {
        "valueType": "boolean",
        "tooltip": "If on, emitted sound favors the facing direction.",
    },
    "facing": {
        "valueType": "number",
        "tooltip": "Facing direction in degrees used when directional is on.",
        "range": {"min": 0, "max": 360, "step": 1},
        "visibleWhen": {"directional": True},
    },
    "emitRange": {
        "valueType": "number",
        "tooltip": "Maximum distance in squares for emitted sound.",
        "range": {"min": 1, "max": 20, "step": 1},
    },
    "emitVolume": {
        "valueType": "number",
        "tooltip": "Emitted sound volume percent.",
        "range": {"min": 0, "max": 100, "step": 1},
    },
    "emitSoundSpeed": {
        "valueType": "number",
        "tooltip": "Playback speed/pitch percent for emitted sound. 50 is normal, 0 is half, 100 is double. Using speed and tempo together may sound weird.",
        "range": {"min": 0, "max": 100, "step": 0.1},
    },
    "emitSoundTempo": {
        "valueType": "number",
        "tooltip": "Playback tempo percent for emitted sound. 50 is normal, 0 is half, 100 is double. Using speed and tempo together may sound weird.",
        "range": {"min": 0, "max": 100, "step": 0.1},
    },
    "emitInitialDelay": {
        "valueType": "number",
        "tooltip": "Delay in seconds before emitted audio starts after this sound is enabled.",
        "range": {"min": 0, "max": 300, "step": 0.1},
    },
    "emitLoopDelay": {
        "valueType": "number",
        "tooltip": "Delay in seconds between each playing of this audio.",
        "range": {"min": 0, "max": 300, "step": 0.1},
    },
    "emitEffect": {
        "valueType": "list",
        "tooltip": "Effect applied to emitted sound.",
        "options": list(EFFECT_OPTIONS),
    },
    "emitEffectValue": {
        "valueType": "number",
        "tooltip": "Amount for emit effect.",
        "range": {"min": 0, "max": 100, "step": 0.1},
    },
    "ambienceScope": {
        "valueType": "list",
        "label": "Ambience scope",
        "tooltip": "Choose whether this stream plays from its tile, fills the whole current location as ambience, or stays silent.",
        "options": list(AMBIENCE_SCOPE_OPTIONS),
    },
    "ambienceName": {
        "valueType": "text",
        "label": "Ambience name",
        "tooltip": "Optional spoken name when this widget is used as the location ambience.",
        "maxLength": 80,
        "visibleWhen": {"ambienceScope": "location"},
    },
    "ambiencePriority": {
        "valueType": "number",
        "label": "Ambience priority",
        "tooltip": "When more than one widget offers location ambience, the highest priority wins.",
        "range": {"min": 0, "max": 100, "step": 1},
        "visibleWhen": {"ambienceScope": "location"},
    },
    "useSound": {
        "valueType": "sound",
        "tooltip": "Sound played on use. Filename assumes sounds folder, or use full URL.",
        "maxLength": 2048,
    },
    "emitSound": {
        "valueType": "sound",
        "tooltip": "Looping emitted sound. Filename assumes sounds folder, or use full URL.",
        "maxLength": 2048,
    },
}
