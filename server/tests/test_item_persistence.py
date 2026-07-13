from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from websockets.asyncio.server import ServerConnection

from app.client import ClientConnection
from app.item_service import ItemService


def _fake_ws() -> ServerConnection:
    return cast(ServerConnection, object())


def test_item_persistence_omits_global_type_properties(tmp_path: Path) -> None:
    state_file = tmp_path / "items.json"
    service = ItemService(state_file=state_file)
    client = ClientConnection(websocket=_fake_ws(), id="u1", x=3, y=4)

    item = service.default_item(client, "dice")
    service.add_item(item)
    service.save_state()

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert isinstance(saved, list)
    assert len(saved) == 1
    assert "capabilities" not in saved[0]
    assert "useSound" not in saved[0]
    assert "emitSound" not in saved[0]

    reloaded = ItemService(state_file=state_file)
    loaded_item = reloaded.items[item.id]
    assert loaded_item.useSound == "sounds/roll.ogg"
    assert loaded_item.emitSound is None
    assert "usable" in loaded_item.capabilities


def test_builtin_items_seed_without_replacing_existing_station(tmp_path: Path) -> None:
    state_file = tmp_path / "items.json"
    existing = {
        "id": "custom-soulfood",
        "type": "radio_station",
        "title": "SoulFoodRadio",
        "locationId": "city",
        "x": 1,
        "y": 2,
        "createdBy": "u1",
        "createdByName": "dominique",
        "updatedBy": "u1",
        "updatedByName": "dominique",
        "createdAt": 1,
        "updatedAt": 1,
        "version": 7,
        "params": {
            "streamUrl": "https://aaastreamer.devinecreations.net/s/soulfoodradio-media",
            "enabled": False,
            "mediaVolume": 50,
            "mediaChannel": "stereo",
            "mediaEffect": "off",
            "mediaEffectValue": 50,
            "stationName": "",
            "nowPlaying": "",
            "facing": 0,
            "emitRange": 10,
        },
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps([existing]), encoding="utf-8")

    service = ItemService(state_file=state_file, seed_builtin_items=True)
    city_soulfood = [
        item
        for item in service.items.values()
        if item.type == "radio_station"
        and item.locationId == "city"
        and item.title == "SoulFoodRadio"
    ]

    assert len(city_soulfood) == 1
    assert city_soulfood[0].id == "custom-soulfood"
    assert "seed-city-blindsoftware" in service.items
    assert service.items["seed-city-blindsoftware"].type == "service_link"
    assert service.items["seed-city-acb-media-1"].type == "radio_station"
    assert (
        service.items["seed-city-acb-media-1"].params["streamUrl"]
        == "https://streaming.live365.com/a11911"
    )
    assert service.items["seed-arcade-moonstep-runner"].locationId == "arcade"
    assert service.items["seed-arcade-moonstep-runner"].params["serviceKind"] == "game"
