from __future__ import annotations

import json
from typing import Sequence, TypeVar, cast

import pytest
from websockets.asyncio.server import ServerConnection

from app.models import (
    BasePacket,
    ItemActionResultPacket,
    ItemPianoNoteBroadcastPacket,
    ItemPianoStatusPacket,
    ItemUseSoundPacket,
)
from app.server import ClientConnection, SignalingServer

PacketT = TypeVar("PacketT", bound=BasePacket)


def _fake_ws() -> ServerConnection:
    return cast(ServerConnection, object())


def _packets_of_type(
    payloads: Sequence[object], packet_type: type[PacketT]
) -> list[PacketT]:
    return [packet for packet in payloads if isinstance(packet, packet_type)]


def _last_packet_of_type(
    payloads: Sequence[object], packet_type: type[PacketT]
) -> PacketT:
    packets = _packets_of_type(payloads, packet_type)
    assert packets
    return packets[-1]


def _activate_client(
    client: ClientConnection,
    *,
    permissions: set[str] | None = None,
) -> ClientConnection:
    client.authenticated = True
    client.user_id = client.user_id or client.id
    client.username = client.username or client.nickname
    client.permissions = set(permissions or client.permissions or set())
    client.world_ready = True
    return client


@pytest.mark.asyncio
async def test_item_use_has_global_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "dice")
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    now_ms = 10_000

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server.item_service, "now_ms", lambda: now_ms)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True

    now_ms += 400
    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "cooldown" in item_result.message.lower()

    now_ms += 700
    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True


@pytest.mark.asyncio
async def test_radio_use_toggles_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "radio_station")
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []
    now_ms = 20_000

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)
    monkeypatch.setattr(server.item_service, "now_ms", lambda: now_ms)

    assert item.params.get("enabled") is True
    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    assert item.params.get("enabled") is False
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True

    now_ms += 1200
    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    assert item.params.get("enabled") is True
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True

    assert any(
        getattr(packet, "type", "") == "item_upsert" for packet in broadcast_payloads
    )


@pytest.mark.asyncio
async def test_radio_media_fields_update_validate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.edit.own"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "radio_station")
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"mediaChannel": "left"},
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("mediaChannel") == "left"

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"mediaChannel": "invalid"},
            }
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "mediachannel must be one of" in item_result.message.lower()

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_update", "itemId": item.id, "params": {"facing": 270}}
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("facing") == 270

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_update", "itemId": item.id, "params": {"facing": 361}}
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "facing must be between 0 and 360" in item_result.message.lower()

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_update", "itemId": item.id, "params": {"mediaVolume": 12}}
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("mediaVolume") == 12

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"mediaEffect": "echo"},
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("mediaEffect") == "echo"

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_update", "itemId": item.id, "params": {"emitRange": 12}}
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("emitRange") == 12

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_update", "itemId": item.id, "params": {"emitRange": 4}}
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "emitrange must be between 5 and 20" in item_result.message.lower()


@pytest.mark.asyncio
async def test_house_radio_remote_tunes_nearest_room_radio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=19,
            y=21,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    remote = server.items["seed-raywonder-living-room-radio-remote"]
    radio = server.items["seed-raywonder-living-room-radio"]

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    async def fake_resolve_radio(item: object) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve_radio)

    assert radio.params["stationIndex"] == 0
    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": remote.id})
    )

    synced_radios = [
        item
        for item in server.items.values()
        if item.type == "radio_station"
        and item.locationId.startswith("raywonder_house_")
        and item.locationId != "raywonder_house_relaxation_room"
    ]
    relaxation_radio = server.items["seed-raywonder-relaxation-ocean-radio"]
    bedroom_radio = server.items["seed-raywonder-bedroom-bedside-radio"]
    assert synced_radios
    assert all(item.params["stationIndex"] == 1 for item in synced_radios)
    assert all(item.params["stationName"] == "DivineCreations radio" for item in synced_radios)
    assert bedroom_radio.params["enabled"] is False
    assert all(
        item.params["enabled"] is True
        for item in synced_radios
        if item.id != bedroom_radio.id
    )
    assert relaxation_radio.params["stationName"] == "TappedIn 30 minute relaxation"
    assert {getattr(item, "id", "") for item in broadcast_items} == {
        item.id for item in synced_radios
    }
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "Remote tuned" in item_result.message
    assert "DivineCreations radio" in item_result.message


