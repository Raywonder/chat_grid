"""QR code item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak QR code details and payload."""

    if item.params.get("enabled") is False:
        return ItemUseResult(self_message=f"{item.title} is off.", others_message="")
    label = str(item.params.get("qrLabel") or item.title).strip()
    kind = str(item.params.get("payloadKind") or "text").strip()
    payload = str(item.params.get("payload") or "").strip()
    description = str(item.params.get("description") or "").strip()
    parts = [f"{label} QR code, {kind}."]
    if description:
        parts.append(description)
    if payload:
        parts.append(f"Payload: {payload}.")
    else:
        parts.append("No payload configured yet.")
    return ItemUseResult(self_message=" ".join(parts), others_message="")


def secondary_use_item(
    item: WorldItem, nickname: str, clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Reuse primary QR readout for inspection."""

    return use_item(item, nickname, clock_formatter)
