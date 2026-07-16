"""Portable eCrypto wallet item validation and normalization."""

from __future__ import annotations

import re

from ....models import WorldItem
from ...helpers import keep_only_known_params, parse_bool_like
from ...sound_policy import enforce_max_length
from .definition import CUSTODY_MODE_OPTIONS, NETWORK_MODE_OPTIONS, PARAM_KEYS


def _clean_text(value: object, *, max_length: int, field_name: str) -> str:
    """Normalize one wallet text field."""

    return enforce_max_length(
        str(value or "").strip(), max_length=max_length, field_name=field_name
    )


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize portable eCrypto wallet params."""

    next_params["walletName"] = _clean_text(
        next_params.get("walletName", item.params.get("walletName", "Pocket eCrypto wallet")),
        max_length=120,
        field_name="walletName",
    ) or "Pocket eCrypto wallet"
    network_mode = str(
        next_params.get("networkMode", item.params.get("networkMode", "test"))
    ).strip().lower()
    if network_mode not in NETWORK_MODE_OPTIONS:
        raise ValueError("networkMode must be test or real.")
    next_params["networkMode"] = network_mode
    chain = _clean_text(
        next_params.get("chain", item.params.get("chain", "ecrypto-test")),
        max_length=80,
        field_name="chain",
    ).lower() or "ecrypto-test"
    if not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{1,79}", chain):
        raise ValueError("chain must be a lowercase chain identifier.")
    next_params["chain"] = chain
    address = _clean_text(
        next_params.get("address", item.params.get("address", "")),
        max_length=240,
        field_name="address",
    )
    if any(ch.isspace() for ch in address):
        raise ValueError("address may not contain spaces.")
    next_params["address"] = address
    next_params["walletLabel"] = _clean_text(
        next_params.get("walletLabel", item.params.get("walletLabel", "")),
        max_length=120,
        field_name="walletLabel",
    )
    custody_mode = str(
        next_params.get("custodyMode", item.params.get("custodyMode", "carried"))
    ).strip().lower()
    if custody_mode not in CUSTODY_MODE_OPTIONS:
        raise ValueError("custodyMode must be carried, account_link, cold_storage, or watch_only.")
    next_params["custodyMode"] = custody_mode
    next_params["description"] = _clean_text(
        next_params.get("description", item.params.get("description", "")),
        max_length=360,
        field_name="description",
    )
    next_params["enabled"] = parse_bool_like(
        next_params.get("enabled", item.params.get("enabled", True)), default=True
    )
    return keep_only_known_params(next_params, PARAM_KEYS)