@pytest.mark.asyncio
async def test_house_radio_remote_syncs_all_house_radios_to_target_station(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=19,
            y=21,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    remote = server.items["seed-raywonder-living-room-radio-remote"]
    living_radio = server.items["seed-raywonder-living-room-radio"]
    target_preset = next(
        preset
        for preset in living_radio.params["stationPresets"]
        if preset["title"] == "ACB Media 1"
    )
    living_radio.params["stationIndex"] = next(
        index
        for index, preset in enumerate(living_radio.params["stationPresets"])
        if preset["title"] == "ACB Media 1"
    )
    living_radio.params["streamUrl"] = target_preset["streamUrl"]
    living_radio.params["stationName"] = target_preset["title"]

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    async def fake_resolve_radio(item: object) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve_radio)

    await server._handle_message(
        client, json.dumps({"type": "item_secondary_use", "itemId": remote.id})
    )

    synced_radios = [
        item
        for item in server.items.values()
        if item.type == "radio_station"
        and item.locationId.startswith("raywonder_house_")
        and item.locationId != "raywonder_house_relaxation_room"
    ]
    relaxation_radio = server.items["seed-raywonder-relaxation-ocean-radio"]
    bedroom_radio = server.items["seed-raywonder-bedroom-bedside-radio"]
    assert synced_radios
    assert all(
        item.params["stationName"] == "ACB Media 1" for item in synced_radios
    )
    assert bedroom_radio.params["enabled"] is False
    assert all(
        item.params["enabled"] is True
        for item in synced_radios
        if item.id != bedroom_radio.id
    )
    assert relaxation_radio.params["stationName"] == "TappedIn 30 minute relaxation"
    assert relaxation_radio.params["stationIndex"] != 8
    assert {getattr(item, "id", "") for item in broadcast_items} == {
        item.id for item in synced_radios
    }
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "Synced" in item_result.message
    assert "ACB Media 1" in item_result.message


@pytest.mark.asyncio
async def test_house_keeper_repairs_broken_room_radio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=19,
            y=20,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    keeper = server.items["seed-raywonder-entry-house-keeper"]
    keeper.locationId = "raywonder_house_living_room"
    keeper.x = 19
    keeper.y = 20
    radio = server.items["seed-raywonder-living-room-radio"]
    radio.params["enabled"] = False
    radio.params["stationIndex"] = 999
    radio.params["streamUrl"] = "htt*broken"
    radio.params["playbackUrl"] = "htt*cached"
    radio.params["stationName"] = "Broken station"

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    async def fake_resolve_radio(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve_radio)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": keeper.id})
    )

    assert radio.params["enabled"] is True
    expected_index = 999 % len(radio.params["stationPresets"])
    expected_station = radio.params["stationPresets"][expected_index]
    assert radio.params["stationIndex"] == expected_index
    assert radio.params["stationName"] == expected_station["title"]
    assert radio.params["streamUrl"] == expected_station["streamUrl"]
    assert radio.params["playbackUrl"] == ""
    assert {getattr(item, "id", "") for item in broadcast_items} == {radio.id}
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "fixed 1 item" in item_result.message
    assert "Living room radio" in item_result.message


@pytest.mark.asyncio
async def test_house_keeper_auto_check_moves_and_repairs_room_radio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    keeper = server.items["seed-raywonder-entry-house-keeper"]
    keeper.locationId = "raywonder_house_living_room"
    keeper.x = 19
    keeper.y = 20
    keeper.params["checkIntervalHours"] = 1
    keeper.params["lastAutoCheckAt"] = 0
    radio = server.items["seed-raywonder-living-room-radio"]
    radio.params["enabled"] = False
    radio.params["streamUrl"] = "htt*broken"
    radio.params["playbackUrl"] = "htt*cached"

    broadcast_items: list[object] = []
    now_ms = 123_000

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    async def fake_resolve_radio(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve_radio)
    monkeypatch.setattr(server.item_service, "now_ms", lambda: now_ms)

    start_position = (keeper.x, keeper.y)

    did_run = await server._run_house_keeper_auto_check(keeper)

    assert did_run is True
    assert abs(keeper.x - start_position[0]) + abs(keeper.y - start_position[1]) == 1
    assert radio.params["enabled"] is True
    assert radio.params["streamUrl"]
    assert radio.params["playbackUrl"] == ""
    assert keeper.params["lastAutoCheckAt"] == now_ms
    assert "Auto checked room; fixed 1 item" in keeper.params["lastAutoCheckSummary"]
    assert {getattr(item, "id", "") for item in broadcast_items} >= {
        keeper.id,
        radio.id,
    }

    broadcast_items.clear()
    did_run_again = await server._run_house_keeper_auto_check(keeper)

    assert did_run_again is False
    assert broadcast_items == []


