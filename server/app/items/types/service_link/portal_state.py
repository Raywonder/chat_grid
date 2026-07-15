"""Portal state helpers for service links."""

from __future__ import annotations

import time

from ....models import WorldItem


def is_portal_kind(item: WorldItem) -> bool:
    """Return whether a service link should behave as a portal."""

    return str(item.params.get("serviceKind", "")).strip().lower() == "portal"


def effective_portal_state(item: WorldItem, now_ms: int | None = None) -> str:
    """Return the current portal state after applying optional open/closed cycles."""

    state = str(item.params.get("portalState", "open")).strip().lower()
    if state not in {"open", "closed"}:
        state = "open"

    try:
        open_seconds = float(item.params.get("portalOpenSeconds", 0))
    except (TypeError, ValueError):
        open_seconds = 0.0
    try:
        closed_seconds = float(item.params.get("portalClosedSeconds", 0))
    except (TypeError, ValueError):
        closed_seconds = 0.0

    if open_seconds <= 0 or closed_seconds <= 0:
        return state

    current_ms = int(time.time() * 1000) if now_ms is None else now_ms
    anchor_ms = item.updatedAt or item.createdAt or current_ms
    elapsed_seconds = max(0.0, (current_ms - anchor_ms) / 1000)
    cycle_seconds = open_seconds + closed_seconds
    phase = elapsed_seconds % cycle_seconds

    if state == "open":
        return "open" if phase < open_seconds else "closed"
    return "closed" if phase < closed_seconds else "open"
