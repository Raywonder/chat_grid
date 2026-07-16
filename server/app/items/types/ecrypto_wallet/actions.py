"""Portable eCrypto wallet item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak portable wallet details."""

    if item.params.get("enabled") is False:
        return ItemUseResult(self_message=f"{item.title} is disabled.", others_message="")
    wallet_name = str(item.params.get("walletName") or item.title).strip() or item.title
    network_mode = str(item.params.get("networkMode") or "test").strip()
    chain = str(item.params.get("chain") or "ecrypto-test").strip()
    address = str(item.params.get("address") or "").strip()
    label = str(item.params.get("walletLabel") or "").strip()
    custody_mode = str(item.params.get("custodyMode") or "carried").replace("_", " ")
    description = str(item.params.get("description") or "").strip()
    parts = [
        f"{wallet_name}. Portable {network_mode} wallet marker for {chain}; custody mode {custody_mode}."
    ]
    if label:
        parts.append(f"Label: {label}.")
    if address:
        parts.append(f"Address: {address}.")
    else:
        parts.append("No wallet address is set yet.")
    if description:
        parts.append(description)
    parts.append("Pick it up to carry it with you. Use an eCrypto bank branch or /ecrypto to manage account links and balances.")
    return ItemUseResult(self_message=" ".join(parts), others_message="")


def secondary_use_item(
    item: WorldItem, nickname: str, clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Reuse the primary readout for inspection."""

    return use_item(item, nickname, clock_formatter)