@pytest.mark.asyncio
async def test_item_update_strips_unknown_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.edit.own"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "radio_station")
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"mediaVolume": 25, "hackedFlag": True},
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("mediaVolume") == 25
    assert "hackedFlag" not in item.params


@pytest.mark.asyncio
async def test_item_use_revalidates_updated_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "widget")
    item.params["hackedFlag"] = True
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server.item_service, "now_ms", lambda: 40_000)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )

    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("enabled") is False
    assert "hackedFlag" not in item.params


@pytest.mark.asyncio
async def test_clock_use_reports_time_without_use_sound_packet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "clock")
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)
    monkeypatch.setattr(server, "_format_clock_display_time", lambda _params: "4:32 PM")
    monkeypatch.setattr(server.item_service, "now_ms", lambda: 30_000)
    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )

    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert item_result.message == "It's 4:32 PM."
    assert not any(
        getattr(packet, "type", "") == "item_use_sound" for packet in broadcast_payloads
    )
    assert any(
        getattr(packet, "type", "") == "item_clock_announce"
        for packet in broadcast_payloads
    )


@pytest.mark.asyncio
async def test_clock_timezone_update_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.edit.own"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "clock")
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"timeZone": "Europe/Berlin"},
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("timeZone") == "Europe/Berlin"

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"announceIntervalMinutes": 1},
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("announceIntervalMinutes") == 1

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"announceIntervalMinutes": 61},
            }
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "announceintervalminutes must be from 1 to 60" in item_result.message.lower()

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"timeZone": "Invalid/Zone"},
            }
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "timezone must be one of" in item_result.message.lower()

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_update", "itemId": item.id, "params": {"alarmEnabled": True}}
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("alarmEnabled") is True
    assert item.params.get("alarmTime") == "12:00 AM"

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"alarmTime": "3:15 PM", "alarmEnabled": True},
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("alarmEnabled") is True
    assert item.params.get("alarmTime") == "3:15 PM"

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_update", "itemId": item.id, "params": {"use24Hour": True}}
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("use24Hour") is True
    assert item.params.get("alarmTime") == "15:15"


@pytest.mark.asyncio
async def test_failed_wheel_use_does_not_consume_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "wheel")
    item.params["spaces"] = ",,,"
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    now_ms = 40_000

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server.item_service, "now_ms", lambda: now_ms)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "spaces" in item_result.message.lower()

    item.params["spaces"] = "a,b,c"
    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True


@pytest.mark.asyncio
async def test_wheel_use_broadcasts_spin_sound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "wheel")
    item.params["spaces"] = "yes, no"
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server.item_service, "now_ms", lambda: 50_000)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )

    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    sound_packets = _packets_of_type(send_payloads, ItemUseSoundPacket)
    assert sound_packets
    assert sound_packets[-1].sound == "sounds/spin.ogg"
    assert sound_packets[-1].x == 5
    assert sound_packets[-1].y == 6


@pytest.mark.asyncio
async def test_widget_update_and_use(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.edit.own", "item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "widget")
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []
    now_ms = 50_000

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server.item_service, "now_ms", lambda: now_ms)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {
                    "directional": True,
                    "facing": 123.4,
                    "emitRange": 7,
                    "emitVolume": 42,
                    "emitSoundSpeed": 25,
                    "emitSoundTempo": 60,
                    "emitEffect": "reverb",
                    "emitEffectValue": 63.2,
                    "ambienceScope": "location",
                    "ambienceName": "Mountain river",
                    "ambiencePriority": 82,
                    "useSound": "ping.ogg",
                    "emitSound": "https://example.com/ambient.ogg",
                },
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("directional") is True
    assert item.params.get("facing") == 123
    assert item.params.get("emitRange") == 7
    assert item.params.get("emitVolume") == 42
    assert item.params.get("emitSoundSpeed") == 25
    assert item.params.get("emitSoundTempo") == 60
    assert item.params.get("emitEffect") == "reverb"
    assert item.params.get("emitEffectValue") == 63.2
    assert item.params.get("ambienceScope") == "location"
    assert item.params.get("ambienceName") == "Mountain river"
    assert item.params.get("ambiencePriority") == 82
    assert item.params.get("useSound") == "sounds/ping.ogg"
    assert item.params.get("emitSound") == "https://example.com/ambient.ogg"

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("enabled") is False
    assert any(getattr(packet, "type", "") == "item_use_sound" for packet in send_payloads)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_update", "itemId": item.id, "params": {"emitRange": 21}}
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "emitrange must be between 1 and 20" in item_result.message.lower()

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"emitSoundSpeed": 101},
            }
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "emitsoundspeed must be between 0 and 100" in item_result.message.lower()

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"emitSoundTempo": 101},
            }
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "emitsoundtempo must be between 0 and 100" in item_result.message.lower()

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"ambienceScope": "section"},
            }
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "ambiencescope must be one of tile, location, off" in item_result.message.lower()


