"""House item validation/normalization."""

from __future__ import annotations

from ....models import WorldItem
from ....world import is_known_location_id, normalize_location_id
from ...helpers import keep_only_known_params
from ...sound_policy import enforce_max_length
from .definition import DOOR_STATE_OPTIONS, PARAM_KEYS


def _clean_text(value: object, *, max_length: int, field_name: str) -> str:
    return enforce_max_length(
        str(value or "").strip(), max_length=max_length, field_name=field_name
    )


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize house params."""

    next_params["houseName"] = _clean_text(
        next_params.get("houseName", "My house"),
        max_length=80,
        field_name="houseName",
    )
    if not next_params["houseName"]:
        next_params["houseName"] = "My house"
    next_params["ownerName"] = _clean_text(
        next_params.get("ownerName", ""), max_length=80, field_name="ownerName"
    )
    door_state = str(next_params.get("doorState", "unlocked")).strip().lower()
    if door_state in {"open", "public", "yes", "on"}:
        door_state = "unlocked"
    elif door_state in {"closed", "private", "no", "off"}:
        door_state = "locked"
    if door_state not in DOOR_STATE_OPTIONS:
        raise ValueError("doorState must be locked or unlocked.")
    next_params["doorState"] = door_state
    target_location = _clean_text(
        next_params.get("targetLocation", item.params.get("targetLocation", "")),
        max_length=64,
        field_name="targetLocation",
    )
    if target_location and is_known_location_id(target_location):
        next_params["targetLocation"] = normalize_location_id(target_location)
    else:
        next_params["targetLocation"] = target_location.casefold()
    next_params["requiredKeyId"] = _clean_text(
        next_params.get("requiredKeyId", ""),
        max_length=80,
        field_name="requiredKeyId",
    )
    next_params["keyLocationHint"] = _clean_text(
        next_params.get("keyLocationHint", ""),
        max_length=160,
        field_name="keyLocationHint",
    )
    next_params["description"] = _clean_text(
        next_params.get("description", ""),
        max_length=240,
        field_name="description",
    )
    next_params["welcomeMessage"] = _clean_text(
        next_params.get("welcomeMessage", ""),
        max_length=240,
        field_name="welcomeMessage",
    )
    return keep_only_known_params(next_params, PARAM_KEYS)
