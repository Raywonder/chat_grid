"""Piano item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def use_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Enter piano play mode for the user who used the item."""

    return ItemUseResult(
        self_message=f"You begin playing {item.title}.",
        others_message=f"{nickname} begins playing {item.title}.",
    )
