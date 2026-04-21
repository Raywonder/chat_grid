"""Widget item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem
from ...helpers import toggle_bool_param


def use_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Toggle enabled state for widget."""

    next_enabled = toggle_bool_param(item.params, "enabled", default=True)
    state_text = "on" if next_enabled else "off"
    return ItemUseResult(
        self_message=f"You turn {state_text} {item.title}.",
        others_message=f"{nickname} turns {state_text} {item.title}.",
        updated_params={**item.params, "enabled": next_enabled},
    )
