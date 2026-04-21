"""Counter item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def use_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Increment counter and return messages plus updated params."""

    next_value = int(item.params.get("value", 0)) + 1
    return ItemUseResult(
        self_message=f"{item.title}: {next_value}",
        others_message=f"{nickname} uses {item.title}: {next_value}",
        updated_params={**item.params, "value": next_value},
    )
