"""Radio item validation/normalization."""

from __future__ import annotations

from ....network_security import validate_media_reference
from ....models import WorldItem
from ...sound_policy import enforce_max_length, normalize_media_reference
from ...helpers import keep_only_known_params
from .definition import (
    CHANNEL_OPTIONS,
    EFFECT_OPTIONS,
    PARAM_KEYS,
    SPEAKER_ROLE_OPTIONS,
    VISIBILITY_OPTIONS,
)


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize radio params."""

    next_params["streamUrl"] = enforce_max_length(
        normalize_media_reference(next_params.get("streamUrl", "")),
        max_length=2048,
        field_name="streamUrl",
    )
    next_params["streamUrl"] = validate_media_reference(
        next_params["streamUrl"], field_name="streamUrl"
    )
    # Read-only resolved playback URL is server-managed and cannot be client-edited.
    current_stream_url = str(item.params.get("streamUrl", "")).strip()
    if next_params["streamUrl"] == current_stream_url:
        next_params["playbackUrl"] = str(item.params.get("playbackUrl", "")).strip()[
            :2048
        ]
    else:
        next_params["playbackUrl"] = ""

    enabled_value = next_params.get("enabled", True)
    if isinstance(enabled_value, bool):
        enabled = enabled_value
    elif isinstance(enabled_value, (int, float)):
        enabled = bool(enabled_value)
    elif isinstance(enabled_value, str):
        token = enabled_value.strip().lower()
        if token in {"on", "true", "1", "yes"}:
            enabled = True
        elif token in {"off", "false", "0", "no"}:
            enabled = False
        else:
            raise ValueError("enabled must be true/false or on/off.")
    else:
        raise ValueError("enabled must be true/false or on/off.")
    next_params["enabled"] = enabled

    try:
        media_volume = int(next_params.get("mediaVolume", 50))
    except (TypeError, ValueError) as exc:
        raise ValueError("mediaVolume must be a number.") from exc
    if not (0 <= media_volume <= 100):
        raise ValueError("mediaVolume must be between 0 and 100.")
    next_params["mediaVolume"] = media_volume

    effect = str(next_params.get("mediaEffect", "off")).strip().lower()
    if effect not in EFFECT_OPTIONS:
        raise ValueError(
            "mediaEffect must be one of reverb, echo, flanger, high_pass, low_pass, off."
        )
    next_params["mediaEffect"] = effect

    channel = str(next_params.get("mediaChannel", "stereo")).strip().lower()
    if channel not in CHANNEL_OPTIONS:
        raise ValueError("mediaChannel must be one of stereo, mono, left, right.")
    next_params["mediaChannel"] = channel

    speaker_role = str(next_params.get("speakerRole", "primary")).strip().lower()
    if speaker_role in {"low", "bass", "subwoofer"}:
        speaker_role = "sub"
    elif speaker_role in {"hi", "treble"}:
        speaker_role = "high"
    elif speaker_role in {"high_low", "highlow", "hi_low_bass", "hilowbass"}:
        speaker_role = "high_low_bass"
    if speaker_role not in SPEAKER_ROLE_OPTIONS:
        raise ValueError(
            "speakerRole must be one of primary, sub, mid, high, high_low_bass."
        )
    next_params["speakerRole"] = speaker_role

    group = str(next_params.get("linkedMediaGroup", "")).strip()
    next_params["linkedMediaGroup"] = enforce_max_length(
        group, max_length=80, field_name="linkedMediaGroup"
    )

    sync_value = next_params.get("syncWithPrimary", False)
    if isinstance(sync_value, bool):
        sync_with_primary = sync_value
    elif isinstance(sync_value, (int, float)):
        sync_with_primary = bool(sync_value)
    elif isinstance(sync_value, str):
        token = sync_value.strip().lower()
        if token in {"on", "true", "1", "yes"}:
            sync_with_primary = True
        elif token in {"off", "false", "0", "no", ""}:
            sync_with_primary = False
        else:
            raise ValueError("syncWithPrimary must be true/false or on/off.")
    else:
        raise ValueError("syncWithPrimary must be true/false or on/off.")
    next_params["syncWithPrimary"] = sync_with_primary

    visibility = str(next_params.get("itemVisibility", "shown")).strip().lower()
    if visibility in {"hidden", "hide", "quiet", "silent"}:
        visibility = "quiet"
    if visibility not in VISIBILITY_OPTIONS:
        raise ValueError("itemVisibility must be shown or quiet.")
    next_params["itemVisibility"] = visibility

    try:
        effect_value = float(next_params.get("mediaEffectValue", 50))
    except (TypeError, ValueError) as exc:
        raise ValueError("mediaEffectValue must be a number.") from exc
    if not (0 <= effect_value <= 100):
        raise ValueError("mediaEffectValue must be between 0 and 100.")
    next_params["mediaEffectValue"] = round(effect_value, 1)
    # Read-only metadata fields are server-managed and cannot be client-edited.
    next_params["stationName"] = str(item.params.get("stationName", "")).strip()[:160]
    next_params["nowPlaying"] = str(item.params.get("nowPlaying", "")).strip()[:200]

    try:
        facing = float(next_params.get("facing", item.params.get("facing", 0)))
    except (TypeError, ValueError) as exc:
        raise ValueError("facing must be a number between 0 and 360.") from exc
    if not (0 <= facing <= 360):
        raise ValueError("facing must be between 0 and 360.")
    next_params["facing"] = int(round(facing))

    try:
        emit_range = int(next_params.get("emitRange", item.params.get("emitRange", 10)))
    except (TypeError, ValueError) as exc:
        raise ValueError("emitRange must be an integer between 5 and 20.") from exc
    if not (5 <= emit_range <= 20):
        raise ValueError("emitRange must be between 5 and 20.")
    next_params["emitRange"] = emit_range
    return keep_only_known_params(next_params, PARAM_KEYS)
