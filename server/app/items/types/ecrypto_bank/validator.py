"""eCrypto bank item validation and normalization."""

from __future__ import annotations

from ....network_security import validate_media_reference
from ....models import WorldItem
from ...helpers import keep_only_known_params, parse_bool_like
from ...sound_policy import (
    enforce_max_length,
    normalize_media_reference,
    normalize_sound_reference,
)
from .definition import PARAM_KEYS, SERVICE_SCOPE_OPTIONS


def _clean_text(value: object, *, max_length: int, field_name: str) -> str:
    """Normalize one bank text field."""

    return enforce_max_length(
        str(value or "").strip(), max_length=max_length, field_name=field_name
    )


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize eCrypto bank params."""

    next_params["bankName"] = _clean_text(
        next_params.get("bankName", item.params.get("bankName", "Crypto eCrypto Bank")),
        max_length=120,
        field_name="bankName",
    ) or "Crypto eCrypto Bank"
    next_params["enabled"] = parse_bool_like(
        next_params.get("enabled", item.params.get("enabled", True)), default=True
    )
    scope = str(
        next_params.get("serviceScope", item.params.get("serviceScope", "wallets_transfers"))
    ).strip().lower()
    if scope not in SERVICE_SCOPE_OPTIONS:
        raise ValueError(
            "serviceScope must be one of wallets, wallets_transfers, deposits_withdrawals, full_service, information_only."
        )
    next_params["serviceScope"] = scope
    try:
        emit_range = int(next_params.get("emitRange", item.params.get("emitRange", 10)))
    except (TypeError, ValueError) as exc:
        raise ValueError("emitRange must be an integer between 1 and 20.") from exc
    if not (1 <= emit_range <= 20):
        raise ValueError("emitRange must be between 1 and 20.")
    next_params["emitRange"] = emit_range

    try:
        emit_volume = int(
            next_params.get("emitVolume", item.params.get("emitVolume", 42))
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

    url = enforce_max_length(
        normalize_media_reference(next_params.get("url", item.params.get("url", ""))),
        max_length=2048,
        field_name="url",
    )
    next_params["url"] = validate_media_reference(url, field_name="url")
    next_params["targetLocation"] = _clean_text(
        next_params.get("targetLocation", item.params.get("targetLocation", "ecrypto_bank_lobby")),
        max_length=80,
        field_name="targetLocation",
    )
    next_params["description"] = _clean_text(
        next_params.get("description", item.params.get("description", "")),
        max_length=360,
        field_name="description",
    )
    next_params["accessNote"] = _clean_text(
        next_params.get("accessNote", item.params.get("accessNote", "")),
        max_length=500,
        field_name="accessNote",
    )
    next_params["emitSound"] = enforce_max_length(
        normalize_sound_reference(
            next_params.get(
                "emitSound",
                item.params.get(
                    "emitSound",
                    "sounds/ambience/ecrypto_bank_lobby.ogg?v=20260714-ecrypto-bank",
                ),
            )
        ),
        max_length=2048,
        field_name="emitSound",
    )
    return keep_only_known_params(next_params, PARAM_KEYS)
