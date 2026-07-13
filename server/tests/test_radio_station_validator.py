from __future__ import annotations

from typing import cast

from app.client import ClientConnection
from app.item_service import ItemService
from app.items.types.radio_station.validator import validate_update
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
