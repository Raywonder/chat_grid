"""House object validation and normalization."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from ....models import WorldItem
from ....network_security import validate_media_reference
from ....world import get_location
from ...helpers import keep_only_known_params, parse_bool_like
from ...sound_policy import (
    enforce_max_length,
    normalize_media_reference,
    normalize_sound_reference,
)
from .definition import (
    CONDITION_OPTIONS,
    EFFECT_OPTIONS,
    FRAGILITY_OPTIONS,
    MATERIAL_OPTIONS,
    OBJECT_KIND_OPTIONS,
    PLACEMENT_OPTIONS,
    PARAM_KEYS,
    WINDOW_STATE_OPTIONS,
)

CHANNEL_OPTIONS: tuple[str, ...] = ("stereo", "mono", "left", "right")
TV_CHANNEL_MODE_OPTIONS: tuple[str, ...] = ("live", "on_demand", "live_and_on_demand")
PHONE_SIDE_OPTIONS: tuple[str, ...] = ("left", "right", "front")
PHONE_AUDIO_MODE_OPTIONS: tuple[str, ...] = ("ear_left", "ear_right", "speaker", "local_only")


def _normalize_preset_stream_reference(value: str, *, field_name: str) -> str:
    """Normalize one saved TV preset without live DNS checks."""

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
    """Validate the TV stream URL that is actually selected for playback."""

    text = value.strip()
    if not text:
        return ""
    if text.startswith("sounds/"):
        return text
    parts = urlsplit(text)
    if parts.scheme:
        return _normalize_preset_stream_reference(text, field_name=field_name)
    return validate_media_reference(text, field_name=field_name)


def _bounded_text(value: object, *, max_length: int, field_name: str) -> str:
    """Normalize a short metadata string field."""

    return enforce_max_length(
        str(value or "").strip(), max_length=max_length, field_name=field_name
    )


def _normalize_station_presets(raw_value: object) -> list[dict[str, str]]:
    """Return a sanitized TV preset list from persisted/server params."""

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
            normalize_media_reference(entry.get("streamUrl") or entry.get("url") or ""),
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
        for key in (
            "sourceType",
            "sourceKey",
            "sourcePath",
            "sourceLabel",
            "playMode",
            "provider",
        ):
            value = _bounded_text(
                entry.get(key), max_length=240, field_name=f"stationPresets.{key}"
            )
            if value:
                preset[key] = value
        presets.append(preset)
    return presets


def _normalize_tv_sources(raw_value: object, *, field_name: str) -> list[dict[str, str]]:
    """Return bounded TV library/provider source metadata entries."""

    if not isinstance(raw_value, list):
        return []
    sources: list[dict[str, str]] = []
    for entry in raw_value[:40]:
        if not isinstance(entry, dict):
            continue
        source: dict[str, str] = {}
        for key in ("key", "title", "kind", "path", "url", "provider", "mode"):
            value = _bounded_text(
                entry.get(key), max_length=512, field_name=f"{field_name}.{key}"
            )
            if value:
                source[key] = value
        if source.get("key") and source.get("title"):
            sources.append(source)
    return sources


def _option(raw: object, fallback: str, options: tuple[str, ...], field_name: str) -> str:
    """Normalize one list option field."""

    value = str(raw or fallback).strip().lower()
    if value not in options:
        raise ValueError(f"{field_name} must be one of {', '.join(options)}.")
    return value


def _money(raw: object, fallback: object, field_name: str) -> int:
    """Normalize one non-negative cost field."""

    try:
        value = int(raw if raw is not None else fallback)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number between 0 and 10000.") from exc
    if not (0 <= value <= 10000):
        raise ValueError(f"{field_name} must be between 0 and 10000.")
    return value


def _number_between(
    raw: object,
    fallback: object,
    field_name: str,
    *,
    minimum: float,
    maximum: float,
    integer: bool = False,
) -> float | int:
    """Normalize one numeric field with inclusive bounds."""

    try:
        value = float(raw if raw is not None else fallback)
    except (TypeError, ValueError) as exc:
        kind = "integer" if integer else "number"
        raise ValueError(
            f"{field_name} must be a {kind} between {minimum:g} and {maximum:g}."
        ) from exc
    if not (minimum <= value <= maximum):
        raise ValueError(f"{field_name} must be between {minimum:g} and {maximum:g}.")
    return int(round(value)) if integer else round(value, 1)


def _validate_location_fit(item: WorldItem, params: dict) -> None:
    """Reject obvious indoor objects from outdoor map locations."""

    location = get_location(item.locationId)
    object_kind = str(params.get("objectKind", "mug")).strip().lower()
    placement = str(params.get("placement", "table")).strip().lower()
    description = str(params.get("description", "") or "").casefold()
    replacement_hint = str(params.get("replacementHint", "") or "").casefold()
    context = f"{description} {replacement_hint}"
    outdoor_locations = {"city", "forest", "town", "houses"}
    indoor_only = {
        "tv",
        "remote",
        "bed",
        "fridge",
        "sink",
        "stove",
        "oven",
        "microwave",
        "curtain",
    }
    furniture_like = {"chair", "couch", "bed", "table", "counter", "shelf"}
    outdoor_ok = any(
        token in context
        for token in ("outdoor", "patio", "porch", "garden", "picnic", "park")
    )
    if object_kind in furniture_like:
        raise ValueError(
            f"{object_kind} should be modeled as furniture, not a house object."
        )
    if location.id in outdoor_locations and object_kind in indoor_only and not outdoor_ok:
        raise ValueError(
            f"{object_kind} belongs indoors here unless the object description or replacement hint clearly says outdoor, patio, porch, garden, or picnic."
        )
    if object_kind == "tv" and placement not in {"wall", "fixture", "furniture"}:
        raise ValueError("TV objects should be wall-mounted or set on furniture.")
    if object_kind == "window" and placement != "wall":
        raise ValueError("Window objects must use wall placement.")
    if object_kind in {"fridge", "stove", "oven", "microwave"} and placement not in {
        "appliance",
        "counter",
        "fixture",
    }:
        raise ValueError(f"{object_kind} objects belong on an appliance, counter, or fixture placement.")
    if object_kind == "sink" and placement not in {"fixture", "counter"}:
        raise ValueError("Sink objects belong in a fixture or counter placement.")


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize house-object params."""

    def param_value(key: str, fallback: object) -> object:
        if key in next_params:
            return next_params[key]
        return item.params.get(key, fallback)

    next_params["objectKind"] = _option(
        next_params.get("objectKind", item.params.get("objectKind", "mug")),
        "mug",
        OBJECT_KIND_OPTIONS,
        "objectKind",
    )
    next_params["placement"] = _option(
        next_params.get("placement", item.params.get("placement", "table")),
        "table",
        PLACEMENT_OPTIONS,
        "placement",
    )
    next_params["material"] = _option(
        next_params.get("material", item.params.get("material", "ceramic")),
        "ceramic",
        MATERIAL_OPTIONS,
        "material",
    )
    next_params["fragility"] = _option(
        next_params.get("fragility", item.params.get("fragility", "normal")),
        "normal",
        FRAGILITY_OPTIONS,
        "fragility",
    )
    next_params["condition"] = _option(
        next_params.get("condition", item.params.get("condition", "intact")),
        "intact",
        CONDITION_OPTIONS,
        "condition",
    )
    next_params["windowState"] = _option(
        next_params.get("windowState", item.params.get("windowState", "closed")),
        "closed",
        WINDOW_STATE_OPTIONS,
        "windowState",
    )
    next_params["ownerName"] = enforce_max_length(
        str(next_params.get("ownerName", item.params.get("ownerName", "")) or "").strip(),
        max_length=80,
        field_name="ownerName",
    )
    next_params["keyId"] = enforce_max_length(
        str(next_params.get("keyId", item.params.get("keyId", "")) or "").strip(),
        max_length=80,
        field_name="keyId",
    )
    next_params["keyFor"] = enforce_max_length(
        str(next_params.get("keyFor", item.params.get("keyFor", "")) or "").strip(),
        max_length=120,
        field_name="keyFor",
    )
    next_params["remoteControlLinkedRadios"] = parse_bool_like(
        next_params.get(
            "remoteControlLinkedRadios",
            item.params.get("remoteControlLinkedRadios", True),
        ),
        default=True,
    )
    next_params["remoteControlLinkedTvs"] = parse_bool_like(
        next_params.get(
            "remoteControlLinkedTvs",
            item.params.get("remoteControlLinkedTvs", True),
        ),
        default=True,
    )
    next_params["surfaceId"] = enforce_max_length(
        str(next_params.get("surfaceId", item.params.get("surfaceId", "")) or "").strip(),
        max_length=128,
        field_name="surfaceId",
    )
    next_params["surfaceTitle"] = enforce_max_length(
        str(
            next_params.get("surfaceTitle", item.params.get("surfaceTitle", "")) or ""
        ).strip(),
        max_length=80,
        field_name="surfaceTitle",
    )
    try:
        surface_order = int(
            next_params.get("surfaceOrder", item.params.get("surfaceOrder", 0)) or 0
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("surfaceOrder must be an integer between 0 and 20.") from exc
    if not (0 <= surface_order <= 20):
        raise ValueError("surfaceOrder must be between 0 and 20.")
    next_params["surfaceOrder"] = surface_order
    next_params["repairCost"] = _money(
        next_params.get("repairCost"), item.params.get("repairCost", 8), "repairCost"
    )
    next_params["purchaseCost"] = _money(
        next_params.get("purchaseCost"),
        item.params.get("purchaseCost", 14),
        "purchaseCost",
    )
    next_params["replacementHint"] = enforce_max_length(
        str(
            next_params.get("replacementHint", item.params.get("replacementHint", ""))
            or ""
        ).strip(),
        max_length=240,
        field_name="replacementHint",
    )
    next_params["giftable"] = parse_bool_like(
        next_params.get("giftable", item.params.get("giftable", True)),
        default=True,
    )
    next_params["description"] = enforce_max_length(
        str(next_params.get("description", item.params.get("description", "")) or "").strip(),
        max_length=240,
        field_name="description",
    )
    next_params["phoneExtension"] = enforce_max_length(
        str(next_params.get("phoneExtension", item.params.get("phoneExtension", "")) or "").strip(),
        max_length=24,
        field_name="phoneExtension",
    )
    next_params["phoneDeviceSide"] = _option(
        next_params.get("phoneDeviceSide", item.params.get("phoneDeviceSide", "front")),
        "front",
        PHONE_SIDE_OPTIONS,
        "phoneDeviceSide",
    )
    next_params["phoneAudioMode"] = _option(
        next_params.get("phoneAudioMode", item.params.get("phoneAudioMode", "ear_left")),
        "ear_left",
        PHONE_AUDIO_MODE_OPTIONS,
        "phoneAudioMode",
    )
    contacts = next_params.get("phoneContacts", item.params.get("phoneContacts", []))
    next_params["phoneContacts"] = contacts[:100] if isinstance(contacts, list) else []
    routes = next_params.get("phonePbxRoutes", item.params.get("phonePbxRoutes", []))
    next_params["phonePbxRoutes"] = routes[:4] if isinstance(routes, list) else []
    object_kind = str(next_params.get("objectKind", "mug")).strip().lower()
    presets = _normalize_station_presets(item.params.get("stationPresets", []))
    if not presets:
        presets = _normalize_station_presets(next_params.get("stationPresets", []))
    next_params["stationPresets"] = presets
    try:
        station_index = int(param_value("stationIndex", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("stationIndex must be a number.") from exc
    if presets:
        station_index %= len(presets)
        next_params["streamUrl"] = presets[station_index]["streamUrl"]
    elif not (0 <= station_index <= 99):
        raise ValueError("stationIndex must be between 0 and 99.")
    next_params["stationIndex"] = station_index

    next_params["streamUrl"] = enforce_max_length(
        normalize_media_reference(param_value("streamUrl", "")),
        max_length=2048,
        field_name="streamUrl",
    )
    if object_kind == "tv":
        next_params["streamUrl"] = _validate_selected_stream_reference(
            next_params["streamUrl"], field_name="streamUrl"
        )
    current_stream_url = str(item.params.get("streamUrl", "")).strip()
    if next_params["streamUrl"] == current_stream_url:
        next_params["playbackUrl"] = str(item.params.get("playbackUrl", "")).strip()[
            :2048
        ]
    else:
        next_params["playbackUrl"] = ""

    next_params["stationName"] = (
        presets[station_index]["title"][:160]
        if presets
        else str(item.params.get("stationName", "")).strip()[:160]
    )
    next_params["nowPlaying"] = str(item.params.get("nowPlaying", "")).strip()[:200]
    next_params["stationSwitchSound"] = enforce_max_length(
        normalize_sound_reference(param_value("stationSwitchSound", "")),
        max_length=2048,
        field_name="stationSwitchSound",
    )
    next_params["linkedMediaGroup"] = enforce_max_length(
        str(param_value("linkedMediaGroup", "") or "").strip(),
        max_length=80,
        field_name="linkedMediaGroup",
    )
    tv_channel_mode = str(
        param_value("tvChannelMode", "live_and_on_demand") or "live_and_on_demand"
    ).strip().lower()
    if tv_channel_mode not in TV_CHANNEL_MODE_OPTIONS:
        raise ValueError(
            "tvChannelMode must be one of live, on_demand, live_and_on_demand."
        )
    next_params["tvChannelMode"] = tv_channel_mode
    next_params["tvLibrarySources"] = _normalize_tv_sources(
        param_value("tvLibrarySources", []), field_name="tvLibrarySources"
    )
    next_params["tvProviderSources"] = _normalize_tv_sources(
        param_value("tvProviderSources", []), field_name="tvProviderSources"
    )
    try:
        play_started_at = int(param_value("playStartedAt", 0) or 0)
    except (TypeError, ValueError):
        play_started_at = 0
    next_params["playStartedAt"] = max(0, play_started_at)

    try:
        media_volume = int(param_value("mediaVolume", 50))
    except (TypeError, ValueError) as exc:
        raise ValueError("mediaVolume must be a number.") from exc
    if not (0 <= media_volume <= 1000):
        raise ValueError("mediaVolume must be between 0 and 1000.")
    next_params["mediaVolume"] = media_volume
    channel = str(param_value("mediaChannel", "stereo")).strip().lower()
    if channel not in CHANNEL_OPTIONS:
        raise ValueError("mediaChannel must be one of stereo, mono, left, right.")
    next_params["mediaChannel"] = channel
    media_effect = str(param_value("mediaEffect", "off")).strip().lower()
    if media_effect not in EFFECT_OPTIONS:
        raise ValueError(
            "mediaEffect must be one of reverb, echo, flanger, high_pass, low_pass, off."
        )
    next_params["mediaEffect"] = media_effect
    next_params["mediaEffectValue"] = _number_between(
        param_value("mediaEffectValue", 50),
        50,
        "mediaEffectValue",
        minimum=0,
        maximum=100,
    )
    try:
        facing = float(param_value("facing", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("facing must be a number between 0 and 360.") from exc
    if not (0 <= facing <= 360):
        raise ValueError("facing must be between 0 and 360.")
    next_params["facing"] = int(round(facing))
    next_params["enabled"] = parse_bool_like(
        next_params.get("enabled", item.params.get("enabled", True)),
        default=True,
    )
    next_params["emitRange"] = _number_between(
        next_params.get("emitRange"),
        item.params.get("emitRange", 6),
        "emitRange",
        minimum=1,
        maximum=20,
        integer=True,
    )
    next_params["emitVolume"] = _number_between(
        next_params.get("emitVolume"),
        item.params.get("emitVolume", 100),
        "emitVolume",
        minimum=0,
        maximum=100,
        integer=True,
    )
    next_params["emitSoundSpeed"] = _number_between(
        next_params.get("emitSoundSpeed"),
        item.params.get("emitSoundSpeed", 50),
        "emitSoundSpeed",
        minimum=0,
        maximum=100,
    )
    next_params["emitSoundTempo"] = _number_between(
        next_params.get("emitSoundTempo"),
        item.params.get("emitSoundTempo", 50),
        "emitSoundTempo",
        minimum=0,
        maximum=100,
    )
    next_params["emitInitialDelay"] = _number_between(
        next_params.get("emitInitialDelay"),
        item.params.get("emitInitialDelay", 0),
        "emitInitialDelay",
        minimum=0,
        maximum=300,
    )
    next_params["emitLoopDelay"] = _number_between(
        next_params.get("emitLoopDelay"),
        item.params.get("emitLoopDelay", 0),
        "emitLoopDelay",
        minimum=0,
        maximum=300,
    )
    emit_effect = (
        str(next_params.get("emitEffect", item.params.get("emitEffect", "off")))
        .strip()
        .lower()
    )
    if emit_effect not in EFFECT_OPTIONS:
        raise ValueError(
            "emitEffect must be one of reverb, echo, flanger, high_pass, low_pass, off."
        )
    next_params["emitEffect"] = emit_effect
    next_params["emitEffectValue"] = _number_between(
        next_params.get("emitEffectValue"),
        item.params.get("emitEffectValue", 50),
        "emitEffectValue",
        minimum=0,
        maximum=100,
    )
    next_params["useSound"] = enforce_max_length(
        normalize_sound_reference(
            next_params.get("useSound", item.params.get("useSound", ""))
        ),
        max_length=2048,
        field_name="useSound",
    )
    next_params["emitSound"] = enforce_max_length(
        normalize_sound_reference(
            next_params.get("emitSound", item.params.get("emitSound", ""))
        ),
        max_length=2048,
        field_name="emitSound",
    )
    _validate_location_fit(item, next_params)
    return keep_only_known_params(next_params, PARAM_KEYS)
