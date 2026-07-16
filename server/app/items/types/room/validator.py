"""Room item validation and normalization."""

from __future__ import annotations

from ....models import WorldItem
from ..place_common import validate_place_update
from .definition import PARAM_KEYS, ROOM_LAYOUT_OPTIONS


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize room params."""

    layout = str(
        next_params.get("roomLayout", item.params.get("roomLayout", "single_room_studio"))
    ).strip().lower()
    if layout not in ROOM_LAYOUT_OPTIONS:
        raise ValueError(
            "roomLayout must be one of single_room_studio, open_plan, bedroom, bathroom, kitchen, living_room, closet, utility, custom."
        )
    next_params["roomLayout"] = layout
    return validate_place_update(
        item,
        next_params,
        default_name="Room",
        default_welcome="You enter the room.",
        allowed_keys=PARAM_KEYS,
    )
