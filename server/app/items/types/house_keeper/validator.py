"""House keeper validation and normalization."""

from __future__ import annotations

from ....models import WorldItem
from ...helpers import keep_only_known_params
from ...sound_policy import enforce_max_length
from .definition import PARAM_KEYS, REPAIR_MODE_OPTIONS


def _option(raw: object, fallback: str, options: tuple[str, ...], field_name: str) -> str:
    """Normalize one list option field."""

    value = str(raw or fallback).strip().lower()
    if value not in options:
        raise ValueError(f"{field_name} must be one of {', '.join(options)}.")
    return value


def _text(
    item: WorldItem,
    next_params: dict,
    key: str,
    *,
    fallback: str,
    max_length: int,
) -> str:
    """Normalize one bounded text param."""

    return enforce_max_length(
        str(next_params.get(key, item.params.get(key, fallback)) or "").strip(),
        max_length=max_length,
        field_name=key,
    )


def _bool_value(raw: object, fallback: bool) -> bool:
    """Normalize one bool-like keeper option."""

    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        value = raw.strip().casefold()
        if value in {"1", "true", "yes", "on", "enabled"}:
            return True
        if value in {"0", "false", "no", "off", "disabled"}:
            return False
    return fallback


def _int_range(raw: object, fallback: int, *, minimum: int, maximum: int, field_name: str) -> int:
    """Normalize one bounded integer field."""

    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer between {minimum} and {maximum}.") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}.")
    return value


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize house-keeper params."""

    next_params["keeperName"] = _text(
        item, next_params, "keeperName", fallback="House keeper", max_length=80
    )
    next_params["houseName"] = _text(
        item, next_params, "houseName", fallback="My house", max_length=80
    )
    next_params["repairMode"] = _option(
        next_params.get("repairMode", item.params.get("repairMode", "auto_repair")),
        "auto_repair",
        REPAIR_MODE_OPTIONS,
        "repairMode",
    )
    next_params["backgroundChecksEnabled"] = _bool_value(
        next_params.get(
            "backgroundChecksEnabled",
            item.params.get("backgroundChecksEnabled", True),
        ),
        True,
    )
    next_params["checkIntervalHours"] = _int_range(
        next_params.get(
            "checkIntervalHours", item.params.get("checkIntervalHours", 6)
        ),
        6,
        minimum=1,
        maximum=168,
        field_name="checkIntervalHours",
    )
    next_params["targetKinds"] = _text(
        item, next_params, "targetKinds", fallback="radio, object", max_length=160
    )
    next_params["authorizedNames"] = _text(
        item, next_params, "authorizedNames", fallback="", max_length=240
    )
    next_params["voicePrompt"] = _text(
        item,
        next_params,
        "voicePrompt",
        fallback="I can check house radios and household items when someone asks.",
        max_length=240,
    )
    next_params["description"] = _text(
        item,
        next_params,
        "description",
        fallback="A small helper agent for in-world house repairs.",
        max_length=240,
    )
    next_params["lastAutoCheckAt"] = _int_range(
        next_params.get("lastAutoCheckAt", item.params.get("lastAutoCheckAt", 0)),
        0,
        minimum=0,
        maximum=9999999999999,
        field_name="lastAutoCheckAt",
    )
    next_params["lastAutoCheckSummary"] = _text(
        item,
        next_params,
        "lastAutoCheckSummary",
        fallback="",
        max_length=240,
    )
    return keep_only_known_params(next_params, PARAM_KEYS)
