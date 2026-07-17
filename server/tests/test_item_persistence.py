from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from websockets.asyncio.server import ServerConnection

from app.client import ClientConnection
from app.item_service import ItemService
from app.world import WORLD_LOCATIONS


def _fake_ws() -> ServerConnection:
    return cast(ServerConnection, object())


def test_world_location_ambience_assets_exist() -> None:
    sounds_dir = Path(__file__).parents[2] / "client" / "public" / "sounds" / "ambience"

    missing = [
        location.ambience_key
        for location in WORLD_LOCATIONS
        if not (sounds_dir / f"{location.ambience_key}.ogg").exists()
    ]

    assert missing == []


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


def test_disconnect_drops_carried_radio_without_turning_it_off(tmp_path: Path) -> None:
    state_file = tmp_path / "items.json"
    service = ItemService(state_file=state_file)
    client = ClientConnection(websocket=_fake_ws(), id="u1", x=7, y=8)

    radio = service.default_item(client, "radio_station")
    radio.title = "Pocket radio"
    radio.carrierId = client.id
    radio.params = {
        **radio.params,
        "enabled": True,
        "streamUrl": "https://example.com/radio.mp3",
        "stationName": "Example Radio",
    }
    service.add_item(radio)

    changed = service.drop_carried_items_for_disconnect(client)

    assert changed == [radio]
    assert radio.carrierId is None
    assert radio.x == client.x
    assert radio.y == client.y
    assert radio.params["enabled"] is True


