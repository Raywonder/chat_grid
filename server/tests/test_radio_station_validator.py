from __future__ import annotations

import socket
from typing import cast

import pytest

from app.client import ClientConnection
from app.item_service import ItemService
from app.items.types.radio_station.validator import validate_update
from app.items.types.radio_station.actions import secondary_use_item
from websockets.asyncio.server import ServerConnection


def _fake_ws() -> ServerConnection:
    return cast(ServerConnection, object())


def test_radio_validator_preserves_readonly_metadata_fields(tmp_path) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")
    item.params["stationName"] = "Original Station"
    item.params["nowPlaying"] = "Original Song"
    item.params["playbackUrl"] = "https://example.com/live.m3u8"

    next_params = {
        **item.params,
        "stationName": "Injected",
        "nowPlaying": "Injected Song",
        "playbackUrl": "https://attacker.example/live.m3u8",
        "mediaVolume": 60,
    }
    validated = validate_update(item, next_params)

    assert validated["mediaVolume"] == 60
    assert validated["stationName"] == "Original Station"
    assert validated["nowPlaying"] == "Original Song"
    assert validated["playbackUrl"] == "https://example.com/live.m3u8"


def test_radio_validator_clears_resolved_playback_when_stream_changes(
    tmp_path,
) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")
    item.params["streamUrl"] = "/old"
    item.params["playbackUrl"] = "https://example.com/old.m3u8"

    next_params = {
        **item.params,
        "streamUrl": "/new",
    }
    validated = validate_update(item, next_params)

    assert validated["streamUrl"] == "/new"
    assert validated["playbackUrl"] == ""


def test_radio_validator_normalizes_linked_speaker_settings(tmp_path) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")

    validated = validate_update(
        item,
        {
            **item.params,
            "speakerRole": "bass",
            "linkedMediaGroup": "  main room movie  ",
            "syncWithPrimary": "yes",
            "itemVisibility": "hidden",
        },
    )

    assert validated["speakerRole"] == "sub"
    assert validated["linkedMediaGroup"] == "main room movie"
    assert validated["syncWithPrimary"] is True
    assert validated["itemVisibility"] == "quiet"


def test_radio_validator_keeps_low_speaker_role_distinct_from_sub(tmp_path) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")

    validated = validate_update(item, {**item.params, "speakerRole": "low"})

    assert validated["speakerRole"] == "low"


def test_radio_validator_preserves_existing_settings_on_partial_update(tmp_path) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")
    item.params.update(
        {
            "stationPresets": [
                {"title": "One", "streamUrl": "https://example.com/one.mp3"},
                {"title": "Two", "streamUrl": "https://example.com/two.mp3"},
            ],
            "stationIndex": 0,
            "streamUrl": "https://example.com/one.mp3",
            "mediaVolume": 64,
            "mediaChannel": "left",
            "mediaEffect": "echo",
            "mediaEffectValue": 72.5,
            "speakerRole": "high",
            "linkedMediaGroup": "front-room",
            "syncWithPrimary": True,
            "itemVisibility": "quiet",
            "stationSwitchSound": "sounds/radio/station-switch/one.mp3",
            "playStartedAt": 12345,
            "facing": 270,
            "emitRange": 14,
            "surfaceId": "shelf-1",
            "surfaceTitle": "Media shelf",
        }
    )

    validated = validate_update(item, {"stationIndex": 1, "mediaVolume": 48})

    assert validated["stationIndex"] == 1
    assert validated["streamUrl"] == "https://example.com/two.mp3"
    assert validated["mediaVolume"] == 48
    assert validated["mediaChannel"] == "left"
    assert validated["mediaEffect"] == "echo"
    assert validated["mediaEffectValue"] == 72.5
    assert validated["speakerRole"] == "high"
    assert validated["linkedMediaGroup"] == "front-room"
    assert validated["syncWithPrimary"] is True
    assert validated["itemVisibility"] == "quiet"
    assert validated["stationSwitchSound"] == "sounds/radio/station-switch/one.mp3"
    assert validated["playStartedAt"] == 12345
    assert validated["facing"] == 270
    assert validated["emitRange"] == 14
    assert validated["surfaceId"] == "shelf-1"
    assert validated["surfaceTitle"] == "Media shelf"


def test_radio_validator_allows_boosted_per_speaker_volume(tmp_path) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")

    validated = validate_update(item, {**item.params, "mediaVolume": 1000})

    assert validated["mediaVolume"] == 1000


def test_radio_validator_rejects_unknown_speaker_role(tmp_path) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")

    try:
        validate_update(item, {**item.params, "speakerRole": "sideways"})
    except ValueError as exc:
        assert "speakerRole" in str(exc)
    else:
        raise AssertionError("unknown speakerRole should be rejected")


def test_radio_presets_drive_station_knob_and_stream(tmp_path) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")
    item.params["stationPresets"] = [
        {"title": "One", "streamUrl": "https://example.com/one.mp3"},
        {
            "title": "Two",
            "streamUrl": "https://example.com/two.mp3",
            "switchSound": "sounds/radio/station-switch/two.mp3",
        },
    ]
    item.params["stationIndex"] = 0
    item.params["streamUrl"] = "https://example.com/one.mp3"

    result = secondary_use_item(item, "tester", lambda _params: "")
    validated = validate_update(item, {**item.params, **(result.updated_params or {})})

    assert result.self_message == "Tuned radio to Two."
    assert validated["stationIndex"] == 1
    assert validated["streamUrl"] == "https://example.com/two.mp3"
    assert validated["stationName"] == "Two"
    assert validated["stationSwitchSound"] == "sounds/radio/station-switch/two.mp3"


def test_radio_presets_do_not_dns_validate_dormant_stations(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")
    item.params["stationPresets"] = [
        {"title": "Working", "streamUrl": "https://good.example/live.mp3"},
        {"title": "Retired", "streamUrl": "https://retired.invalid/live.mp3"},
    ]
    item.params["stationIndex"] = 0
    item.params["streamUrl"] = "https://good.example/live.mp3"

    def fake_getaddrinfo(host: str, port, type: int = 0):
        if host == "good.example":
            return [(socket.AF_INET, type, 6, "", ("93.184.216.34", 0))]
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    validated = validate_update(item, {**item.params})

    assert len(validated["stationPresets"]) == 2
    assert validated["streamUrl"] == "https://good.example/live.mp3"


def test_radio_validator_allows_selected_sounds_relative_stream(tmp_path) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")
    item.params["stationPresets"] = [
        {
            "title": "Relaxation",
            "streamUrl": "sounds/radio/relaxation/tappedin-30min-relaxation.mp3",
        },
    ]
    item.params["stationIndex"] = 0
    item.params["streamUrl"] = "sounds/radio/relaxation/tappedin-30min-relaxation.mp3"

    validated = validate_update(item, {**item.params})

    assert (
        validated["streamUrl"]
        == "sounds/radio/relaxation/tappedin-30min-relaxation.mp3"
    )


def test_radio_validator_does_not_dns_reject_selected_external_stream(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester")
    item = service.default_item(client, "radio_station")
    item.params["stationPresets"] = [
        {"title": "Retired", "streamUrl": "https://retired.invalid/live.mp3"},
    ]
    item.params["stationIndex"] = 0
    item.params["streamUrl"] = "https://retired.invalid/live.mp3"

    def fake_getaddrinfo(host: str, port, type: int = 0):
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    validated = validate_update(item, {**item.params})

    assert validated["streamUrl"] == "https://retired.invalid/live.mp3"
