"""Official FIFA World Cup live-score integration for the Town Square Café."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import WorldItem


FIFA_COMPETITION_ID = "17"
FIFA_API_URL = "https://api.fifa.com/api/v3/calendar/matches"
FIFA_PUBLIC_URL = (
    "https://www.fifa.com/en/tournaments/mens/worldcup/"
    "canadamexicousa2026/articles/match-schedule-fixtures-results-teams-stadiums"
)
BOARD_ITEM_ID = "seed-town-cafe-world-cup-board"
TV_ITEM_ID = "seed-town-cafe-world-cup-tv"


@dataclass(frozen=True)
class WorldCupStatus:
    """Accessible text derived from one official FIFA match record."""

    headline: str
    body: str
    announcement: str
    banner: str
    now_playing: str


def fetch_world_cup_status(
    *, now: datetime | None = None, timeout: int = 15
) -> WorldCupStatus:
    """Fetch the most relevant current World Cup match from FIFA's public API."""

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    range_start = (current - timedelta(days=7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    range_end = (current + timedelta(days=7)).replace(
        hour=23, minute=59, second=59, microsecond=0
    )
    query = urlencode(
        {
            "idCompetition": FIFA_COMPETITION_ID,
            "from": _api_time(range_start),
            "to": _api_time(range_end),
            "language": "en",
            "count": "100",
        }
    )
    request = Request(
        f"{FIFA_API_URL}?{query}",
        headers={
            "User-Agent": "EndiginousWorldCupCafe/1.0",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    results = payload.get("Results", []) if isinstance(payload, dict) else []
    if not isinstance(results, list):
        results = []
    return status_from_matches(results, now=current)


def status_from_matches(
    matches: list[dict[str, Any]], *, now: datetime
) -> WorldCupStatus:
    """Choose a live, next, or latest match and format accessible board text."""

    parsed = [(match, _match_datetime(match)) for match in matches]
    parsed = [(match, when) for match, when in parsed if when is not None]
    live = [entry for entry in parsed if _is_live(entry[0])]
    future = [entry for entry in parsed if entry[1] >= now]
    past = [entry for entry in parsed if entry[1] < now]
    if live:
        match, when = min(live, key=lambda entry: entry[1])
        state = "Live"
    elif future:
        match, when = min(future, key=lambda entry: entry[1])
        state = "Next match"
    elif past:
        match, when = max(past, key=lambda entry: entry[1])
        state = "Latest result"
    else:
        return WorldCupStatus(
            headline="FIFA World Cup 2026",
            body="No match is listed in the current fourteen-day FIFA feed window. Open the official schedule for fixtures and results.",
            announcement="FIFA World Cup café update. No match is listed in the current feed window.",
            banner="Official FIFA schedule|Fixtures and results|Where to watch",
            now_playing="No current match in the feed window",
        )

    home = _team_name(match.get("Home"))
    away = _team_name(match.get("Away"))
    home_score = _score(match.get("Home"), match.get("HomeTeamScore"))
    away_score = _score(match.get("Away"), match.get("AwayTeamScore"))
    clock = str(match.get("MatchTime") or "").strip()
    stage = _localized_text(match.get("StageName"))
    time_text = when.strftime("%B %d at %H:%M UTC")
    score_text = f"{home} {home_score}, {away} {away_score}"
    if state == "Next match":
        score_text = f"{home} versus {away}"
    live_clock = f", {clock}" if clock and state == "Live" else ""
    stage_text = f" {stage}." if stage else ""
    body = f"{state}: {score_text}{live_clock}.{stage_text} {time_text}."
    announcement = f"World Cup café live board. {body}"
    banner_parts = [state, score_text]
    if clock and state == "Live":
        banner_parts.append(clock)
    if stage:
        banner_parts.append(stage)
    return WorldCupStatus(
        headline=f"FIFA World Cup 2026 — {state}",
        body=body[:360],
        announcement=announcement[:500],
        banner="|".join(banner_parts)[:500],
        now_playing=f"{state}: {score_text}{live_clock}"[:240],
    )


def upsert_world_cup_cafe_status(
    items: dict[str, WorldItem], status: WorldCupStatus, *, now_ms: int
) -> list[WorldItem]:
    """Apply live FIFA text to the café board and TV and return changed items."""

    changes: list[WorldItem] = []
    board = items.get(BOARD_ITEM_ID)
    if board is not None and board.createdBy == "system":
        board_values: dict[str, object] = {
            "headline": status.headline,
            "body": status.body,
            "announcementText": status.announcement,
            "bannerText": status.banner,
            "url": FIFA_PUBLIC_URL,
        }
        if _update_item(board, board_values, now_ms=now_ms):
            changes.append(board)
    tv = items.get(TV_ITEM_ID)
    if tv is not None and tv.createdBy == "system":
        tv_values: dict[str, object] = {
            "stationName": "FIFA World Cup 2026 live scores",
            "nowPlaying": status.now_playing,
        }
        if _update_item(tv, tv_values, now_ms=now_ms):
            changes.append(tv)
    return changes


def _update_item(item: WorldItem, values: dict[str, object], *, now_ms: int) -> bool:
    updated = False
    for key, value in values.items():
        if item.params.get(key) != value:
            item.params[key] = value
            updated = True
    if updated:
        item.updatedAt = now_ms
        item.updatedBy = "fifa-live-feed"
        item.updatedByName = "FIFA live feed"
        item.version += 1
    return updated


def _api_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _match_datetime(match: dict[str, Any]) -> datetime | None:
    value = str(match.get("Date") or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


def _is_live(match: dict[str, Any]) -> bool:
    return int(match.get("MatchStatus") or -1) == 3


def _localized_text(value: object) -> str:
    if not isinstance(value, list):
        return ""
    for entry in value:
        if isinstance(entry, dict):
            text = str(entry.get("Description") or "").strip()
            if text:
                return text
    return ""


def _team_name(value: object) -> str:
    if not isinstance(value, dict):
        return "Team to be decided"
    return (
        str(value.get("ShortClubName") or "").strip()
        or _localized_text(value.get("TeamName"))
        or str(value.get("Abbreviation") or "").strip()
        or "Team to be decided"
    )


def _score(team: object, fallback: object) -> int:
    value = team.get("Score") if isinstance(team, dict) else fallback
    try:
        return int(value if value is not None else fallback or 0)
    except (TypeError, ValueError):
        return 0
