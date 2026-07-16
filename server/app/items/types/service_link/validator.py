"""Interactive link item validation and normalization."""

from __future__ import annotations

from ....network_security import validate_media_reference
from ....models import WorldItem
from ...helpers import keep_only_known_params, parse_bool_like
from ...sound_policy import (
    enforce_max_length,
    normalize_media_reference,
    normalize_sound_reference,
)
from .definition import (
    DOOR_STATE_OPTIONS,
    PARAM_KEYS,
    PORTAL_DESTINATION_MODE_OPTIONS,
    PORTAL_STATE_OPTIONS,
    SERVICE_KIND_OPTIONS,
    VERIFICATION_STATUS_OPTIONS,
)


def _bounded_text(raw: object, *, field_name: str, max_length: int) -> str:
    """Normalize one service text field and enforce its maximum length."""

    return enforce_max_length(
        str(raw or "").strip(), max_length=max_length, field_name=field_name
    )


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize interactive link params."""

    kind = str(
        next_params.get("serviceKind", item.params.get("serviceKind", "service"))
    ).strip().lower()
    if kind not in SERVICE_KIND_OPTIONS:
        raise ValueError(
            "serviceKind must be one of app, door, game, house, room, service, "
            "site, station, tool, portal."
        )
    next_params["serviceKind"] = kind

    url = enforce_max_length(
        normalize_media_reference(next_params.get("url", item.params.get("url", ""))),
        max_length=2048,
        field_name="url",
    )
    next_params["url"] = validate_media_reference(url, field_name="url")
    next_params["targetLocation"] = _bounded_text(
        next_params.get("targetLocation", item.params.get("targetLocation", "")),
        field_name="targetLocation",
        max_length=64,
    ).casefold()
    portal_destination_mode = str(
        next_params.get(
            "portalDestinationMode",
            item.params.get("portalDestinationMode", "random"),
        )
    ).strip().lower()
    if portal_destination_mode not in PORTAL_DESTINATION_MODE_OPTIONS:
        raise ValueError("portalDestinationMode must be random or static.")
    next_params["portalDestinationMode"] = portal_destination_mode
    raw_pool = next_params.get(
        "portalLocationPool", item.params.get("portalLocationPool", "")
    )
    if isinstance(raw_pool, (list, tuple)):
        raw_pool = ",".join(str(entry) for entry in raw_pool)
    pool = _bounded_text(
        raw_pool,
        field_name="portalLocationPool",
        max_length=512,
    )
    next_params["portalLocationPool"] = ",".join(
        token.strip().casefold()
        for token in pool.replace(";", ",").split(",")
        if token.strip()
    )
    door_state = str(
        next_params.get("doorState", item.params.get("doorState", "unlocked"))
    ).strip().lower()
    if door_state not in DOOR_STATE_OPTIONS:
        raise ValueError("doorState must be unlocked or locked.")
    next_params["doorState"] = door_state
    next_params["requiredKeyId"] = _bounded_text(
        next_params.get("requiredKeyId", item.params.get("requiredKeyId", "")),
        field_name="requiredKeyId",
        max_length=80,
    )
    next_params["keyLocationHint"] = _bounded_text(
        next_params.get("keyLocationHint", item.params.get("keyLocationHint", "")),
        field_name="keyLocationHint",
        max_length=160,
    )
    portal_state = str(
        next_params.get("portalState", item.params.get("portalState", "open"))
    ).strip().lower()
    if portal_state not in PORTAL_STATE_OPTIONS:
        raise ValueError("portalState must be open or closed.")
    next_params["portalState"] = portal_state
    for field_name in ("portalOpenSeconds", "portalClosedSeconds"):
        try:
            value = float(next_params.get(field_name, item.params.get(field_name, 0)))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be a number between 0 and 86400."
            ) from exc
        if not (0 <= value <= 86400):
            raise ValueError(f"{field_name} must be between 0 and 86400.")
        next_params[field_name] = int(value) if value.is_integer() else round(value, 1)
    next_params["softwareAuthor"] = _bounded_text(
        next_params.get("softwareAuthor", item.params.get("softwareAuthor", "")),
        field_name="softwareAuthor",
        max_length=120,
    )
    verification_status = str(
        next_params.get(
            "verificationStatus",
            item.params.get("verificationStatus", "author_verified"),
        )
    ).strip().lower()
    if verification_status not in VERIFICATION_STATUS_OPTIONS:
        raise ValueError(
            "verificationStatus must be one of unverified, community_verified, "
            "author_verified, staff_verified."
        )
    next_params["verificationStatus"] = verification_status
    try:
        verification_available_at = int(
            next_params.get(
                "verificationAvailableAt",
                item.params.get("verificationAvailableAt", 0),
            )
            or 0
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("verificationAvailableAt must be a timestamp.") from exc
    if not (0 <= verification_available_at <= 9999999999999):
        raise ValueError("verificationAvailableAt must be a valid timestamp.")
    next_params["verificationAvailableAt"] = verification_available_at
    next_params["description"] = _bounded_text(
        next_params.get("description", item.params.get("description", "")),
        field_name="description",
        max_length=240,
    )
    next_params["launchMessage"] = _bounded_text(
        next_params.get("launchMessage", item.params.get("launchMessage", "")),
        field_name="launchMessage",
        max_length=240,
    )
    next_params["enabled"] = parse_bool_like(
        next_params.get("enabled", item.params.get("enabled", True)), default=True
    )
    try:
        emit_range = int(next_params.get("emitRange", item.params.get("emitRange", 12)))
    except (TypeError, ValueError) as exc:
        raise ValueError("emitRange must be an integer between 1 and 20.") from exc
    if not (1 <= emit_range <= 20):
        raise ValueError("emitRange must be between 1 and 20.")
    next_params["emitRange"] = emit_range

    try:
        emit_volume = int(
            next_params.get("emitVolume", item.params.get("emitVolume", 100))
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("emitVolume must be an integer between 0 and 100.") from exc
    if not (0 <= emit_volume <= 100):
        raise ValueError("emitVolume must be between 0 and 100.")
    next_params["emitVolume"] = emit_volume

    try:
        emit_speed = float(
            next_params.get("emitSoundSpeed", item.params.get("emitSoundSpeed", 50))
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("emitSoundSpeed must be a number between 0 and 100.") from exc
    if not (0 <= emit_speed <= 100):
        raise ValueError("emitSoundSpeed must be between 0 and 100.")
    next_params["emitSoundSpeed"] = round(emit_speed, 1)

    try:
        emit_tempo = float(
            next_params.get("emitSoundTempo", item.params.get("emitSoundTempo", 50))
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("emitSoundTempo must be a number between 0 and 100.") from exc
    if not (0 <= emit_tempo <= 100):
        raise ValueError("emitSoundTempo must be between 0 and 100.")
    next_params["emitSoundTempo"] = round(emit_tempo, 1)

    try:
        emit_initial_delay = float(
            next_params.get("emitInitialDelay", item.params.get("emitInitialDelay", 0))
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "emitInitialDelay must be a number between 0 and 300."
        ) from exc
    if not (0 <= emit_initial_delay <= 300):
        raise ValueError("emitInitialDelay must be between 0 and 300.")
    next_params["emitInitialDelay"] = round(emit_initial_delay, 1)

    try:
        emit_loop_delay = float(
            next_params.get("emitLoopDelay", item.params.get("emitLoopDelay", 0))
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("emitLoopDelay must be a number between 0 and 300.") from exc
    if not (0 <= emit_loop_delay <= 300):
        raise ValueError("emitLoopDelay must be between 0 and 300.")
    next_params["emitLoopDelay"] = round(emit_loop_delay, 1)

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
    return keep_only_known_params(next_params, PARAM_KEYS)
