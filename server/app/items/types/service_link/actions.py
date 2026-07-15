"""Interactive link item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem
from .portal_state import effective_portal_state, is_portal_kind


def _details_for(item: WorldItem) -> str:
    """Build a concise spoken details line for one link item."""

    kind = str(item.params.get("serviceKind", "service")).strip() or "service"
    description = str(item.params.get("description", "")).strip()
    author = str(item.params.get("softwareAuthor", "")).strip()
    verification_status = (
        str(item.params.get("verificationStatus", "unverified")).strip()
        or "unverified"
    )
    url = str(item.params.get("url", "")).strip()
    target_location = str(item.params.get("targetLocation", "")).strip()
    door_state = str(item.params.get("doorState", "unlocked")).strip().lower()
    key_hint = str(item.params.get("keyLocationHint", "")).strip()
    parts = [f"{item.title} is a {kind}"]
    if target_location:
        parts.append(f"Door status: {door_state or 'unlocked'}")
        if door_state == "locked" and key_hint:
            parts.append(f"Key hint: {key_hint}")
    if is_portal_kind(item):
        parts.append(f"Portal status: {effective_portal_state(item)}")
        destination_mode = (
            str(item.params.get("portalDestinationMode", "random")).strip().lower()
            or "random"
        )
        parts.append(f"Destination mode: {destination_mode}")
        portal_pool = str(item.params.get("portalLocationPool", "")).strip()
        if destination_mode == "random" and portal_pool:
            parts.append(f"Random pool: {portal_pool}")
        open_seconds = item.params.get("portalOpenSeconds", 0)
        closed_seconds = item.params.get("portalClosedSeconds", 0)
        if open_seconds and closed_seconds:
            parts.append(
                "Cycle: opens for "
                f"{open_seconds} seconds and closes for {closed_seconds} seconds"
            )
    if description:
        parts.append(description)
    if author:
        parts.append(f"Author: {author}")
    if verification_status:
        parts.append(f"Verification: {verification_status.replace('_', ' ')}")
    if target_location:
        parts.append(f"Destination: {target_location}")
    if url:
        parts.append(f"URL: {url}")
    return ". ".join(parts) + "."


def use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Announce link details and URL when used."""

    if item.params.get("enabled") is False:
        if is_portal_kind(item):
            return ItemUseResult(
                self_message=f"{item.title} is closed.",
                others_message="",
            )
        return ItemUseResult(
            self_message=f"{item.title} is off.",
            others_message="",
        )

    launch_message = str(item.params.get("launchMessage", "")).strip()
    target_location = str(item.params.get("targetLocation", "")).strip()
    door_state = str(item.params.get("doorState", "unlocked")).strip().lower()
    if target_location and door_state == "locked":
        key_hint = str(item.params.get("keyLocationHint", "")).strip()
        message = f"{item.title} is locked."
        if key_hint:
            message = f"{message} {key_hint}"
        return ItemUseResult(
            self_message=message,
            others_message="",
        )
    if (
        target_location
        and is_portal_kind(item)
        and effective_portal_state(item) == "closed"
    ):
        return ItemUseResult(
            self_message=f"{item.title} is closed.",
            others_message="",
        )
    message = launch_message or _details_for(item)
    if target_location and is_portal_kind(item):
        destination_mode = (
            str(item.params.get("portalDestinationMode", "random")).strip().lower()
            or "random"
        )
        if destination_mode != "static":
            message = launch_message or f"{item.title} shimmers and chooses a destination."
    if target_location and not launch_message and not is_portal_kind(item):
        message = f"Entering {item.title}."
    if (
        target_location
        and not launch_message
        and is_portal_kind(item)
        and str(item.params.get("portalDestinationMode", "random")).strip().lower()
        == "static"
    ):
        message = f"Entering {item.title}."
    url = str(item.params.get("url", "")).strip()
    if launch_message and url:
        message = f"{message} URL: {url}."
    return ItemUseResult(self_message=message, others_message="")


def secondary_use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak full details for the link item."""

    return ItemUseResult(self_message=_details_for(item), others_message="")