def test_disconnect_drops_carried_tv_without_turning_it_off(tmp_path: Path) -> None:
    state_file = tmp_path / "items.json"
    service = ItemService(state_file=state_file)
    client = ClientConnection(websocket=_fake_ws(), id="u1", x=4, y=5)

    tv = service.default_item(client, "house_object")
    tv.title = "Wall TV"
    tv.carrierId = client.id
    tv.params = {
        **tv.params,
        "objectKind": "tv",
        "placement": "wall",
        "enabled": True,
    }
    service.add_item(tv)

    changed = service.drop_carried_items_for_disconnect(client)

    assert changed == [tv]
    assert tv.carrierId is None
    assert tv.x == client.x
    assert tv.y == client.y
    assert tv.params["enabled"] is True


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
    assert service.items["seed-city-chat-grid-radio"].type == "radio_station"
    radio = service.items["seed-city-chat-grid-radio"]
    assert radio.params["streamUrl"] == "https://aaastreamer.devinecreations.net/s/soulfoodradio-media"
    assert len(radio.params["stationPresets"]) >= 18
    preset_titles = [preset["title"] for preset in radio.params["stationPresets"]]
    assert "Chris Mix Radio" in preset_titles
    assert "StreamMadness - The Plague" in preset_titles
    assert "BBC Radio 1" in preset_titles
    assert "NPR Program Stream" in preset_titles
    assert "Classical KUSC" in preset_titles
    assert "Jazz24" in preset_titles
    assert [title for title in preset_titles if title.startswith("ACB Media ")] == [
        f"ACB Media {index}" for index in range(1, 11)
    ]
    assert radio.params["stationPresets"][8]["streamUrl"] == "https://streaming.live365.com/a11911"
    assert "seed-city-acb-media-1" not in service.items
    assert service.items["seed-arcade-moonstep-runner"].locationId == "arcade"
    assert service.items["seed-arcade-moonstep-runner"].params["serviceKind"] == "game"
    assert service.items["seed-town-ecrypto-bank"].type == "ecrypto_bank"
    assert service.items["seed-town-ecrypto-bank"].locationId == "town"
    assert (
        service.items["seed-town-ecrypto-bank"].params["serviceScope"]
        == "wallets_transfers"
    )
    assert (
        service.items["seed-town-ecrypto-bank"].params["emitSound"]
        == "sounds/ambience/ecrypto_bank_lobby.ogg?v=20260714-ecrypto-bank"
    )
    assert (
        service.items["seed-town-ecrypto-bank"].params["targetLocation"]
        == "ecrypto_bank_lobby"
    )
    assert service.items["seed-town-ecrypto-bank"].params["emitRange"] == 10
    assert service.items["seed-town-ecrypto-bank"].params["emitVolume"] == 42
    ecrypto_banks = [
        item for item in service.items.values() if item.type == "ecrypto_bank"
    ]
    assert {item.locationId for item in ecrypto_banks}.issuperset(
        {"city", "town", "forest", "offices", "arcade", "houses", "ecrypto_bank_lobby"}
    )
    assert service.items["seed-ecrypto-bank-lobby-teller"].locationId == "ecrypto_bank_lobby"
    assert service.items["seed-ecrypto-bank-lobby-atm"].params["serviceScope"] == "wallets_transfers"
    assert service.items["seed-ecrypto-bank-lobby-exit"].params["targetLocation"] == "town"
    assert all("carryable" not in item.capabilities for item in ecrypto_banks)
    assert service.items["seed-town-pocket-ecrypto-wallet"].type == "ecrypto_wallet"
    assert "carryable" in service.items["seed-town-pocket-ecrypto-wallet"].capabilities
    assert service.items["seed-town-pocket-ecrypto-wallet"].params["custodyMode"] == "carried"
    assert service.items["seed-city-portal-arcade"].locationId == "city"
    assert service.items["seed-city-portal-arcade"].params["serviceKind"] == "portal"
    assert service.items["seed-city-portal-arcade"].params["targetLocation"] == "arcade"
    assert (
        service.items["seed-city-portal-arcade"].params["emitSound"]
        == "sounds/teleport_pad_loop.ogg"
    )
    assert (
        service.items["seed-city-portal-arcade"].params["useSound"]
        == "sounds/teleport_departure_whoosh.ogg"
    )
    assert service.items["seed-arcade-portal-city"].locationId == "arcade"
    assert service.items["seed-arcade-portal-city"].params["targetLocation"] == "city"
    assert (
        service.items["seed-houses-raywonder-front-door"].params["targetLocation"]
        == "raywonder_house_entry"
    )
    assert (
        service.items["seed-houses-raywonder-front-door"].params["doorState"]
        == "unlocked"
    )
    assert (
        service.items["seed-houses-raywonder-front-door"].params["emitSound"]
        == "sounds/house_threshold_loop.ogg"
    )
    assert "seed-houses-neighborhood-teleport-pad" in service.items
    assert (
        service.items["seed-houses-neighborhood-teleport-pad"].params[
            "targetLocation"
        ]
        == "city"
    )
    assert (
        service.items["seed-raywonder-entry-door-living-room"].locationId
        == "raywonder_house_entry"
    )
    assert (
        service.items["seed-raywonder-entry-door-bedroom"].params["targetLocation"]
        == "raywonder_house_bedroom"
    )
    assert service.items["seed-raywonder-entry-door-bedroom"].params["doorState"] == "locked"
    assert (
        service.items["seed-raywonder-entry-door-bedroom"].params["requiredKeyId"]
        == "raywonder-bedroom-key"
    )
    assert (
        service.items["seed-raywonder-entry-door-bedroom"].params["emitSound"]
        == "sounds/door_soft_loop.ogg"
    )
    assert service.items["seed-raywonder-entry-house-alarm"].type == "house_alarm"
    assert (
        service.items["seed-raywonder-entry-house-alarm"].locationId
        == "houses"
    )
    assert (
        service.items["seed-raywonder-entry-house-alarm"].params["authorizedNames"]
        == "Dom, Dominique, Clawdia"
    )
    assert (
        service.items["seed-raywonder-entry-house-alarm"].params["notificationMode"]
        == "in_grid"
    )
    assert service.items["seed-raywonder-entry-house-keeper"].type == "house_keeper"
    assert (
        service.items["seed-raywonder-entry-house-keeper"].locationId
        == "raywonder_house_entry"
    )
    assert (
        service.items["seed-raywonder-entry-house-keeper"].params["targetKinds"]
        == "radio, object"
    )
    assert service.items["seed-houses-matthew-front-door"].params["accessAlarmItemId"] == "seed-houses-matthew-alarm"
    assert service.items["seed-houses-matthew-alarm"].locationId == "houses"
    assert service.items["seed-matthew-music-piano"].locationId == "matthew_house_music_room"
    assert service.items["seed-raywonder-entry-bedroom-key"].type == "house_object"
    assert (
        service.items["seed-raywonder-entry-bedroom-key"].params["keyId"]
        == "raywonder-bedroom-key"
    )
    assert (
        service.items["seed-raywonder-entry-door-relaxation-room"].params[
            "targetLocation"
        ]
        == "raywonder_house_relaxation_room"
    )
    relaxation_presets = service.items["seed-raywonder-relaxation-ocean-radio"].params[
        "stationPresets"
    ]
    meditation_preset = next(
        preset
        for preset in relaxation_presets
        if preset["title"] == "Steve G. Jones spiritual meditation"
    )
    assert (
        meditation_preset["streamUrl"]
        == "sounds/radio/relaxation/steve-g-jones-spiritual-meditation-module1.mp3"
    )
    assert service.items["seed-raywonder-living-room-radio"].params["enabled"] is True
    assert service.items["seed-raywonder-kitchen-counter-radio"].params["enabled"] is True
    assert service.items["seed-raywonder-bedroom-bedside-radio"].params["enabled"] is False
    assert (
        service.items["seed-raywonder-living-room-radio"].params["linkedMediaGroup"]
        == "raywonder-house-radios"
    )
    assert (
        service.items["seed-raywonder-kitchen-counter-radio"].params["speakerRole"]
        == "mid"
    )
    assert (
        service.items["seed-raywonder-bedroom-bedside-radio"].params["speakerRole"]
        == "high"
    )
    assert (
        service.items["seed-raywonder-relaxation-ocean-radio"].params["speakerRole"]
        == "sub"
    )
    assert (
        service.items["seed-raywonder-living-room-radio-remote"].params["objectKind"]
        == "remote"
    )
    assert (
        service.items["seed-raywonder-living-room-radio-remote"]
        .params["remoteControlLinkedRadios"]
        is True
    )
    assert (
        service.items["seed-raywonder-living-room-radio"].params["stationPresets"][2][
            "title"
        ]
        == "Chris Mix Radio"
    )
    assert (
        service.items["seed-raywonder-living-room-radio"].params["stationPresets"][8][
            "title"
        ]
        == "ACB Media 1"
    )
    assert (
        service.items["seed-raywonder-living-room-radio"].params["stationPresets"][-1][
            "title"
        ]
        == "Steve G. Jones spiritual meditation"
    )
    assert service.items["seed-raywonder-kitchen-fridge"].params["objectKind"] == "fridge"
    assert (
        service.items["seed-raywonder-kitchen-fridge"].params["emitSound"]
        == "sounds/house/fridge_hum_loop.ogg"
    )
    assert service.items["seed-raywonder-kitchen-fridge"].params["emitRange"] == 5
    assert service.items["seed-raywonder-kitchen-sink"].params["placement"] == "fixture"
    assert service.items["seed-raywonder-kitchen-stove"].params["placement"] == "appliance"
    assert service.items["seed-city-portal-forest"].params["targetLocation"] == "forest"
    assert service.items["seed-forest-portal-city"].locationId == "forest"
    assert service.items["seed-forest-picnic-table"].type == "furniture"
    assert service.items["seed-forest-picnic-table"].params["furnitureKind"] == "table"
    assert "outdoor" in service.items["seed-forest-picnic-table"].params["style"]
    assert service.items["seed-town-park-bench"].params["furnitureKind"] == "bench"
    assert service.items["seed-town-cafe-entrance"].params["targetLocation"] == "town_cafe"
    assert service.items["seed-town-cafe-exit"].params["targetLocation"] == "town"
    assert service.items["seed-town-cafe-ambience"].params["ambienceScope"] == "location"
    assert service.items["seed-town-cafe-table-west"].params["furnitureKind"] == "table"
    assert service.items["seed-town-cafe-chair-east-b"].params["postureMode"] == "sit"
    assert service.items["seed-town-cafe-world-cup-tv"].params["objectKind"] == "tv"
    assert service.items["seed-town-cafe-world-cup-board"].type == "billboard"
    assert service.items["seed-houses-front-porch-bench"].params["furnitureKind"] == "bench"
    assert service.items["seed-houses-mailbox"].params["objectKind"] == "mailbox"
    assert service.items["seed-raywonder-living-room-couch"].type == "furniture"
    assert (
        service.items["seed-raywonder-living-room-couch"].params["furnitureKind"]
        == "couch"
    )
    assert service.items["seed-raywonder-living-room-couch"].params["postureMode"] == "sit"
    assert service.items["seed-raywonder-living-room-tv"].params["objectKind"] == "tv"
    assert service.items["seed-raywonder-living-room-tv"].params["placement"] == "wall"
    assert service.items["seed-raywonder-studio-wall-shelf"].type == "furniture"
    assert service.items["seed-raywonder-studio-wall-shelf"].params["furnitureKind"] == "shelf"
    assert service.items["seed-raywonder-studio-notebook"].params["surfaceId"] == "seed-raywonder-studio-desk"
    assert service.items["seed-raywonder-kitchen-counter"].type == "furniture"
    assert service.items["seed-raywonder-kitchen-microwave"].params["surfaceId"] == "seed-raywonder-kitchen-counter"
    assert service.items["seed-raywonder-bedroom-bed"].type == "furniture"
    assert service.items["seed-raywonder-bedroom-nightstand"].params["furnitureKind"] == "nightstand"
    assert service.items["seed-raywonder-bedroom-lamp"].params["surfaceId"] == "seed-raywonder-bedroom-nightstand"
    assert service.items["seed-raywonder-living-room-window"].params["windowState"] == "open"
    assert service.items["seed-raywonder-bedroom-window"].params["windowState"] == "closed"


