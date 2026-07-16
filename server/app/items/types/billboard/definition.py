"""Billboard item static metadata and defaults."""

from __future__ import annotations

LABEL = "billboard"
TOOLTIP = (
    "A visible or audio-only announcement surface for promos, links, banners, "
    "and short spoken notices."
)
EDITABLE_PROPERTIES: tuple[str, ...] = (
    "title",
    "enabled",
    "billboardMode",
    "itemVisibility",
    "headline",
    "body",
    "url",
    "announcementText",
    "voiceName",
    "voiceAssetUrl",
    "bannerText",
    "rotationSeconds",
    "emitRange",
)
CAPABILITIES: tuple[str, ...] = ("editable", "carryable", "deletable", "usable")
USE_SOUND: str | None = None
EMIT_SOUND: str | None = None
USE_COOLDOWN_MS = 1000
EMIT_RANGE = 12
DIRECTIONAL = False
DEFAULT_TITLE = "billboard"
DEFAULT_PARAMS: dict = {
    "enabled": True,
    "billboardMode": "interactive",
    "itemVisibility": "visible",
    "headline": "",
    "body": "",
    "url": "",
    "announcementText": "",
    "voiceName": "",
    "voiceAssetUrl": "",
    "bannerText": "",
    "rotationSeconds": 12,
    "emitRange": 12,
}
PARAM_KEYS: tuple[str, ...] = (
    "enabled",
    "billboardMode",
    "itemVisibility",
    "headline",
    "body",
    "url",
    "announcementText",
    "voiceName",
    "voiceAssetUrl",
    "bannerText",
    "rotationSeconds",
    "emitRange",
)

BILLBOARD_MODE_OPTIONS: tuple[str, ...] = (
    "interactive",
    "display_only",
    "audio_only",
)
ITEM_VISIBILITY_OPTIONS: tuple[str, ...] = (
    "visible",
    "hidden",
)

PROPERTY_METADATA: dict[str, dict[str, object]] = {
    "title": {
        "valueType": "text",
        "tooltip": "Display name spoken and shown for this billboard.",
        "maxLength": 80,
    },
    "enabled": {
        "valueType": "boolean",
        "tooltip": "Turns this billboard announcement on or off.",
    },
    "billboardMode": {
        "valueType": "list",
        "tooltip": "Interactive links can be used; display-only is read-only; audio-only is for spoken notices.",
        "options": list(BILLBOARD_MODE_OPTIONS),
    },
    "itemVisibility": {
        "valueType": "list",
        "tooltip": "Visible billboards draw on the grid; hidden billboards can still be heard.",
        "options": list(ITEM_VISIBILITY_OPTIONS),
    },
    "headline": {
        "valueType": "text",
        "tooltip": "Main billboard headline.",
        "maxLength": 120,
    },
    "body": {
        "valueType": "text",
        "tooltip": "Short billboard body text or promo copy.",
        "maxLength": 360,
    },
    "url": {
        "valueType": "text",
        "tooltip": "Optional public or site-relative link shown by an interactive billboard.",
        "maxLength": 2048,
    },
    "announcementText": {
        "valueType": "text",
        "tooltip": "Text intended to be spoken by a voice announcement.",
        "maxLength": 500,
    },
    "voiceName": {
        "valueType": "text",
        "tooltip": "Optional voice label for authored announcements.",
        "maxLength": 80,
    },
    "voiceAssetUrl": {
        "valueType": "text",
        "tooltip": "Optional real voice MP3/OGG path or URL played spatially from the billboard.",
        "maxLength": 2048,
    },
    "bannerText": {
        "valueType": "text",
        "tooltip": "Optional rotating banner copy. Separate multiple banners with |.",
        "maxLength": 500,
    },
    "rotationSeconds": {
        "valueType": "number",
        "tooltip": "Seconds between rotating banner lines.",
        "range": {"min": 3, "max": 300, "step": 1},
    },
    "emitRange": {
        "valueType": "number",
        "tooltip": "Maximum distance in squares where this billboard announcement can be heard.",
        "range": {"min": 1, "max": 20, "step": 1},
    },
}
