"""Shared handlers for simple place-style item types."""

from __future__ import annotations

from typing import Callable

from ...item_types import ItemUseResult
from ...models import WorldItem
from ...world import is_known_location_id, normalize_location_id
from ..helpers import keep_only_known_params
from ..sound_policy import enforce_max_length

DOOR_STATE_OPTIONS: tuple[str, ...] = ("unlocked", "locked")


def clean_text(value: object, *, max_length: int, field_name: str) -> str:
    """Normalize a short editable text field and enforce its maximum length."""

    return enforce_max_length(
        str(value or "").strip(), max_length=max_length, field_name=field_name
    )


def normalize_door_state(value: object) -> str:
    """Normalize friendly public/private door aliases to locked/unlocked."""

    door_state = str(value or "unlocked").strip().lower()
    if door_state in {"open", "public", "yes", "on"}:
        door_state = "unlocked"
    elif door_state in {"closed", "private", "no", "off"}:
        door_state = "locked"
    if door_state not in DOOR_STATE_OPTIONS:
        raise ValueError("doorState must be locked or unlocked.")
    return door_state


def validate_place_update(
    item: WorldItem,
    next_params: dict,
    *,
    default_name: str,
    default_welcome: str,
    allowed_keys: tuple[str, ...],
) -> dict:
    """Validate and normalize shared place params."""

    next_params["placeName"] = clean_text(
        next_params.get("placeName", item.params.get("placeName", default_name)),
        max_length=80,
        field_name="placeName",
    )
    if not next_params["placeName"]:
        next_params["placeName"] = default_name
    next_params["ownerName"] = clean_text(
        next_params.get("ownerName", item.params.get("ownerName", "")),
        max_length=80,
        field_name="ownerName",
    )
    next_params["doorState"] = normalize_door_state(
        next_params.get("doorState", item.params.get("doorState", "unlocked"))
    )
    target_location = clean_text(
        next_params.get("targetLocation", item.params.get("targetLocation", "")),
        max_length=64,
        field_name="targetLocation",
    )
    if target_location and is_known_location_id(target_location):
        next_params["targetLocation"] = normalize_location_id(target_location)
    else:
        next_params["targetLocation"] = target_location.casefold()
    next_params["description"] = clean_text(
        next_params.get("description", item.params.get("description", "")),
        max_length=360,
        field_name="description",
    )
    next_params["welcomeMessage"] = clean_text(
        next_params.get("welcomeMessage", item.params.get("welcomeMessage", default_welcome)),
        max_length=240,
        field_name="welcomeMessage",
    )
    next_params["zoneNotes"] = clean_text(
        next_params.get("zoneNotes", item.params.get("zoneNotes", "")),
        max_length=500,
        field_name="zoneNotes",
    )
    return keep_only_known_params(next_params, allowed_keys)


def use_place_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Open or report a simple place-style item."""

    place_name = str(item.params.get("placeName") or item.title).strip()
    owner_name = str(item.params.get("ownerName") or "").strip()
    door_state = str(item.params.get("doorState") or "unlocked").strip().lower()
    if door_state == "locked":
        owner_text = f" owned by {owner_name}" if owner_name else ""
        return ItemUseResult(
            self_message=f"{place_name}{owner_text} is locked.",
            others_message=f"{nickname} checks the locked entrance at {place_name}.",
        )

    welcome = str(item.params.get("welcomeMessage") or "").strip()
    description = str(item.params.get("description") or "").strip()
    zones = str(item.params.get("zoneNotes") or "").strip()
    parts = [welcome or f"You enter {place_name}."]
    target_location = str(item.params.get("targetLocation") or "").strip()
    if target_location:
        parts.append(f"Entering {place_name}.")
    if owner_name:
        parts.append(f"Owner: {owner_name}.")
    if description:
        parts.append(description)
    if zones:
        parts.append(f"Layout: {zones}.")
    return ItemUseResult(
        self_message=" ".join(parts),
        others_message=f"{nickname} enters {place_name}.",
    )


def inspect_place_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak details for a simple place-style item."""

    place_name = str(item.params.get("placeName") or item.title).strip()
    door_state = str(item.params.get("doorState") or "unlocked").strip().lower()
    owner_name = str(item.params.get("ownerName") or "").strip()
    description = str(item.params.get("description") or "").strip()
    zones = str(item.params.get("zoneNotes") or "").strip()
    target_location = str(item.params.get("targetLocation") or "").strip()
    parts = [f"{place_name} is a {item.type.replace('_', ' ')}.", f"Door: {door_state}."]
    if target_location:
        parts.append(f"Destination: {target_location}.")
    if owner_name:
        parts.append(f"Owner: {owner_name}.")
    if description:
        parts.append(description)
    if zones:
        parts.append(f"Layout: {zones}.")
    return ItemUseResult(self_message=" ".join(parts), others_message="")
