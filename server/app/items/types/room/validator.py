"""Room item validation and normalization."""

from __future__ import annotations

from ....models import WorldItem
from ..place_common import validate_place_update
from .definition import PARAM_KEYS, ROOM_LAYOUT_OPTIONS, SPACE_KIND_OPTIONS


def _bounded_number(value: object, *, name: str, minimum: float, maximum: float, integer: bool = False) -> int | float:
    """Normalize a user-entered dimension while keeping room sizes usable."""

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}.")
    return int(round(number)) if integer else round(number, 2)


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
    space_kind = str(next_params.get("spaceKind", item.params.get("spaceKind", "indoor"))).strip().lower()
    if space_kind not in SPACE_KIND_OPTIONS:
        raise ValueError("spaceKind must be indoor or outdoor.")
    next_params["spaceKind"] = space_kind
    next_params["widthSquares"] = _bounded_number(next_params.get("widthSquares", item.params.get("widthSquares", 12)), name="widthSquares", minimum=1, maximum=41, integer=True)
    next_params["depthSquares"] = _bounded_number(next_params.get("depthSquares", item.params.get("depthSquares", 10)), name="depthSquares", minimum=1, maximum=41, integer=True)
    next_params["squareFeet"] = _bounded_number(next_params.get("squareFeet", item.params.get("squareFeet", 0)), name="squareFeet", minimum=0, maximum=100000)
    return validate_place_update(
        item,
        next_params,
        default_name="Room",
        default_welcome="You enter the room.",
        allowed_keys=PARAM_KEYS,
    )