def test_system_builtin_seed_audio_params_are_updated(tmp_path: Path) -> None:
    state_file = tmp_path / "items.json"
    stale_portal = {
        "id": "seed-city-portal-houses",
        "type": "service_link",
        "title": "Houses portal",
        "locationId": "city",
        "x": 20,
        "y": 21,
        "createdBy": "system",
        "createdByName": "system",
        "updatedBy": "system",
        "updatedByName": "system",
        "createdAt": 1,
        "updatedAt": 1,
        "version": 1,
        "params": {
            "serviceKind": "portal",
            "targetLocation": "houses",
            "description": "A doorway from Main City to the Houses location.",
            "launchMessage": "Entering Houses.",
            "doorState": "unlocked",
            "enabled": True,
        },
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps([stale_portal]), encoding="utf-8")

    service = ItemService(state_file=state_file, seed_builtin_items=True)
    portal = service.items["seed-city-portal-houses"]

    assert portal.params["emitSound"] == "sounds/teleport_pad_loop.ogg"
    assert portal.params["useSound"] == "sounds/teleport_departure_whoosh.ogg"
    assert portal.params["emitRange"] == 12
    assert portal.version == 2


def test_system_builtin_seed_type_and_location_are_corrected(tmp_path: Path) -> None:
    state_file = tmp_path / "items.json"
    stale_couch = {
        "id": "seed-raywonder-living-room-couch",
        "type": "house_object",
        "title": "Living room couch",
        "locationId": "city",
        "x": 1,
        "y": 2,
        "createdBy": "system",
        "createdByName": "system",
        "updatedBy": "system",
        "updatedByName": "system",
        "createdAt": 1,
        "updatedAt": 1,
        "version": 3,
        "params": {
            "objectKind": "couch",
            "placement": "floor",
        },
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps([stale_couch]), encoding="utf-8")

    service = ItemService(state_file=state_file, seed_builtin_items=True)
    couch = service.items["seed-raywonder-living-room-couch"]

    assert couch.type == "furniture"
    assert couch.locationId == "raywonder_house_living_room"
    assert (couch.x, couch.y) == (18, 21)
    assert couch.params["furnitureKind"] == "couch"
    assert couch.params["postureMode"] == "sit"
    assert couch.version == 4


