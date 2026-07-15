"""Radio item validation/normalization."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from ....network_security import validate_media_reference
from ....models import WorldItem
from ...sound_policy import (
    enforce_max_length,
    normalize_media_reference,
    normalize_sound_reference,
)
from ...helpers import keep_only_known_params
from .definition import (
    CHANNEL_OPTIONS,
    EFFECT_OPTIONS,
    PARAM_KEYS,
    SPEAKER_ROLE_OPTIONS,
    VISIBILITY_OPTIONS,
)


def _normalize_preset_stream_reference(value: str, *, field_name: str) -> str:
    """Normalize one saved preset without live DNS checks.

    Station preset lists are dormant catalog data. A retired third-party hostname
    should not make every other preset unusable; the selected stream is still
    passed through `validate_media_reference` before playback.
    """

    text = value.strip()
    if not text:
        return ""
    parts = urlsplit(text)
    if parts.scheme:
        scheme = parts.scheme.lower()
        if scheme not in {"http", "https"}:
            raise ValueError(f"{field_name} must use http or https.")
        if parts.username is not None or parts.password is not None:
            raise ValueError(f"{field_name} must not include credentials.")
        if not parts.hostname:
            raise ValueError(f"{field_name} must be a valid http/https URL.")
        netloc = parts.hostname.lower()
        if ":" in netloc and not netloc.startswith("["):
            netloc = f"[{netloc}]"
        if parts.port is not None:
            netloc = f"{netloc}:{parts.port}"
        return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment))
    if parts.netloc:
        raise ValueError(f"{field_name} must use http or https when specifying a host.")
    if text.startswith("/") or text.startswith("sounds/"):
        return text
    raise ValueError(
        f"{field_name} must be an absolute http/https URL, site-relative path, or sounds/ path."
    )


def _validate_selected_stream_reference(value: str, *, field_name: str) -> str:
    """Validate the stream URL that is actually selected for playback."""

    text = value.strip()
    if not text:
        return ""
    if text.startswith("sounds/"):
        return text
    parts = urlsplit(text)
    if parts.scheme:
        return _normalize_preset_stream_reference(text, field_name=field_name)
    return validate_media_reference(text, field_name=field_name)


def _normalize_station_presets(raw_value: object) -> list[dict[str, str]]:
    """Return a sanitized station preset list from persisted/server params."""

    if not isinstance(raw_value, list):
        return []
    presets: list[dict[str, str]] = []
    for entry in raw_value[:100]:
        if not isinstance(entry, dict):
            continue
        title = enforce_max_length(
            str(entry.get("title") or entry.get("name") or "").strip(),
            max_length=120,
            field_name="stationPresets.title",
        )
        url = enforce_max_length(
            normalize_media_reference(
                entry.get("streamUrl") or entry.get("url") or ""
            ),
            max_length=2048,
            field_name="stationPresets.streamUrl",
        )
        if not title or not url:
            continue
        preset = {
            "title": title,
            "streamUrl": _normalize_preset_stream_reference(
                url, field_name="stationPresets.streamUrl"
            ),
        }
        switch_sound = normalize_sound_reference(
            entry.get("switchSound") or entry.get("stationSwitchSound") or ""
        )
        if switch_sound:
            switch_sound = enforce_max_length(
                switch_sound,
                max_length=2048,
                field_name="stationPresets.switchSound",
            )
            if switch_sound.startswith(("http://", "https://")):
                switch_sound = validate_media_reference(
                    switch_sound, field_name="stationPresets.switchSound"
                )
            preset["switchSound"] = switch_sound
        presets.append(preset)
    return presets


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize radio params."""

    def param_value(key: str, fallback: object) -> object:
        """Return an updated value, preserving the existing radio setting by default."""

        if key in next_params:
            return next_params[key]
        return item.params.get(key, fallback)

    # Presets are server/persisted data. Client updates preserve the existing list.
    presets = _normalize_station_presets(item.params.get("stationPresets", []))
    if not presets:
        presets = _normalize_station_presets(next_params.get("stationPresets", []))
    next_params["stationPresets"] = presets

    try:
        station_index = int(next_params.get("stationIndex", item.params.get("stationIndex", 0)))
    except (TypeError, ValueError) as exc:
        raise ValueError("stationIndex must be a number.") from exc
    if presets:
        station_index %= len(presets)
        next_params["streamUrl"] = presets[station_index]["streamUrl"]
    elif not (0 <= station_index <= 99):
        raise ValueError("stationIndex must be between 0 and 99.")
    next_params["stationIndex"] = station_index

    next_params["streamUrl"] = enforce_max_length(
        normalize_media_reference(next_params.get("streamUrl", "")),
        max_length=2048,
        field_name="streamUrl",
    )
    next_params["streamUrl"] = _validate_selected_stream_reference(
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

    enabled_value = param_value("enabled", True)
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
        media_volume = int(param_value("mediaVolume", 50))
    except (TypeError, ValueError) as exc:
        raise ValueError("mediaVolume must be a number.") from exc
    if not (0 <= media_volume <= 1000):
        raise ValueError("mediaVolume must be between 0 and 1000.")
    next_params["mediaVolume"] = media_volume

    effect = str(param_value("mediaEffect", "off")).strip().lower()
    if effect not in EFFECT_OPTIONS:
        raise ValueError(
            "mediaEffect must be one of reverb, echo, flanger, high_pass, low_pass, off."
        )
    next_params["mediaEffect"] = effect

    channel = str(param_value("mediaChannel", "stereo")).strip().lower()
    if channel not in CHANNEL_OPTIONS:
        raise ValueError("mediaChannel must be one of stereo, mono, left, right.")
    next_params["mediaChannel"] = channel

    speaker_role = str(param_value("speakerRole", "primary")).strip().lower()
    if speaker_role in {"bass", "subwoofer"}:
        speaker_role = "sub"
    elif speaker_role in {"hi", "treble"}:
        speaker_role = "high"
    elif speaker_role in {"high_low", "highlow", "hi_low_bass", "hilowbass"}:
        speaker_role = "high_low_bass"
    if speaker_role not in SPEAKER_ROLE_OPTIONS:
        raise ValueError(
            "speakerRole must be one of primary, sub, low, mid, high, high_low_bass."
        )
    next_params["speakerRole"] = speaker_role

    group = str(param_value("linkedMediaGroup", "")).strip()
    next_params["linkedMediaGroup"] = enforce_max_length(
        group, max_length=80, field_name="linkedMediaGroup"
    )

    sync_value = param_value("syncWithPrimary", False)
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

    visibility = str(param_value("itemVisibility", "shown")).strip().lower()
    if visibility in {"hidden", "hide", "quiet", "silent"}:
        visibility = "quiet"
    if visibility not in VISIBILITY_OPTIONS:
        raise ValueError("itemVisibility must be shown or quiet.")
    next_params["itemVisibility"] = visibility

    switch_sound = normalize_sound_reference(param_value("stationSwitchSound", ""))
    if switch_sound:
        switch_sound = enforce_max_length(
            switch_sound, max_length=2048, field_name="stationSwitchSound"
        )
        if switch_sound.startswith(("http://", "https://")):
            switch_sound = validate_media_reference(
                switch_sound, field_name="stationSwitchSound"
            )
    next_params["stationSwitchSound"] = switch_sound

    try:
        effect_value = float(param_value("mediaEffectValue", 50))
    except (TypeError, ValueError) as exc:
        raise ValueError("mediaEffectValue must be a number.") from exc
    if not (0 <= effect_value <= 100):
        raise ValueError("mediaEffectValue must be between 0 and 100.")
    next_params["mediaEffectValue"] = round(effect_value, 1)
    # Read-only metadata fields are server-managed and cannot be client-edited.
    if presets:
        next_params["stationName"] = presets[station_index]["title"][:160]
        next_params["nowPlaying"] = str(next_params.get("nowPlaying", "")).strip()[
            :200
        ]
    else:
        next_params["stationName"] = str(item.params.get("stationName", "")).strip()[
            :160
        ]
        next_params["nowPlaying"] = str(item.params.get("nowPlaying", "")).strip()[
            :200
        ]

    try:
        play_started_at = int(
            param_value("playStartedAt", 0) or 0
        )
    except (TypeError, ValueError):
        play_started_at = 0
    next_params["playStartedAt"] = max(0, play_started_at)

    try:
        facing = float(param_value("facing", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("facing must be a number between 0 and 360.") from exc
    if not (0 <= facing <= 360):
        raise ValueError("facing must be between 0 and 360.")
    next_params["facing"] = int(round(facing))

    try:
        emit_range = int(param_value("emitRange", 10))
    except (TypeError, ValueError) as exc:
        raise ValueError("emitRange must be an integer between 5 and 20.") from exc
    if not (5 <= emit_range <= 20):
        raise ValueError("emitRange must be between 5 and 20.")
    next_params["emitRange"] = emit_range
    next_params["surfaceId"] = enforce_max_length(
        str(param_value("surfaceId", "") or "").strip(),
        max_length=128,
        field_name="surfaceId",
    )
    next_params["surfaceTitle"] = enforce_max_length(
        str(param_value("surfaceTitle", "") or "").strip(),
        max_length=80,
        field_name="surfaceTitle",
    )
    try:
        surface_order = int(param_value("surfaceOrder", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("surfaceOrder must be an integer between 0 and 20.") from exc
    if not (0 <= surface_order <= 20):
        raise ValueError("surfaceOrder must be between 0 and 20.")
    next_params["surfaceOrder"] = surface_order
    return keep_only_known_params(next_params, PARAM_KEYS)
