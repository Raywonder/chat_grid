"""Wheel item use actions."""

from __future__ import annotations

import random
from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def use_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Spin wheel and produce delayed landed value."""

    spaces_raw = item.params.get("spaces", "")
    if isinstance(spaces_raw, str):
        spaces = [token.strip() for token in spaces_raw.split(",") if token.strip()]
    elif isinstance(spaces_raw, list):
        spaces = [str(token).strip() for token in spaces_raw if str(token).strip()]
    else:
        spaces = []
    if not spaces:
        raise ValueError(
            "wheel spaces must contain at least one comma-delimited value."
        )
    landed = str(random.choice(spaces))  # nosec B311
    return ItemUseResult(
        self_message=f"You spin {item.title}.",
        others_message=f"{nickname} spins {item.title}.",
        delayed_self_message=landed,
        delayed_others_message=landed,
    )