def test_startup_recovers_stale_carried_items(tmp_path: Path) -> None:
    service = ItemService(state_file=tmp_path / "items.json")
    client = ClientConnection(websocket=_fake_ws(), id="gone-client", nickname="tester")
    remote = service.default_item(client, "house_object")
    remote.id = "living-room-remote"
    remote.locationId = "raywonder_house_living_room"
    remote.x = 19
    remote.y = 21
    remote.carrierId = "gone-client"
    service.add_item(remote)

    changed = service.recover_stale_carried_items(active_client_ids=set())

    assert [item.id for item in changed] == ["living-room-remote"]
    assert remote.carrierId is None
    assert remote.locationId == "raywonder_house_living_room"
    assert (remote.x, remote.y) == (19, 21)
    assert remote.updatedBy == "system"


def test_builtin_seed_preserves_user_changed_radio_settings(tmp_path: Path) -> None:
    state_file = tmp_path / "items.json"
    user_changed_radio = {
        "id": "seed-raywonder-living-room-radio",
        "type": "radio_station",
        "title": "Living room radio",
        "locationId": "raywonder_house_living_room",
        "x": 19,
        "y": 20,
        "createdBy": "system",
        "createdByName": "system",
        "updatedBy": "19",
        "updatedByName": "dominique",
        "createdAt": 1,
        "updatedAt": 2,
        "version": 5,
        "params": {
            "streamUrl": "https://example.com/custom.mp3",
            "stationName": "Custom",
            "stationIndex": 3,
            "stationPresets": [],
            "enabled": True,
            "mediaVolume": 33,
            "speakerRole": "sub",
        },
    }
    state_file.write_text(json.dumps([user_changed_radio]), encoding="utf-8")

    service = ItemService(state_file=state_file, seed_builtin_items=True)
    radio = service.items["seed-raywonder-living-room-radio"]

    assert radio.params["streamUrl"] == "https://example.com/custom.mp3"
    assert radio.params["stationName"] == "Custom"
    assert radio.params["stationIndex"] == 3
    assert radio.params["mediaVolume"] == 33
    assert radio.params["speakerRole"] == "sub"
    assert radio.params["linkedMediaGroup"] == "raywonder-house-radios"