@pytest.mark.asyncio
async def test_carried_item_use_sound_uses_carrier_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "widget")
    item.params["useSound"] = "sounds/test.ogg"
    item.carrierId = client.id
    # Keep stale coordinates to verify carrier position is used for use-sound broadcasts.
    item.x = 1
    item.y = 1
    server.item_service.add_item(item)
    client.x = 9
    client.y = 10

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []
    now_ms = 60_000

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server.item_service, "now_ms", lambda: now_ms)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    sound_packets = _packets_of_type(send_payloads, ItemUseSoundPacket)
    assert sound_packets
    assert sound_packets[-1].x == 9
    assert sound_packets[-1].y == 10


@pytest.mark.asyncio
async def test_piano_update_and_use(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.edit.own", "item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "piano")
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {
                    "instrument": "drum_kit",
                    "emitRange": 12,
                },
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("instrument") == "drum_kit"
    assert item.params.get("voiceMode") == "poly"
    assert item.params.get("octave") == 0
    assert item.params.get("attack") == 1
    assert item.params.get("decay") == 22
    assert item.params.get("release") == 12
    assert item.params.get("brightness") == 68
    assert item.params.get("emitRange") == 12

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"instrument": "nintendo"},
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("instrument") == "nintendo"
    assert item.params.get("voiceMode") == "poly"
    assert item.params.get("octave") == 0
    assert item.params.get("attack") == 1
    assert item.params.get("decay") == 24
    assert item.params.get("release") == 15
    assert item.params.get("brightness") == 85

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": item.id})
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "begin playing" in item_result.message.lower()
    assert not any(
        getattr(packet, "type", "") == "item_use_sound" for packet in broadcast_payloads
    )

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"instrument": "banjo"},
            }
        ),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "instrument must be one of" in item_result.message.lower()

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": item.id,
                "params": {"voiceMode": "mono", "octave": -2},
            }
        ),
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.params.get("voiceMode") == "mono"
    assert item.params.get("octave") == -2

    await server._handle_message(
        client,
        json.dumps({"type": "item_update", "itemId": item.id, "params": {"octave": 3}}),
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "octave must be between -2 and 2" in item_result.message.lower()


@pytest.mark.asyncio
async def test_piano_note_packet_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws_sender = _fake_ws()
    sender = _activate_client(
        ClientConnection(websocket=ws_sender, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    ws_other = _fake_ws()
    other = _activate_client(
        ClientConnection(websocket=ws_other, id="u2", nickname="listener", x=7, y=6)
    )
    server.clients[ws_sender] = sender
    server.clients[ws_other] = other
    item = server.item_service.default_item(sender, "piano")
    item.params["instrument"] = "organ"
    item.params["attack"] = 20
    item.params["decay"] = 60
    item.params["emitRange"] = 12
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)

    await server._handle_message(
        sender,
        json.dumps(
            {
                "type": "item_piano_note",
                "itemId": item.id,
                "keyId": "KeyA",
                "midi": 60,
                "on": True,
            }
        ),
    )

    assert send_payloads
    packet = _last_packet_of_type(send_payloads, ItemPianoNoteBroadcastPacket)
    assert packet.itemId == item.id
    assert packet.instrument == "organ"
    assert packet.voiceMode == "poly"
    assert packet.octave == 0
    assert packet.attack == 20
    assert packet.decay == 60
    assert packet.release == 45
    assert packet.brightness == 68
    assert packet.emitRange == 12


@pytest.mark.asyncio
async def test_piano_note_key_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws_sender = _fake_ws()
    sender = _activate_client(
        ClientConnection(websocket=ws_sender, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws_sender] = sender
    ws_listener = _fake_ws()
    listener = _activate_client(
        ClientConnection(websocket=ws_listener, id="u2", nickname="listener", x=7, y=6)
    )
    server.clients[ws_listener] = listener
    item = server.item_service.default_item(sender, "piano")
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)

    for index, key_id in enumerate(
        ("KeyA", "KeyS", "KeyD", "KeyF", "KeyG", "KeyH", "KeyJ", "KeyK", "KeyL", "Semicolon", "Quote", "KeyZ")
    ):
        await server._handle_message(
            sender,
            json.dumps(
                {
                    "type": "item_piano_note",
                    "itemId": item.id,
                    "keyId": key_id,
                    "midi": 60,
                    "on": True,
                }
            ),
        )
    assert len(_packets_of_type(send_payloads, ItemPianoNoteBroadcastPacket)) == 12

    # 13th distinct held key is dropped by cap.
    await server._handle_message(
        sender,
        json.dumps(
            {
                "type": "item_piano_note",
                "itemId": item.id,
                "keyId": "KeyX",
                "midi": 60,
                "on": True,
            }
        ),
    )
    assert len(_packets_of_type(send_payloads, ItemPianoNoteBroadcastPacket)) == 12


@pytest.mark.asyncio
async def test_piano_recording_toggle_and_save(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "piano")
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_piano_recording",
                "itemId": item.id,
                "action": "toggle_record",
            }
        ),
    )
    assert (
        _packets_of_type(send_payloads, ItemPianoStatusPacket)[-1].event
        == "record_started"
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    assert item.id in server.piano_recording_state_by_item

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_piano_note",
                "itemId": item.id,
                "keyId": "KeyA",
                "midi": 60,
                "on": True,
            }
        ),
    )
    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_piano_note",
                "itemId": item.id,
                "keyId": "KeyA",
                "midi": 60,
                "on": False,
            }
        ),
    )
    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_piano_recording",
                "itemId": item.id,
                "action": "toggle_record",
            }
        ),
    )
    assert (
        _packets_of_type(send_payloads, ItemPianoStatusPacket)[-1].event
        == "record_paused"
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert item_result.message == "Recording paused."
    assert item.id in server.piano_recording_state_by_item

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_piano_recording", "itemId": item.id, "action": "stop_record"}
        ),
    )
    assert (
        _packets_of_type(send_payloads, ItemPianoStatusPacket)[-1].event
        == "record_stopped"
    )
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert item_result.message == "Recording stopped."
    assert item.id not in server.piano_recording_state_by_item
    song_id = item.params.get("songId")
    assert isinstance(song_id, str)
    payload = server.item_service.piano_songs.get(song_id)
    assert isinstance(payload, dict)
    keys = payload.get("keys")
    states = payload.get("states")
    events = payload.get("events")
    assert isinstance(keys, list) and "KeyA" in keys
    assert isinstance(states, list) and len(states) >= 1
    assert isinstance(events, list) and len(events) >= 2


@pytest.mark.asyncio
async def test_piano_playback_starts_task(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "piano")
    item.params["songId"] = "item:test-song"
    server.item_service.piano_songs["item:test-song"] = {
        "meta": {
            "instrument": "piano",
            "voiceMode": "poly",
            "attack": 15,
            "decay": 45,
            "release": 35,
            "brightness": 55,
            "emitRange": 15,
        },
        "keys": ["KeyA"],
        "states": [["piano", "poly", 15, 45, 35, 55, 15]],
        "events": [[0, 0, 60, 1, 0]],
    }
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    playback_started: list[str] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return

    async def fake_start_playback(current_item) -> None:
        playback_started.append(current_item.id)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server, "_start_piano_playback", fake_start_playback)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_piano_recording", "itemId": item.id, "action": "playback"}
        ),
    )
    assert (
        _packets_of_type(send_payloads, ItemPianoStatusPacket)[-1].event
        == "playback_started"
    )
    assert _last_packet_of_type(send_payloads, ItemActionResultPacket).ok is True
    task = server.piano_playback_tasks_by_item.get(item.id)
    assert task is not None
    await task
    assert playback_started == [item.id]
