"""Furniture item validation and normalization."""

from __future__ import annotations

from ....models import WorldItem
from ....world import get_location
from ...helpers import keep_only_known_params, parse_bool_like
from ...sound_policy import enforce_max_length
from .definition import (
    CONDITION_OPTIONS,
    FURNITURE_KIND_OPTIONS,
    MATERIAL_OPTIONS,
    PARAM_KEYS,
    POSTURE_MODE_OPTIONS,
)


def _option(raw: object, fallback: str, options: tuple[str, ...], field_name: str) -> str:
    """Normalize one list option field."""

    value = str(raw or fallback).strip().lower()
    if value not in options:
        raise ValueError(f"{field_name} must be one of {', '.join(options)}.")
    return value


def _validate_location_fit(item: WorldItem, params: dict) -> None:
    """Reject furniture that plainly belongs indoors when placed outside."""

    location = get_location(item.locationId)
    furniture_kind = str(params.get("furnitureKind", "table")).strip().lower()
    style = str(params.get("style", "") or "").casefold()
    outdoor_ok = any(
        token in style
        for token in ("outdoor", "patio", "porch", "garden", "picnic", "park")
    )
    outdoor_locations = {"city", "forest", "town", "houses"}
    indoor_only = {"bed", "nightstand", "dresser", "desk", "couch", "sofa", "booth"}
    if location.id in outdoor_locations and furniture_kind in indoor_only and not outdoor_ok:
        raise ValueError(
            f"{furniture_kind} furniture belongs indoors here unless its style clearly says outdoor, patio, porch, garden, or picnic."
        )
    if location.kind in {"room", "house"} and furniture_kind == "bench" and outdoor_ok:
        raise ValueError("Outdoor benches belong outside, on a porch, or in the neighborhood.")


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize furniture params."""

    next_params["furnitureKind"] = _option(
        next_params.get("furnitureKind", item.params.get("furnitureKind", "table")),
        "table",
        FURNITURE_KIND_OPTIONS,
        "furnitureKind",
    )
    next_params["material"] = _option(
        next_params.get("material", item.params.get("material", "wood")),
        "wood",
        MATERIAL_OPTIONS,
        "material",
    )
    next_params["condition"] = _option(
        next_params.get("condition", item.params.get("condition", "good")),
        "good",
        CONDITION_OPTIONS,
        "condition",
    )
    next_params["postureMode"] = _option(
        next_params.get("postureMode", item.params.get("postureMode", "none")),
        "none",
        POSTURE_MODE_OPTIONS,
        "postureMode",
    )
    next_params["supportsObjects"] = parse_bool_like(
        next_params.get("supportsObjects", item.params.get("supportsObjects", True)),
        default=True,
    )
    try:
        slots = int(next_params.get("surfaceSlots", item.params.get("surfaceSlots", 4)))
    except (TypeError, ValueError) as exc:
        raise ValueError("surfaceSlots must be an integer between 0 and 20.") from exc
    if not (0 <= slots <= 20):
        raise ValueError("surfaceSlots must be between 0 and 20.")
    next_params["surfaceSlots"] = slots
    try:
        seating_capacity = int(
            next_params.get(
                "seatingCapacity", item.params.get("seatingCapacity", 0)
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("seatingCapacity must be an integer between 0 and 6.") from exc
    if not (0 <= seating_capacity <= 6):
        raise ValueError("seatingCapacity must be between 0 and 6.")
    next_params["seatingCapacity"] = seating_capacity
    next_params["style"] = enforce_max_length(
        str(next_params.get("style", item.params.get("style", "")) or "").strip(),
        max_length=120,
        field_name="style",
    )
    next_params["surfaceNote"] = enforce_max_length(
        str(
            next_params.get("surfaceNote", item.params.get("surfaceNote", "")) or ""
        ).strip(),
        max_length=240,
        field_name="surfaceNote",
    )
    _validate_location_fit(item, next_params)
    return keep_only_known_params(next_params, PARAM_KEYS)
