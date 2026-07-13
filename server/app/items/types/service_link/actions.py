"""Service/app item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def _details_for(item: WorldItem) -> str:
    """Build a concise spoken details line for one service item."""

    kind = str(item.params.get("serviceKind", "service")).strip() or "service"
    description = str(item.params.get("description", "")).strip()
    url = str(item.params.get("url", "")).strip()
    parts = [f"{item.title} is a {kind}"]
    if description:
        parts.append(description)
    if url:
        parts.append(f"URL: {url}")
    return ". ".join(parts) + "."


def use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Announce service details and URL when used."""

    if item.params.get("enabled") is False:
        return ItemUseResult(
            self_message=f"{item.title} is off.",
            others_message="",
        )

    launch_message = str(item.params.get("launchMessage", "")).strip()
    message = launch_message or _details_for(item)
    url = str(item.params.get("url", "")).strip()
    if launch_message and url:
        message = f"{message} URL: {url}."
    return ItemUseResult(self_message=message, others_message="")


def secondary_use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak full details for the service item."""

    return ItemUseResult(self_message=_details_for(item), others_message="")
