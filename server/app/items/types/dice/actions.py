"""Dice item use actions."""

from __future__ import annotations

import random
from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def use_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Roll dice and report result."""

    try:
        sides = max(1, min(100, int(item.params.get("sides", 6))))
        number = max(1, min(100, int(item.params.get("number", 2))))
    except (TypeError, ValueError):
        sides = 6
        number = 2
    rolls = [random.randint(1, sides) for _ in range(number)]
    total = sum(rolls)
    rolls_text = ", ".join(str(value) for value in rolls)
    if number == 1:
        return ItemUseResult(
            self_message=f"You rolled {item.title}: {rolls_text}.",
            others_message=f"{nickname} rolled {item.title}: {rolls_text}.",
        )
    return ItemUseResult(
        self_message=f"You rolled {item.title}: {rolls_text} (total {total}).",
        others_message=f"{nickname} rolled {item.title}: {rolls_text} (total {total}).",
    )
