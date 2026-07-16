"""Billboard item validation and normalization."""

from __future__ import annotations

from ....network_security import validate_media_reference
from ....models import WorldItem
from ...helpers import keep_only_known_params, parse_bool_like
from ...sound_policy import (
    enforce_max_length,
    normalize_media_reference,
    normalize_sound_reference,
)
from .definition import BILLBOARD_MODE_OPTIONS, ITEM_VISIBILITY_OPTIONS, PARAM_KEYS


def _bounded_text(raw: object, *, field_name: str, max_length: int) -> str:
    """Normalize one billboard text field and enforce its maximum length."""

    return enforce_max_length(
        str(raw or "").strip(), max_length=max_length, field_name=field_name
    )


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize billboard params."""

    next_params["enabled"] = parse_bool_like(
        next_params.get("enabled", item.params.get("enabled", True)), default=True
    )

    mode = (
        str(next_params.get("billboardMode", item.params.get("billboardMode", "interactive")))
        .strip()
        .lower()
    )
    if mode not in BILLBOARD_MODE_OPTIONS:
        raise ValueError(
            "billboardMode must be one of interactive, display_only, audio_only."
        )
    next_params["billboardMode"] = mode

    visibility = (
        str(next_params.get("itemVisibility", item.params.get("itemVisibility", "visible")))
        .strip()
        .lower()
    )
    if visibility not in ITEM_VISIBILITY_OPTIONS:
        raise ValueError("itemVisibility must be visible or hidden.")
    next_params["itemVisibility"] = visibility

    next_params["headline"] = _bounded_text(
        next_params.get("headline", item.params.get("headline", "")),
        field_name="headline",
        max_length=120,
    )
    next_params["body"] = _bounded_text(
        next_params.get("body", item.params.get("body", "")),
        field_name="body",
        max_length=360,
    )
    url = enforce_max_length(
        normalize_media_reference(next_params.get("url", item.params.get("url", ""))),
        max_length=2048,
        field_name="url",
    )
    next_params["url"] = validate_media_reference(url, field_name="url")
    next_params["announcementText"] = _bounded_text(
        next_params.get("announcementText", item.params.get("announcementText", "")),
        field_name="announcementText",
        max_length=500,
    )
    next_params["voiceName"] = _bounded_text(
        next_params.get("voiceName", item.params.get("voiceName", "")),
        field_name="voiceName",
        max_length=80,
    )
    voice_asset_url = normalize_sound_reference(
        next_params.get("voiceAssetUrl", item.params.get("voiceAssetUrl", ""))
    )
    if voice_asset_url:
        voice_asset_url = enforce_max_length(
            voice_asset_url, max_length=2048, field_name="voiceAssetUrl"
        )
        if voice_asset_url.startswith(("http://", "https://")):
            voice_asset_url = validate_media_reference(
                voice_asset_url, field_name="voiceAssetUrl"
            )
    next_params["voiceAssetUrl"] = voice_asset_url
    next_params["bannerText"] = _bounded_text(
        next_params.get("bannerText", item.params.get("bannerText", "")),
        field_name="bannerText",
        max_length=500,
    )

    try:
        rotation_seconds = int(
            next_params.get("rotationSeconds", item.params.get("rotationSeconds", 12))
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("rotationSeconds must be an integer between 3 and 300.") from exc
    if not (3 <= rotation_seconds <= 300):
        raise ValueError("rotationSeconds must be between 3 and 300.")
    next_params["rotationSeconds"] = rotation_seconds

    try:
        emit_range = int(next_params.get("emitRange", item.params.get("emitRange", 12)))
    except (TypeError, ValueError) as exc:
        raise ValueError("emitRange must be an integer between 1 and 20.") from exc
    if not (1 <= emit_range <= 20):
        raise ValueError("emitRange must be between 1 and 20.")
    next_params["emitRange"] = emit_range

    return keep_only_known_params(next_params, PARAM_KEYS)
