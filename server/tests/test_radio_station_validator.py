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

    next_params = {
        **item.params,
        "stationName": "Injected",
        "nowPlaying": "Injected Song",
        "mediaVolume": 60,
    }
    validated = validate_update(item, next_params)

    assert validated["mediaVolume"] == 60
    assert validated["stationName"] == "Original Station"
    assert validated["nowPlaying"] == "Original Song"
