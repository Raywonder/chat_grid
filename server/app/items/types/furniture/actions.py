"""Furniture item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def _label(item: WorldItem) -> str:
    kind = str(item.params.get("furnitureKind", "furniture")).replace("_", " ")
    return item.title if item.title.lower() != kind else f"the {kind}"


def use_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Use furniture for sitting, lying, leaning, or surface inspection."""

    posture = str(item.params.get("postureMode", "none")).strip().lower()
    label = _label(item)
    if posture in {"sit", "sit_lie"}:
        return ItemUseResult(
            self_message=f"You sit at {label}.",
            others_message=f"{nickname} sits at {label}.",
        )
    if posture == "lie":
        return ItemUseResult(
            self_message=f"You lie down on {label}.",
            others_message=f"{nickname} lies down on {label}.",
        )
    if posture == "lean":
        return ItemUseResult(
            self_message=f"You lean against {label}.",
            others_message=f"{nickname} leans against {label}.",
        )
    note = str(item.params.get("surfaceNote", "") or "").strip()
    return ItemUseResult(
        self_message=note or f"{label} is ready to hold house objects.",
        others_message=f"{nickname} checks {label}.",
    )


def secondary_use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak furniture details."""

    kind = str(item.params.get("furnitureKind", "furniture")).replace("_", " ")
    material = str(item.params.get("material", "mixed")).replace("_", " ")
    condition = str(item.params.get("condition", "good")).replace("_", " ")
    slots = int(item.params.get("surfaceSlots", 0) or 0)
    supports = bool(item.params.get("supportsObjects", True))
    note = str(item.params.get("surfaceNote", "") or "").strip()
    parts = [
        f"{item.title} is {kind} furniture.",
        f"Material: {material}.",
        f"Condition: {condition}.",
    ]
    if supports:
        parts.append(f"Surface slots: {slots}.")
    if note:
        parts.append(note)
    return ItemUseResult(self_message=" ".join(parts), others_message="")
