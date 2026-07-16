"""QR code item validation and normalization."""

from __future__ import annotations

from ....models import WorldItem
from ...helpers import keep_only_known_params, parse_bool_like
from ...sound_policy import enforce_max_length
from .definition import PARAM_KEYS, PAYLOAD_KIND_OPTIONS


def _clean_text(value: object, *, max_length: int, field_name: str) -> str:
    """Normalize one QR text field."""

    return enforce_max_length(
        str(value or "").strip(), max_length=max_length, field_name=field_name
    )


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize QR code params."""

    next_params["qrLabel"] = _clean_text(
        next_params.get("qrLabel", item.params.get("qrLabel", "QR code")),
        max_length=80,
        field_name="qrLabel",
    ) or "QR code"
    payload_kind = str(
        next_params.get("payloadKind", item.params.get("payloadKind", "url"))
    ).strip().lower()
    if payload_kind not in PAYLOAD_KIND_OPTIONS:
        raise ValueError("payloadKind must be one of url, text, contact, wifi, payment, ecrypto.")
    next_params["payloadKind"] = payload_kind
    next_params["payload"] = _clean_text(
        next_params.get("payload", item.params.get("payload", "")),
        max_length=2048,
        field_name="payload",
    )
    next_params["description"] = _clean_text(
        next_params.get("description", item.params.get("description", "")),
        max_length=240,
        field_name="description",
    )
    next_params["enabled"] = parse_bool_like(
        next_params.get("enabled", item.params.get("enabled", True)), default=True
    )
    return keep_only_known_params(next_params, PARAM_KEYS)
