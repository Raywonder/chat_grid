"""House item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def _house_label(item: WorldItem) -> str:
    house_name = str(item.params.get("houseName") or "").strip()
    return house_name or item.title


def use_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Open or report the house front door."""

    label = _house_label(item)
    owner_name = str(item.params.get("ownerName") or "").strip()
    door_state = str(item.params.get("doorState") or "unlocked").strip().lower()
    if door_state == "locked":
        owner_text = f" owned by {owner_name}" if owner_name else ""
        key_hint = str(item.params.get("keyLocationHint") or "").strip()
        message = f"{label}{owner_text} is locked."
        if key_hint:
            message = f"{message} {key_hint}"
        return ItemUseResult(
            self_message=message,
            others_message=f"{nickname} checks the locked door at {label}.",
        )

    welcome = str(item.params.get("welcomeMessage") or "").strip()
    description = str(item.params.get("description") or "").strip()
    parts = [welcome or f"You open {label}."]
    if owner_name:
        parts.append(f"Owner: {owner_name}.")
    if description:
        parts.append(description)
    return ItemUseResult(
        self_message=" ".join(parts),
        others_message=f"{nickname} opens {label}.",
    )


def secondary_use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak house details."""

    label = _house_label(item)
    owner_name = str(item.params.get("ownerName") or "").strip()
    door_state = str(item.params.get("doorState") or "unlocked").strip().lower()
    description = str(item.params.get("description") or "").strip()
    target_location = str(item.params.get("targetLocation") or "").strip()
    parts = [f"{label} is a house.", f"Door: {door_state}."]
    if target_location:
        parts.append(f"Interior: {target_location}.")
    key_hint = str(item.params.get("keyLocationHint") or "").strip()
    if door_state == "locked" and key_hint:
        parts.append(f"Key hint: {key_hint}")
    if owner_name:
        parts.append(f"Owner: {owner_name}.")
    if description:
        parts.append(description)
    return ItemUseResult(self_message=" ".join(parts), others_message="")
