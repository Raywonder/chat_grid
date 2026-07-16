"""Radio item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem
from ...helpers import toggle_bool_param


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
        if not title or not url:
            continue
        preset = {"title": title, "streamUrl": url}
        switch_sound = str(entry.get("switchSound") or entry.get("stationSwitchSound") or "").strip()
        if switch_sound:
            preset["switchSound"] = switch_sound
        presets.append(preset)
    return presets


def _station_index(item: WorldItem, preset_count: int) -> int:
    try:
        index = int(item.params.get("stationIndex", 0))
    except (TypeError, ValueError):
        index = 0
    if preset_count <= 0:
        return 0
    return index % preset_count


def _station_label(item: WorldItem) -> str:
    presets = _station_presets(item)
    if presets:
        return presets[_station_index(item, len(presets))]["title"]
    station_name = str(item.params.get("stationName", "")).strip()
    return station_name or item.title


def use_item(
    item: WorldItem, nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Toggle radio on/off when used."""

    next_enabled = toggle_bool_param(item.params, "enabled", default=True)
    state_text = "on" if next_enabled else "off"
    station = _station_label(item)
    return ItemUseResult(
        self_message=f"You switch {item.title} {state_text}. Station: {station}.",
        others_message=f"{nickname} switches {item.title} {state_text}.",
        updated_params={
            **item.params,
            "enabled": next_enabled,
            "playStartedAt": item.params.get("playStartedAt", 0) if next_enabled else 0,
        },
    )


def secondary_use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Tune to the next preset station, or speak now-playing metadata."""

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
                "stationSwitchSound": station.get("switchSound", ""),
                "nowPlaying": "",
                "playStartedAt": item.params.get("playStartedAt", 0),
            },
        )

    if item.params.get("enabled") is False:
        return ItemUseResult(
            self_message=f"{item.title} is off.",
            others_message="",
        )

    station_name = str(item.params.get("stationName", "")).strip()
    now_playing = str(item.params.get("nowPlaying", "")).strip()
    if now_playing and station_name:
        message = f"Playing {now_playing} from {station_name}."
    elif now_playing:
        message = f"Playing {now_playing}."
    elif station_name:
        message = f"Playing from {station_name}."
    else:
        message = "No now playing data."
    return ItemUseResult(self_message=message, others_message="")
