"""Tests for the official FIFA World Cup café integration."""

from datetime import datetime, timezone

from app.models import WorldItem
from app.world_cup_live import (
    BOARD_ITEM_ID,
    TV_ITEM_ID,
    status_from_matches,
    upsert_world_cup_cafe_status,
)


def _match(*, status: int = 3) -> dict:
    return {
        "Date": "2026-07-15T19:00:00Z",
        "MatchStatus": status,
        "MatchTime": "34'",
        "StageName": [{"Locale": "en-GB", "Description": "Semi-final"}],
        "Home": {"ShortClubName": "England", "Score": 0},
        "Away": {"ShortClubName": "Argentina", "Score": 1},
    }


def _item(item_id: str, item_type: str) -> WorldItem:
    return WorldItem(
        id=item_id,
        type=item_type,
        title="test",
        locationId="town_cafe",
        x=1,
        y=1,
        createdBy="system",
        createdByName="system",
        updatedBy="system",
        updatedByName="system",
        createdAt=1,
        updatedAt=1,
        version=1,
        capabilities=[],
        params={},
    )


def test_live_match_text_includes_score_clock_and_stage() -> None:
    status = status_from_matches(
        [_match()], now=datetime(2026, 7, 15, 19, 34, tzinfo=timezone.utc)
    )
    assert status.headline.endswith("Live")
    assert "England 0, Argentina 1" in status.body
    assert "34'" in status.body
    assert "Semi-final" in status.body


def test_upsert_updates_board_and_tv_metadata() -> None:
    status = status_from_matches(
        [_match()], now=datetime(2026, 7, 15, 19, 34, tzinfo=timezone.utc)
    )
    board = _item(BOARD_ITEM_ID, "billboard")
    tv = _item(TV_ITEM_ID, "house_object")
    changed = upsert_world_cup_cafe_status(
        {board.id: board, tv.id: tv}, status, now_ms=200
    )
    assert changed == [board, tv]
    assert board.params["headline"].endswith("Live")
    assert "Argentina 1" in tv.params["nowPlaying"]
    assert board.version == 2
    assert tv.version == 2
    assert board.updatedBy == "fifa-live-feed"
    assert tv.updatedByName == "FIFA live feed"
