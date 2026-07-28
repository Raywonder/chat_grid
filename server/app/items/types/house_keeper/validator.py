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


def _bounded_list(raw: object, *, limit: int = 12) -> list[str]:
    """Normalize a small server-managed task list."""

    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for value in raw:
        text = " ".join(str(value or "").split())[:240]
        if text and text not in result:
            result.append(text)
    return result[:limit]


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
    next_params["autonomyEnabled"] = _bool_value(next_params.get("autonomyEnabled", item.params.get("autonomyEnabled", True)), True)
    next_params["localModelEnabled"] = _bool_value(next_params.get("localModelEnabled", item.params.get("localModelEnabled", False)), False)
    next_params["localModelUrl"] = _text(item, next_params, "localModelUrl", fallback="http://127.0.0.1:11434/api/chat", max_length=240)
    next_params["localModelName"] = _text(item, next_params, "localModelName", fallback="llama3.2:3b", max_length=80)
    next_params["interactionRadius"] = _int_range(next_params.get("interactionRadius", item.params.get("interactionRadius", 4)), 4, minimum=1, maximum=12, field_name="interactionRadius")
    next_params["webDiscoveryEnabled"] = _bool_value(next_params.get("webDiscoveryEnabled", item.params.get("webDiscoveryEnabled", False)), False)
    next_params["taskBoard"] = _bounded_list(next_params.get("taskBoard", item.params.get("taskBoard", [])))
    next_params["lastAutonomyAt"] = _int_range(next_params.get("lastAutonomyAt", item.params.get("lastAutonomyAt", 0)), 0, minimum=0, maximum=9999999999999, field_name="lastAutonomyAt")
    next_params["lastAutonomySummary"] = _text(item, next_params, "lastAutonomySummary", fallback="", max_length=240)
    raw_held_keys = next_params.get("heldKeyIds", item.params.get("heldKeyIds", []))
    if not isinstance(raw_held_keys, list):
        raw_held_keys = []
    next_params["heldKeyIds"] = [
        str(key_id).strip()[:128] for key_id in raw_held_keys if str(key_id).strip()
    ][:32]
    return keep_only_known_params(next_params, PARAM_KEYS)
