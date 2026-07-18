"""House object item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem
from ...helpers import toggle_bool_param


def _placement_text(item: WorldItem) -> str:
    placement = str(item.params.get("placement", "") or "").strip().replace("_", " ")
    surface_title = str(item.params.get("surfaceTitle", "") or "").strip()
    if surface_title:
        return f" It is sitting on {surface_title}."
    if placement:
        return f" It belongs on the {placement}."
    return ""


def _repair_text(item: WorldItem) -> str:
    repair_cost = int(item.params.get("repairCost", 0) or 0)
    purchase_cost = int(item.params.get("purchaseCost", 0) or 0)
    hint = str(item.params.get("replacementHint", "") or "").strip()
    giftable = bool(item.params.get("giftable", True))
    parts = []
    if repair_cost:
        parts.append(f"Repair suggested: {repair_cost} credits.")
    if purchase_cost:
        parts.append(f"Replacement purchase suggested: {purchase_cost} credits.")
    if giftable:
        parts.append("Someone may also give a similar replacement.")
    if hint:
        parts.append(hint)
    return " ".join(parts)


def _station_presets(item: WorldItem) -> list[dict[str, str]]:
    raw_presets = item.params.get("stationPresets")
    if not isinstance(raw_presets, list):
        return []
    presets: list[dict[str, str]] = []
    for entry in raw_presets:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or entry.get("name") or "").strip()
        url = str(entry.get("streamUrl") or entry.get("url") or "").strip()
        if title and url:
            presets.append({"title": title, "streamUrl": url})
    return presets


def _station_index(item: WorldItem, preset_count: int) -> int:
    try:
        index = int(item.params.get("stationIndex", 0))
    except (TypeError, ValueError):
        index = 0
    return index % preset_count if preset_count > 0 else 0


def _station_label(item: WorldItem) -> str:
    presets = _station_presets(item)
    if presets:
        return presets[_station_index(item, len(presets))]["title"]
    station_name = str(item.params.get("stationName", "")).strip()
    return station_name or "TV audio"


def use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Inspect an object and report its condition."""

    condition = str(item.params.get("condition", "intact")).strip().lower()
    description = str(item.params.get("description", "") or "").strip()
    owner = str(item.params.get("ownerName", "") or "").strip()
    owner_text = f" Owner: {owner}." if owner else ""
    key_for = str(item.params.get("keyFor", "") or "").strip()
    object_kind = str(item.params.get("objectKind", "")).strip().lower()
    if item.params.get("journalFolder"):
        journals = item.params.get("journalIndex")
        letters = item.params.get("letterIndex")
        journal_count = len(journals) if isinstance(journals, list) else 0
        letter_count = len(letters) if isinstance(letters, list) else 0
        return ItemUseResult(
            self_message=(
                f"{item.title} holds {journal_count} journal entries and "
                f"{letter_count} letters. It is Claudia's private writing collection "
                "kept in the desk drawer."
            ),
            others_message="",
        )
    if object_kind == "tv":
        next_enabled = toggle_bool_param(item.params, "enabled", default=True)
        state_text = "on" if next_enabled else "off"
        station = _station_label(item)
        return ItemUseResult(
            self_message=f"You switch {item.title} {state_text}. Channel: {station}.",
            others_message=f"{_nickname} switches {item.title} {state_text}.",
            updated_params={
                **item.params,
                "enabled": next_enabled,
                "playStartedAt": item.params.get("playStartedAt", 0)
                if next_enabled
                else 0,
            },
        )
    if object_kind == "keys" and key_for:
        description = f"{description} Opens: {key_for}.".strip()
    if object_kind == "window":
        window_state = str(item.params.get("windowState", "closed")).strip().lower()
        outside_text = (
            " Outside ambience can carry in from outdoors."
            if window_state == "open"
            else " Outside ambience is muffled while it is closed."
        )
        description = f"{description} Window: {window_state}.{outside_text}".strip()
    if condition in {"broken", "cracked"}:
        return ItemUseResult(
            self_message=(
                f"{item.title} is {condition}.{owner_text} {_repair_text(item)}"
            ).strip(),
            others_message="",
        )
    return ItemUseResult(
        self_message=(
            f"{item.title} is {condition}.{owner_text} {description}{_placement_text(item)}"
        ).strip(),
        others_message="",
    )


def secondary_use_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Repair a cracked or broken object in-place."""

    object_kind = str(item.params.get("objectKind", "")).strip().lower()
    if object_kind == "tv":
        presets = _station_presets(item)
        if presets:
            next_index = (_station_index(item, len(presets)) + 1) % len(presets)
            station = presets[next_index]
            return ItemUseResult(
                self_message=f"Tuned {item.title} to {station['title']}.",
                others_message="",
                updated_params={
                    **item.params,
                    "stationIndex": next_index,
                    "streamUrl": station["streamUrl"],
                    "playbackUrl": "",
                    "stationName": station["title"],
                    "nowPlaying": "",
                    "playStartedAt": item.params.get("playStartedAt", 0),
                },
            )
        if item.params.get("enabled") is False:
            return ItemUseResult(self_message=f"{item.title} is off.", others_message="")
        station_name = str(item.params.get("stationName", "")).strip()
        now_playing = str(item.params.get("nowPlaying", "")).strip()
        if now_playing and station_name:
            message = f"Playing {now_playing} from {station_name}."
        elif now_playing:
            message = f"Playing {now_playing}."
        elif station_name:
            message = f"Playing from {station_name}."
        else:
            message = "No TV now playing data."
        return ItemUseResult(self_message=message, others_message="")
    if object_kind == "window":
        window_state = str(item.params.get("windowState", "closed")).strip().lower()
        next_state = "closed" if window_state == "open" else "open"
        verb = "closes" if next_state == "closed" else "opens"
        self_verb = "close" if next_state == "closed" else "open"
        next_params = {**item.params, "windowState": next_state}
        return ItemUseResult(
            self_message=f"You {self_verb} {item.title}.",
            others_message=f"{nickname} {verb} {item.title}.",
            updated_params=next_params,
        )

    condition = str(item.params.get("condition", "intact")).strip().lower()
    if condition not in {"broken", "cracked"}:
        return ItemUseResult(
            self_message=f"{item.title} does not need repair.",
            others_message="",
        )
    next_params = {**item.params, "condition": "repaired"}
    return ItemUseResult(
        self_message=f"You repair {item.title}.",
        others_message=f"{nickname} repairs {item.title}.",
        updated_params=next_params,
    )
