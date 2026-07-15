"""eCrypto bank item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak the eCrypto bank service details."""

    if item.params.get("enabled") is False:
        return ItemUseResult(self_message=f"{item.title} is closed.", others_message="")
    bank_name = str(item.params.get("bankName") or item.title).strip()
    scope = str(item.params.get("serviceScope") or "wallets_transfers").replace("_", " ")
    description = str(item.params.get("description") or "").strip()
    access_note = str(item.params.get("accessNote") or "").strip()
    url = str(item.params.get("url") or "").strip()
    parts = [
        f"{bank_name}. eCrypto service scope: {scope}. "
        "Log in, then use this bank or /ecrypto for your linked account."
    ]
    if description:
        parts.append(description)
    if access_note:
        parts.append(access_note)
    if url:
        parts.append(f"Service URL: {url}.")
    return ItemUseResult(self_message=" ".join(parts), others_message="")


def secondary_use_item(
    item: WorldItem, nickname: str, clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Reuse the primary readout for inspection."""

    return use_item(item, nickname, clock_formatter)
