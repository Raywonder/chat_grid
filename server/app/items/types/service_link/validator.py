"""Service/app item validation and normalization."""

from __future__ import annotations

from ....network_security import validate_media_reference
from ....models import WorldItem
from ...helpers import keep_only_known_params, parse_bool_like
from ...sound_policy import enforce_max_length, normalize_media_reference
from .definition import PARAM_KEYS, SERVICE_KIND_OPTIONS


def _bounded_text(raw: object, *, field_name: str, max_length: int) -> str:
    """Normalize one service text field and enforce its maximum length."""

    return enforce_max_length(
        str(raw or "").strip(), max_length=max_length, field_name=field_name
    )


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize service link params."""

    kind = str(
        next_params.get("serviceKind", item.params.get("serviceKind", "service"))
    ).strip().lower()
    if kind not in SERVICE_KIND_OPTIONS:
        raise ValueError(
            "serviceKind must be one of app, game, service, site, station, tool."
        )
    next_params["serviceKind"] = kind

    url = enforce_max_length(
        normalize_media_reference(next_params.get("url", item.params.get("url", ""))),
        max_length=2048,
        field_name="url",
    )
    next_params["url"] = validate_media_reference(url, field_name="url")
    next_params["description"] = _bounded_text(
        next_params.get("description", item.params.get("description", "")),
        field_name="description",
        max_length=240,
    )
    next_params["launchMessage"] = _bounded_text(
        next_params.get("launchMessage", item.params.get("launchMessage", "")),
        field_name="launchMessage",
        max_length=240,
    )
    next_params["enabled"] = parse_bool_like(
        next_params.get("enabled", item.params.get("enabled", True)), default=True
    )
    return keep_only_known_params(next_params, PARAM_KEYS)
