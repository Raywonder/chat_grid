"""Owner-approved public discoveries for short-lived Endiginous notices."""

from __future__ import annotations

from .blind_productions_billboards import BlindProductionsMessage

SHAFTFALL_EXPIRES_AT_MS = 1785801600000  # 2026-08-04T00:00:00Z


def current_curated_billboards(*, now_ms: int) -> list[BlindProductionsMessage]:
    """Return public notices with explicit expiry and rotation limits."""

    if now_ms >= SHAFTFALL_EXPIRES_AT_MS:
        return []

    return [
        BlindProductionsMessage(
            title="Fancy a game? Shaftfall",
            url="https://applevis.com/forum/ios-ipados-gaming/shaftfall",
            source="Games",
            author="AppleVis community",
            preview=(
                "Fancy an accessible iOS game discovery? AppleVis has a lively "
                "community discussion about Shaftfall for players looking for "
                "something new to try."
            ),
            updated="2026-07-21T00:00:00Z",
            expires_at_ms=SHAFTFALL_EXPIRES_AT_MS,
            max_rotations=6,
            location_id="arcade",
        )
    ]
