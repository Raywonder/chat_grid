"""Cabin item validation and normalization."""

from __future__ import annotations

from ....models import WorldItem
from ..place_common import validate_place_update
from .definition import PARAM_KEYS


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize cabin params."""

    return validate_place_update(
        item,
        next_params,
        default_name="Cabin",
        default_welcome="You enter the cabin.",
        allowed_keys=PARAM_KEYS,
    )
