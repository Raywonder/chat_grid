"""House keeper item actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def _label(item: WorldItem) -> str:
    keeper_name = str(item.params.get("keeperName") or "").strip()
    return keeper_name or item.title


def use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Generic fallback when a server-side keeper hook is unavailable."""

    label = _label(item)
    prompt = str(item.params.get("voicePrompt") or "").strip()
    return ItemUseResult(
        self_message=f"{label} is ready. {prompt}".strip(),
        others_message="",
    )


def secondary_use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak configured keeper details without repairing anything."""

    label = _label(item)
    house_name = str(item.params.get("houseName") or "the house").strip()
    repair_mode = str(item.params.get("repairMode") or "auto_repair").strip()
    target_kinds = str(item.params.get("targetKinds") or "radio, object").strip()
    description = str(item.params.get("description") or "").strip()
    parts = [
        f"{label} looks after {house_name}.",
        f"Mode: {repair_mode}.",
        f"Targets: {target_kinds}.",
    ]
    if description:
        parts.append(description)
    return ItemUseResult(self_message=" ".join(parts), others_message="")

