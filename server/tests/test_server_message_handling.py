from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
from time import monotonic
from typing import Sequence, TypeVar, cast
import uuid

import pytest
from websockets.asyncio.server import ServerConnection

from app.client import ClientConnection
from app.auth_service import AuthError
from app.models import (
    BasePacket,
    BroadcastChatMessagePacket,
    BroadcastPositionPacket,
    BroadcastTeleportCompletePacket,
    AdminActionResultPacket,
    AdminNotificationsListResultPacket,
    AdminPlatformOverviewResultPacket,
    AuthResultPacket,
    DirectMessageBroadcastPacket,
    ItemActionResultPacket,
    ItemGameLaunchPacket,
    ItemTransferTargetsResultPacket,
    LocationChangedPacket,
    PongPacket,
    SocialActionPacket,
    UserActionResultPacket,
    WelcomePacket,
    WorldItem,
)
from app.server import (
    AUTH_LOGIN_FAILURE_MESSAGE,
    AUTH_RESUME_FAILURE_MESSAGE,
    SignalingServer,
)
from app.item_type_handlers import get_item_type_handler

PacketT = TypeVar("PacketT", bound=BasePacket)


def _fake_ws() -> ServerConnection:
    return cast(ServerConnection, object())


def _packet_types(payloads: list[object]) -> list[str]:
    return [getattr(packet, "type", "") for packet in payloads]


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
    user_id: str | None = None,
    username: str | None = None,
    permissions: set[str] | None = None,
) -> ClientConnection:
    client.authenticated = True
    client.user_id = user_id or client.user_id or client.id
    client.username = username or client.username or client.nickname
    client.permissions = set(permissions or client.permissions or set())
    client.world_ready = True
    return client


def test_client_ip_prefers_forwarded_for_from_loopback_proxy() -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = cast(
        ServerConnection,
        SimpleNamespace(
            remote_address=("127.0.0.1", 12345),
            request=SimpleNamespace(
                headers={"X-Forwarded-For": "203.0.113.10, 198.51.100.25"}
            ),
        ),
    )
    client = ClientConnection(websocket=ws, id="u1", nickname="tester")
    assert server._client_ip(client) == "198.51.100.25"


def test_client_ip_ignores_forwarded_for_from_non_loopback_peer() -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = cast(
        ServerConnection,
        SimpleNamespace(
            remote_address=("203.0.113.20", 12345),
            request=SimpleNamespace(headers={"X-Forwarded-For": "198.51.100.25"}),
        ),
    )
    client = ClientConnection(websocket=ws, id="u1", nickname="tester")
    assert server._client_ip(client) == "203.0.113.20"


def test_resolve_client_version_metadata_reads_release_and_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version_text = """
window.CHGRID_RELEASE_VERSION = "0.1.1";
window.CHGRID_CLIENT_REVISION = "R350";
""".strip()
    resolved = SignalingServer._client_version_metadata_from_web_version_text(
        version_text
    )

    assert resolved == ("0.1.1", "R350")


def test_ecrypto_command_links_wallet_and_reports_balance(tmp_path: Path) -> None:
    server = SignalingServer(
        "127.0.0.1", 8765, None, None, auth_db_path=tmp_path / "auth.db"
    )
    try:
        session = server.auth_service.register("alpha", "password99")
        client = _activate_client(
            ClientConnection(websocket=_fake_ws(), id="u1", nickname="Alpha"),
            user_id=session.user.id,
            username=session.user.username,
            permissions={"item.use", "chat.send"},
        )

        linked = server._handle_ecrypto_command(
            client, "connect-source real ethereum 0xabc123 dom-windows main"
        )
        assert "Real-chain wallet linked" in linked
        assert "dom-windows" in linked
        assert "no real-chain transaction" in linked

        deposited = server._handle_ecrypto_command(client, "faucet 150")
        assert "Balance: 150 TEST-ECR" in deposited

        balance = server._handle_ecrypto_command(client, "balance")
        assert "@alpha" in balance
        assert "150 TEST-ECR" in balance
        assert "(0 test, 1 real)" in balance
        wallets = server._handle_ecrypto_command(client, "wallets")
        assert "from dom-windows" in wallets
    finally:
        server.auth_service.close()


def test_ecrypto_inventory_requires_privileged_agent_or_admin(tmp_path: Path) -> None:
    server = SignalingServer(
        "127.0.0.1", 8765, None, None, auth_db_path=tmp_path / "auth.db"
    )
    try:
        alpha = server.auth_service.register("alpha", "password99")
        beta = server.auth_service.register("beta", "password99")
        server.auth_service.ecrypto_test_deposit(beta.user.id, 40)
        normal_client = _activate_client(
            ClientConnection(websocket=_fake_ws(), id="u1", nickname="Alpha"),
            user_id=alpha.user.id,
            username=alpha.user.username,
            permissions={"chat.send"},
        )
        assert "Not authorized" in server._handle_ecrypto_command(
            normal_client, "inventory"
        )

        admin_client = _activate_client(
            ClientConnection(websocket=_fake_ws(), id="admin", nickname="Admin"),
            user_id=alpha.user.id,
            username=alpha.user.username,
            permissions={"server.manage_settings"},
        )
        inventory = server._handle_ecrypto_command(admin_client, "inventory")
        assert "@alpha" in inventory
        assert "@beta" in inventory
        assert "40 TEST-ECR" in inventory
    finally:
        server.auth_service.close()


def test_ecrypto_transfer_command_uses_test_chain_accounts(tmp_path: Path) -> None:
    server = SignalingServer(
        "127.0.0.1", 8765, None, None, auth_db_path=tmp_path / "auth.db"
    )
    try:
        alpha = server.auth_service.register("alpha", "password99")
        beta = server.auth_service.register("beta", "password99")
        client = _activate_client(
            ClientConnection(websocket=_fake_ws(), id="u1", nickname="Alpha"),
            user_id=alpha.user.id,
            username=alpha.user.username,
            permissions={"item.use", "chat.send"},
        )
        server.auth_service.ecrypto_test_deposit(alpha.user.id, 200)

        result = server._handle_ecrypto_command(client, "transfer beta 75 for snacks")

        assert "Sent 75 TEST-ECR to @beta" in result
        assert "125 TEST-ECR" in result
        assert server.auth_service.get_ecrypto_account_summary(beta.user.id).test_balance == 75
    finally:
        server.auth_service.close()


def test_ecrypto_bank_use_text_is_linked_to_logged_in_user(tmp_path: Path) -> None:
    server = SignalingServer(
        "127.0.0.1", 8765, None, None, auth_db_path=tmp_path / "auth.db"
    )
    try:
        session = server.auth_service.register("alpha", "password99")
        client = _activate_client(
            ClientConnection(websocket=_fake_ws(), id="u1", nickname="Alpha"),
            user_id=session.user.id,
            username=session.user.username,
            permissions={"item.use"},
        )
        item = server.items["seed-town-ecrypto-bank"]
        server.auth_service.ecrypto_test_deposit(session.user.id, 25)

        text = server._ecrypto_bank_use_text(client, item)

        assert "Crypto eCrypto Bank" in text
        assert "@alpha" in text
        assert "25 TEST-ECR" in text
        assert "Secondary use enters the bank lobby" in text
    finally:
        server.auth_service.close()


@pytest.mark.asyncio
async def test_ecrypto_bank_secondary_use_enters_lobby(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = SignalingServer(
        "127.0.0.1", 8765, None, None, auth_db_path=tmp_path / "auth.db"
    )
    try:
        session = server.auth_service.register("alpha", "password99")
        ws = _fake_ws()
        client = _activate_client(
            ClientConnection(
                websocket=ws,
                id="u1",
                nickname="Alpha",
                x=20,
                y=18,
                location_id="town",
            ),
            user_id=session.user.id,
            username=session.user.username,
            permissions={"item.use"},
        )
        server.clients[ws] = client
        item = server.items["seed-town-ecrypto-bank"]
        send_payloads: list[object] = []
        changed_locations: list[str] = []

        async def fake_send(websocket: ServerConnection, packet: object) -> None:
            send_payloads.append(packet)

        async def fake_change_location(
            target_client: ClientConnection, location_id: str
        ) -> None:
            changed_locations.append(location_id)
            target_client.location_id = location_id

        monkeypatch.setattr(server, "_send", fake_send)
        monkeypatch.setattr(server, "_change_client_location", fake_change_location)

        await server._handle_message(
            client, json.dumps({"type": "item_secondary_use", "itemId": item.id})
        )

        assert changed_locations == ["ecrypto_bank_lobby"]
        result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
        assert result.ok is True
        assert "Entering the bank lobby" in result.message
    finally:
        server.auth_service.close()


def test_ecrypto_wallet_item_is_portable_and_readable() -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    try:
        client = _activate_client(
            ClientConnection(websocket=_fake_ws(), id="u1", nickname="Alpha"),
            permissions={"item.add"},
        )
        wallet = server.item_service.default_item(client, "ecrypto_wallet")
        wallet.params = {
            **wallet.params,
            "address": "test_alpha_001",
            "walletLabel": "walking wallet",
        }
        handler = get_item_type_handler(wallet.type)

        result = handler.use(wallet, client.nickname, server._format_clock_display_time)

        assert "carry it with you" in result.self_message
        assert "test_alpha_001" in result.self_message
        assert "carryable" in wallet.capabilities
    finally:
        server.auth_service.close()


@pytest.mark.asyncio
async def test_update_position_rejects_out_of_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6)
    server.clients[ws] = client

    broadcast_payloads: list[object] = []

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_broadcast", fake_broadcast)

    await server._handle_message(
        client, json.dumps({"type": "update_position", "x": 200, "y": -5})
    )

    assert client.x == 5
    assert client.y == 6
    assert broadcast_payloads == []


@pytest.mark.asyncio
async def test_direct_message_sends_only_to_target_and_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    sender_ws = _fake_ws()
    target_ws = cast(ServerConnection, object())
    bystander_ws = cast(ServerConnection, object())
    sender = _activate_client(
        ClientConnection(websocket=sender_ws, id="u1", nickname="Alice", x=5, y=5),
        permissions={"chat.send"},
    )
    target = _activate_client(
        ClientConnection(websocket=target_ws, id="u2", nickname="Bob", x=6, y=5),
        permissions={"chat.send"},
    )
    bystander = _activate_client(
        ClientConnection(websocket=bystander_ws, id="u3", nickname="Casey", x=8, y=8),
        permissions={"chat.send"},
    )
    server.clients[sender_ws] = sender
    server.clients[target_ws] = target
    server.clients[bystander_ws] = bystander

    sent_payloads: dict[ServerConnection, list[object]] = {
        sender_ws: [],
        target_ws: [],
        bystander_ws: [],
    }

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads[websocket].append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        sender,
        json.dumps(
            {
                "type": "direct_message",
                "targetId": "u2",
                "message": "private hello",
            }
        ),
    )

    target_dm = _last_packet_of_type(
        sent_payloads[target_ws], DirectMessageBroadcastPacket
    )
    sender_dm = _last_packet_of_type(
        sent_payloads[sender_ws], DirectMessageBroadcastPacket
    )
    assert target_dm.message == "private hello"
    assert target_dm.senderNickname == "Alice"
    assert target_dm.targetNickname == "Bob"
    assert target_dm.outgoing is False
    assert sender_dm.outgoing is True
    assert sent_payloads[bystander_ws] == []


@pytest.mark.asyncio
async def test_user_action_broadcasts_contextual_social_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    sender_ws = _fake_ws()
    target_ws = cast(ServerConnection, object())
    sender = _activate_client(
        ClientConnection(websocket=sender_ws, id="u1", nickname="Alice", x=5, y=5)
    )
    target = _activate_client(
        ClientConnection(websocket=target_ws, id="u2", nickname="Bob", x=6, y=5)
    )
    server.clients[sender_ws] = sender
    server.clients[target_ws] = target
    sent_payloads: dict[ServerConnection, list[object]] = {sender_ws: [], target_ws: []}

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads[websocket].append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        sender,
        json.dumps(
            {"type": "user_action", "actionId": "tap_shoulder", "targetId": "u2"}
        ),
    )

    target_action = _last_packet_of_type(sent_payloads[target_ws], SocialActionPacket)
    sender_result = _last_packet_of_type(
        sent_payloads[sender_ws], UserActionResultPacket
    )
    assert target_action.actionId == "tap_shoulder"
    assert target_action.actorNickname == "Alice"
    assert target_action.targetNickname == "Bob"
    assert "taps Bob" in target_action.message
    assert target_action.sound == "/sounds/reactions/tap_shoulder.mp3"
    assert sender_result.ok is True
    assert sender_result.targetId == "u2"


@pytest.mark.asyncio
async def test_user_action_hug_broadcasts_spatial_reaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    sender_ws = _fake_ws()
    target_ws = cast(ServerConnection, object())
    sender = _activate_client(
        ClientConnection(websocket=sender_ws, id="u1", nickname="Clawdia", x=5, y=5)
    )
    target = _activate_client(
        ClientConnection(websocket=target_ws, id="u2", nickname="Dom", x=6, y=5)
    )
    server.clients[sender_ws] = sender
    server.clients[target_ws] = target
    sent_payloads: dict[ServerConnection, list[object]] = {sender_ws: [], target_ws: []}

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads[websocket].append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        sender,
        json.dumps({"type": "user_action", "actionId": "hug", "targetId": "u2"}),
    )

    target_action = _last_packet_of_type(sent_payloads[target_ws], SocialActionPacket)
    sender_result = _last_packet_of_type(
        sent_payloads[sender_ws], UserActionResultPacket
    )
    assert target_action.actionId == "hug"
    assert target_action.actorNickname == "Clawdia"
    assert target_action.targetNickname == "Dom"
    assert target_action.message == "Clawdia hugs Dom."
    assert target_action.sound == "/sounds/reactions/hug.mp3"
    assert (target_action.x, target_action.y) == (6, 5)
    assert sender_result.ok is True
    assert sender_result.message == "Clawdia hugs Dom."
    assert sender_result.targetId == "u2"


@pytest.mark.asyncio
async def test_user_action_playful_smack_broadcasts_spatial_reaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    sender_ws = _fake_ws()
    target_ws = cast(ServerConnection, object())
    sender = _activate_client(
        ClientConnection(websocket=sender_ws, id="u1", nickname="Clawdia", x=5, y=5)
    )
    target = _activate_client(
        ClientConnection(websocket=target_ws, id="u2", nickname="Dom", x=6, y=5)
    )
    server.clients[sender_ws] = sender
    server.clients[target_ws] = target
    sent_payloads: dict[ServerConnection, list[object]] = {sender_ws: [], target_ws: []}

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads[websocket].append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        sender,
        json.dumps({"type": "user_action", "actionId": "playful_smack", "targetId": "u2"}),
    )

    target_action = _last_packet_of_type(sent_payloads[target_ws], SocialActionPacket)
    sender_result = _last_packet_of_type(
        sent_payloads[sender_ws], UserActionResultPacket
    )
    assert target_action.actionId == "playful_smack"
    assert target_action.message == "Clawdia gives Dom a playful smack."
    assert target_action.sound == "/sounds/reactions/playful_smack.mp3"
    assert sender_result.ok is True


@pytest.mark.asyncio
async def test_social_reaction_slash_commands_include_new_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    sender_ws = _fake_ws()
    target_ws = cast(ServerConnection, object())
    sender = _activate_client(
        ClientConnection(websocket=sender_ws, id="u1", nickname="Clawdia", x=5, y=5)
    )
    target = _activate_client(
        ClientConnection(websocket=target_ws, id="u2", nickname="Dom", x=6, y=5)
    )
    server.clients[sender_ws] = sender
    server.clients[target_ws] = target
    broadcast_payloads: list[object] = []

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    assert await server._handle_chat_command(sender, "/highfive Dom") is True
    assert await server._handle_chat_command(sender, "/smack Dom") is True

    high_five = _last_packet_of_type(broadcast_payloads[:-1], SocialActionPacket)
    playful_smack = _last_packet_of_type(broadcast_payloads, SocialActionPacket)
    assert high_five.actionId == "high_five"
    assert high_five.message == "Clawdia high-fives Dom."
    assert high_five.sound == "/sounds/reactions/high_five.mp3"
    assert playful_smack.actionId == "playful_smack"
    assert playful_smack.message == "Clawdia gives Dom a playful smack."
    assert playful_smack.sound == "/sounds/reactions/playful_smack.mp3"


@pytest.mark.asyncio
async def test_user_action_rejects_target_in_other_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    sender_ws = _fake_ws()
    target_ws = cast(ServerConnection, object())
    sender = _activate_client(
        ClientConnection(websocket=sender_ws, id="u1", nickname="Alice", x=5, y=5)
    )
    target = _activate_client(
        ClientConnection(
            websocket=target_ws, id="u2", nickname="Bob", location_id="arcade", x=6, y=5
        )
    )
    server.clients[sender_ws] = sender
    server.clients[target_ws] = target
    sent_payloads: dict[ServerConnection, list[object]] = {sender_ws: [], target_ws: []}

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads[websocket].append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        sender,
        json.dumps(
            {"type": "user_action", "actionId": "tap_shoulder", "targetId": "u2"}
        ),
    )

    sender_result = _last_packet_of_type(
        sent_payloads[sender_ws], UserActionResultPacket
    )
    assert sender_result.ok is False
    assert sender_result.message == "That user is no longer nearby."
    assert sent_payloads[target_ws] == []


@pytest.mark.asyncio
async def test_direct_message_rejects_target_in_other_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    sender_ws = _fake_ws()
    target_ws = cast(ServerConnection, object())
    sender = _activate_client(
        ClientConnection(websocket=sender_ws, id="u1", nickname="Alice", x=5, y=5),
        permissions={"chat.send"},
    )
    target = _activate_client(
        ClientConnection(websocket=target_ws, id="u2", nickname="Bob", x=6, y=5),
        permissions={"chat.send"},
    )
    target.location_id = "arcade"
    server.clients[sender_ws] = sender
    server.clients[target_ws] = target

    sent_payloads: dict[ServerConnection, list[object]] = {
        sender_ws: [],
        target_ws: [],
    }

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads[websocket].append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        sender,
        json.dumps(
            {
                "type": "direct_message",
                "targetId": "u2",
                "message": "private hello",
            }
        ),
    )

    error = _last_packet_of_type(sent_payloads[sender_ws], BroadcastChatMessagePacket)
    assert error.system is True
    assert error.message == "That user is not available for direct messages."
    assert sent_payloads[target_ws] == []


@pytest.mark.asyncio
async def test_raywonder_studio_door_knock_and_allow_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    guest_ws = _fake_ws()
    host_ws = cast(ServerConnection, object())
    guest = _activate_client(
        ClientConnection(
            websocket=guest_ws,
            id="guest-1",
            nickname="Matthew",
            x=22,
            y=20,
            location_id="raywonder_house_entry",
        ),
        permissions={"item.use", "chat.send"},
    )
    host = _activate_client(
        ClientConnection(
            websocket=host_ws,
            id="host-1",
            nickname="Dom",
            x=22,
            y=20,
            location_id="raywonder_house_studio",
        ),
        permissions={"item.use", "chat.send"},
    )
    server.clients[guest_ws] = guest
    server.clients[host_ws] = host
    door = server.items["seed-raywonder-entry-door-studio"]
    assert door.params["doorState"] == "locked"

    sent_payloads: dict[ServerConnection, list[object]] = {
        guest_ws: [],
        host_ws: [],
    }

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads[websocket].append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        guest,
        json.dumps({"type": "item_use", "itemId": door.id}),
    )

    knock_result = _last_packet_of_type(
        sent_payloads[guest_ws], ItemActionResultPacket
    )
    host_notice = _last_packet_of_type(
        sent_payloads[host_ws], BroadcastChatMessagePacket
    )
    assert knock_result.message == "You knock on the studio door."
    assert "Matthew knocks on the studio door" in host_notice.message
    assert guest.location_id == "raywonder_house_entry"

    await server._handle_message(
        host,
        json.dumps({"type": "chat_message", "message": "/allow Matthew"}),
    )
    guest_notice = _last_packet_of_type(
        sent_payloads[guest_ws], BroadcastChatMessagePacket
    )
    assert "allows you into the studio" in guest_notice.message

    await server._handle_message(
        guest,
        json.dumps({"type": "item_use", "itemId": door.id}),
    )

    arrival = _last_packet_of_type(sent_payloads[guest_ws], LocationChangedPacket)
    assert arrival.locationId == "raywonder_house_studio"
    assert guest.location_id == "raywonder_house_studio"


@pytest.mark.asyncio
async def test_locked_bedroom_door_unlocks_with_key_on_square(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    guest_ws = _fake_ws()
    guest = _activate_client(
        ClientConnection(
            websocket=guest_ws,
            id="guest-1",
            nickname="Dom",
            x=20,
            y=24,
            location_id="raywonder_house_entry",
        ),
        permissions={"item.use", "chat.send"},
    )
    server.clients[guest_ws] = guest
    door = server.items["seed-raywonder-entry-door-bedroom"]
    key = server.items["seed-raywonder-entry-bedroom-key"]
    assert door.params["doorState"] == "locked"
    assert key.params["keyId"] == door.params["requiredKeyId"]

    sent_payloads: dict[ServerConnection, list[object]] = {guest_ws: []}

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads[websocket].append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        guest,
        json.dumps({"type": "item_use", "itemId": door.id}),
    )

    result = _last_packet_of_type(sent_payloads[guest_ws], ItemActionResultPacket)
    assert result.ok is True
    assert "Bedroom door unlocks with Bedroom key." in result.message
    assert door.params["doorState"] == "unlocked"
    assert guest.location_id == "raywonder_house_bedroom"


@pytest.mark.asyncio
async def test_cabin_use_with_target_location_enters_real_navigable_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            x=5,
            y=5,
            location_id="forest",
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    cabin = server.item_service.default_item(client, "cabin")
    cabin.title = "Pine cabin"
    cabin.x = 5
    cabin.y = 5
    cabin.locationId = "forest"
    cabin.params["placeName"] = "Pine cabin"
    cabin.params["targetLocation"] = "town"
    server.item_service.add_item(cabin)

    sent_payloads: list[object] = []
    broadcast_payloads: list[tuple[str, object, ServerConnection | None]] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append((location_id, packet, exclude))

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": cabin.id})
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    arrival = _last_packet_of_type(sent_payloads, LocationChangedPacket)
    arrival_chat = _last_packet_of_type(sent_payloads, BroadcastChatMessagePacket)
    assert result.ok is True
    assert "You enter the cabin" in result.message
    assert client.location_id == "town"
    assert arrival.locationId == "town"
    assert arrival.x == 18
    assert arrival.y == 18
    assert "You arrive in Town" in arrival_chat.message
    assert any(
        location_id == "forest"
        and isinstance(packet, BroadcastChatMessagePacket)
        and "left for Town" in packet.message
        for location_id, packet, _exclude in broadcast_payloads
    )


@pytest.mark.asyncio
async def test_raywonder_studio_allow_requires_inside_studio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            x=22,
            y=20,
            location_id="raywonder_house_entry",
        ),
        permissions={"chat.send"},
    )
    server.clients[ws] = client
    sent_payloads: dict[ServerConnection, list[object]] = {ws: []}

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads[websocket].append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client,
        json.dumps({"type": "chat_message", "message": "/allow Matthew"}),
    )

    error = _last_packet_of_type(sent_payloads[ws], BroadcastChatMessagePacket)
    assert error.message == "You need to be inside the studio to allow someone in."


@pytest.mark.asyncio
async def test_radio_metadata_refresh_updates_station_and_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = ClientConnection(websocket=ws, id="u1", nickname="tester", x=10, y=10)
    server.clients[ws] = client

    radio = server.item_service.default_item(client, "radio_station")
    radio.params["streamUrl"] = "http://example.com/stream"
    radio.params["enabled"] = True
    radio.params["emitRange"] = 10
    radio.params["stationName"] = ""
    radio.params["nowPlaying"] = ""
    server.item_service.add_item(radio)

    async def fake_broadcast_item(item: object) -> None:
        return None

    def fake_fetch(url: str) -> tuple[str, str, str]:
        assert url == "http://example.com/stream"
        return ("Test Station", "Test Song", "")

    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_fetch_stream_metadata", fake_fetch)

    await server._refresh_radio_metadata_once()

    assert radio.params["stationName"] == "Test Station"
    assert radio.params["nowPlaying"] == "Test Song"


@pytest.mark.asyncio
async def test_welcome_resolves_enabled_radio_playback_before_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    server.item_service.items.clear()
    ws = _fake_ws()
    client = ClientConnection(
        websocket=ws,
        id="u1",
        nickname="tester",
        x=10,
        y=10,
        location_id="raywonder_house_living_room",
    )
    server.clients[ws] = client

    radio = server.item_service.default_item(client, "radio_station")
    radio.locationId = "raywonder_house_living_room"
    radio.x = 24
    radio.y = 20
    radio.params["streamUrl"] = "https://aaastreamer.example/s/soulfoodradio-media"
    radio.params["playbackUrl"] = ""
    radio.params["enabled"] = True
    radio.params["stationName"] = "SoulFoodRadio"
    radio.params["nowPlaying"] = ""
    radio.params["playStartedAt"] = 0
    server.item_service.add_item(radio)

    sent_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_ensure_builtin_items_and_broadcast() -> None:
        return None

    def fake_fetch(url: str) -> tuple[str, str, str]:
        assert url == "https://aaastreamer.example/s/soulfoodradio-media"
        return (
            "SoulFoodRadio",
            "A song",
            "https://aaastreamer.example/hls/live/sk_test/index.m3u8",
        )

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(
        server,
        "_ensure_builtin_items_and_broadcast",
        fake_ensure_builtin_items_and_broadcast,
    )
    monkeypatch.setattr(server, "_fetch_stream_metadata", fake_fetch)
    monkeypatch.setattr(server, "_request_state_save", lambda: None)

    await server._send_welcome(client)

    welcome = _last_packet_of_type(sent_payloads, WelcomePacket)
    welcome_radio = next(item for item in (welcome.items or []) if item["id"] == radio.id)
    assert welcome_radio["params"]["playbackUrl"].endswith("/hls/live/sk_test/index.m3u8")
    assert welcome_radio["params"]["nowPlaying"] == "A song"
    assert welcome_radio["params"]["playStartedAt"] > 0


@pytest.mark.asyncio
async def test_radio_metadata_refresh_skips_when_no_listener_in_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = ClientConnection(websocket=ws, id="u1", nickname="tester", x=0, y=0)
    server.clients[ws] = client

    radio = server.item_service.default_item(client, "radio_station")
    radio.x = 30
    radio.y = 30
    radio.params["streamUrl"] = "http://example.com/stream"
    radio.params["enabled"] = True
    radio.params["emitRange"] = 5
    server.item_service.add_item(radio)

    called = False

    def fake_fetch(url: str) -> tuple[str, str]:
        nonlocal called
        called = True
        return ("X", "Y")

    monkeypatch.setattr(server, "_fetch_stream_metadata", fake_fetch)

    await server._refresh_radio_metadata_once()

    assert called is False


@pytest.mark.asyncio
async def test_item_secondary_use_radio_reports_now_playing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=5),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    radio = server.item_service.default_item(client, "radio_station")
    radio.x = 5
    radio.y = 5
    radio.params["enabled"] = True
    radio.params["stationName"] = "Station X"
    radio.params["nowPlaying"] = "Song Y"
    server.item_service.add_item(radio)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        client, json.dumps({"type": "item_secondary_use", "itemId": radio.id})
    )

    results = _packets_of_type(send_payloads, ItemActionResultPacket)
    assert results
    assert results[-1].ok is True
    assert results[-1].action == "secondary_use"
    assert "Playing Song Y from Station X." in results[-1].message
    assert broadcast_payloads == []


@pytest.mark.asyncio
async def test_radio_use_sets_play_started_at_when_switched_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=5),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    radio = server.item_service.default_item(client, "radio_station")
    radio.x = 5
    radio.y = 5
    radio.params["enabled"] = False
    radio.params["streamUrl"] = "https://example.com/live.mp3"
    radio.params["playStartedAt"] = 0
    server.item_service.add_item(radio)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        return None

    async def fake_resolve(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": radio.id})
    )

    result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert radio.params["enabled"] is True
    assert radio.params["playStartedAt"] > 0


@pytest.mark.asyncio
async def test_active_tv_switches_off_linked_music_radio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    tv = server.item_service.default_item(client, "house_object")
    tv.id = "living-tv"
    tv.title = "Living room TV"
    tv.locationId = client.location_id
    tv.x = 5
    tv.y = 5
    tv.params["objectKind"] = "tv"
    tv.params["placement"] = "wall"
    tv.params["enabled"] = False
    tv.params["linkedMediaGroup"] = "living-media"
    tv.params["streamUrl"] = "https://example.com/tv-live.mp3"
    tv.params["stationName"] = "Movie Channel"
    server.item_service.add_item(tv)

    radio = server.item_service.default_item(client, "radio_station")
    radio.id = "living-radio"
    radio.title = "Living room radio"
    radio.locationId = client.location_id
    radio.params["enabled"] = True
    radio.params["playStartedAt"] = 123
    radio.params["linkedMediaGroup"] = "living-media"
    radio.params["stationPresets"] = [
        {"title": "Music", "streamUrl": "https://example.com/music.mp3"}
    ]
    server.item_service.add_item(radio)

    sent_payloads: list[object] = []
    broadcast_items: list[str] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(getattr(item, "id", ""))

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return None

    async def fake_resolve(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": tv.id})
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert tv.params["enabled"] is True
    assert radio.params["enabled"] is False
    assert radio.params["playStartedAt"] == 0
    assert broadcast_items == ["living-tv", "living-radio"]


@pytest.mark.asyncio
async def test_active_tv_syncs_linked_speaker_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    tv = server.item_service.default_item(client, "house_object")
    tv.id = "living-tv"
    tv.title = "Living room TV"
    tv.locationId = client.location_id
    tv.x = 5
    tv.y = 5
    tv.params["objectKind"] = "tv"
    tv.params["placement"] = "wall"
    tv.params["enabled"] = False
    tv.params["linkedMediaGroup"] = "living-media"
    tv.params["streamUrl"] = "https://example.com/tv-live.mp3"
    tv.params["playbackUrl"] = "https://example.com/tv-live-resolved.mp3"
    tv.params["stationIndex"] = 4
    tv.params["stationName"] = "Movie Channel"
    tv.params["nowPlaying"] = "Feature Audio"
    server.item_service.add_item(tv)

    speaker = server.item_service.default_item(client, "radio_station")
    speaker.id = "living-sub"
    speaker.title = "Living room subwoofer"
    speaker.locationId = client.location_id
    speaker.params["enabled"] = False
    speaker.params["linkedMediaGroup"] = "living-media"
    speaker.params["speakerRole"] = "sub"
    speaker.params["syncWithPrimary"] = True
    speaker.params["streamUrl"] = ""
    speaker.params["playbackUrl"] = ""
    speaker.params["stationName"] = ""
    speaker.params["nowPlaying"] = ""
    server.item_service.add_item(speaker)

    sent_payloads: list[object] = []
    broadcast_items: list[str] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(getattr(item, "id", ""))

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return None

    async def fake_resolve(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": tv.id})
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert speaker.params["enabled"] is True
    assert speaker.params["streamUrl"] == "https://example.com/tv-live.mp3"
    assert speaker.params["playbackUrl"] == "https://example.com/tv-live-resolved.mp3"
    assert speaker.params["stationIndex"] == 4
    assert speaker.params["stationName"] == "Movie Channel"
    assert speaker.params["nowPlaying"] == "Feature Audio"
    assert speaker.params["playStartedAt"] > 0
    assert broadcast_items == ["living-tv", "living-sub"]


@pytest.mark.asyncio
async def test_house_object_bed_cycles_sit_lie_stand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=5),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    bed = server.item_service.default_item(client, "house_object")
    bed.id = "bed-1"
    bed.title = "Bedroom bed"
    bed.x = 6
    bed.y = 5
    bed.params["objectKind"] = "bed"
    bed.params["placement"] = "furniture"
    server.item_service.add_item(bed)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": bed.id})
    )

    first_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    first_position = _last_packet_of_type(send_payloads, BroadcastPositionPacket)
    assert first_result.ok is True
    assert first_result.message == "You sit on Bedroom bed."
    assert client.seated_item_id == bed.id
    assert client.posture == "sitting"
    assert first_position.posture == "sitting"

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": bed.id})
    )

    second_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    second_position = _last_packet_of_type(send_payloads, BroadcastPositionPacket)
    assert second_result.ok is True
    assert second_result.message == "You lie down on Bedroom bed."
    assert client.seated_item_id == bed.id
    assert client.posture == "lying"
    assert second_position.posture == "lying"

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": bed.id})
    )

    third_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    third_position = _last_packet_of_type(send_payloads, BroadcastPositionPacket)
    assert third_result.ok is True
    assert third_result.message == "You get up from Bedroom bed."
    assert client.seated_item_id is None
    assert client.posture == "standing"
    assert third_position.posture == "standing"


@pytest.mark.asyncio
async def test_seated_user_can_walk_away_from_couch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=5),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    couch = server.item_service.default_item(client, "house_object")
    couch.id = "couch-1"
    couch.title = "Living room couch"
    couch.x = 6
    couch.y = 5
    couch.params["objectKind"] = "couch"
    couch.params["placement"] = "floor"
    couch.params["postureMode"] = "sit"
    couch.params["seatingCapacity"] = 4
    server.item_service.add_item(couch)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": couch.id})
    )

    assert client.x == couch.x
    assert client.y == couch.y
    assert client.seated_item_id == couch.id
    assert client.posture == "sitting"

    await server._handle_message(
        client, json.dumps({"type": "update_position", "x": 7, "y": 5})
    )

    position = _last_packet_of_type(send_payloads, BroadcastPositionPacket)
    self_messages = [
        packet.message
        for packet in send_payloads
        if isinstance(packet, BroadcastChatMessagePacket)
    ]
    peer_messages = [
        packet.message
        for packet in broadcast_payloads
        if isinstance(packet, BroadcastChatMessagePacket)
    ]
    assert client.x == 7
    assert client.y == 5
    assert client.seated_item_id is None
    assert client.posture == "standing"
    assert position.posture == "standing"
    assert position.seatedItemId is None
    assert "You get up from Living room couch." in self_messages
    assert "tester gets up from Living room couch." in peer_messages
    assert "Stand up before moving away from the furniture." not in self_messages


@pytest.mark.asyncio
async def test_radio_remote_tuning_error_returns_item_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    radio = server.item_service.default_item(client, "radio_station")
    radio.id = "radio-1"
    radio.title = "Living room radio"
    radio.locationId = client.location_id
    radio.x = 5
    radio.y = 6
    radio.params["stationPresets"] = [
        {"title": "One", "streamUrl": "https://example.com/one.mp3"},
        {"title": "Two", "streamUrl": "https://retired.invalid/two.mp3"},
    ]
    radio.params["stationIndex"] = 0
    server.item_service.add_item(radio)

    remote = server.item_service.default_item(client, "house_object")
    remote.id = "remote-1"
    remote.title = "Universal radio remote"
    remote.locationId = client.location_id
    remote.x = client.x
    remote.y = client.y
    remote.params["objectKind"] = "remote"
    remote.params["description"] = "A programmable radio remote."
    server.item_service.add_item(remote)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_apply_radio_station_index(*args, **kwargs) -> None:
        raise ValueError("DNS resolution failed.")

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(
        server, "_apply_radio_station_index", fake_apply_radio_station_index
    )

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": remote.id})
    )

    result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert result.ok is False
    assert result.action == "use"
    assert result.itemId == remote.id
    assert "Remote could not tune Living room radio" in result.message


@pytest.mark.asyncio
async def test_carried_radio_remote_station_previous_syncs_connected_radios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    presets = [
        {"title": "One", "streamUrl": "https://example.com/one.mp3"},
        {
            "title": "Two",
            "streamUrl": "https://example.com/two.mp3",
            "switchSound": "sounds/radio/station-switch/two.mp3",
        },
        {"title": "Three", "streamUrl": "https://example.com/three.mp3"},
    ]

    primary = server.item_service.default_item(client, "radio_station")
    primary.id = "living-radio"
    primary.title = "Living room radio"
    primary.locationId = client.location_id
    primary.x = 5
    primary.y = 6
    primary.params["linkedMediaGroup"] = "test-house-radios"
    primary.params["stationPresets"] = presets
    primary.params["stationIndex"] = 0
    server.item_service.add_item(primary)

    kitchen = server.item_service.default_item(client, "radio_station")
    kitchen.id = "kitchen-radio"
    kitchen.title = "Kitchen radio"
    kitchen.locationId = "raywonder_house_kitchen"
    kitchen.params["linkedMediaGroup"] = "test-house-radios"
    kitchen.params["stationPresets"] = presets
    kitchen.params["stationIndex"] = 0
    server.item_service.add_item(kitchen)

    remote = server.item_service.default_item(client, "house_object")
    remote.id = "remote-1"
    remote.title = "Universal radio remote"
    remote.locationId = client.location_id
    remote.carrierId = client.id
    remote.params["objectKind"] = "remote"
    remote.params["description"] = "A programmable radio remote."
    server.item_service.add_item(remote)

    sent_payloads: list[object] = []
    broadcast_items: list[str] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(getattr(item, "id", ""))

    async def fake_resolve(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_remote_control",
                "itemId": remote.id,
                "action": "station_previous",
            }
        ),
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert "Remote tuned 2 connected radios to Three." == result.message
    assert primary.params["stationIndex"] == 2
    assert kitchen.params["stationIndex"] == 2
    assert primary.params["stationSwitchSound"] == ""
    assert primary.params["playStartedAt"] > 0
    assert kitchen.params["playStartedAt"] == primary.params["playStartedAt"]
    assert set(broadcast_items) == {"living-radio", "kitchen-radio"}


@pytest.mark.asyncio
async def test_carried_radio_remote_preserves_individual_radio_power(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    presets = [
        {"title": "One", "streamUrl": "https://example.com/one.mp3"},
        {"title": "Two", "streamUrl": "https://example.com/two.mp3"},
    ]

    primary = server.item_service.default_item(client, "radio_station")
    primary.id = "living-radio"
    primary.title = "Living room radio"
    primary.locationId = client.location_id
    primary.x = 5
    primary.y = 6
    primary.params["linkedMediaGroup"] = "test-house-radios"
    primary.params["stationPresets"] = presets
    primary.params["stationIndex"] = 0
    primary.params["enabled"] = True
    server.item_service.add_item(primary)

    bedroom = server.item_service.default_item(client, "radio_station")
    bedroom.id = "bedroom-radio"
    bedroom.title = "Bedroom radio"
    bedroom.locationId = "raywonder_house_bedroom"
    bedroom.params["linkedMediaGroup"] = "test-house-radios"
    bedroom.params["stationPresets"] = presets
    bedroom.params["stationIndex"] = 0
    bedroom.params["enabled"] = False
    server.item_service.add_item(bedroom)

    remote = server.item_service.default_item(client, "house_object")
    remote.id = "remote-1"
    remote.title = "Universal radio remote"
    remote.locationId = client.location_id
    remote.carrierId = client.id
    remote.params["objectKind"] = "remote"
    remote.params["description"] = "A programmable radio remote."
    server.item_service.add_item(remote)

    sent_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        return None

    async def fake_resolve(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_remote_control",
                "itemId": remote.id,
                "action": "station_next",
            }
        ),
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert primary.params["stationIndex"] == 1
    assert primary.params["enabled"] is True
    assert bedroom.params["stationIndex"] == 1
    assert bedroom.params["enabled"] is False


@pytest.mark.asyncio
async def test_carried_radio_remote_can_unlink_from_synced_station_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    presets = [
        {"title": "One", "streamUrl": "https://example.com/one.mp3"},
        {"title": "Two", "streamUrl": "https://example.com/two.mp3"},
    ]

    primary = server.item_service.default_item(client, "radio_station")
    primary.id = "living-radio"
    primary.title = "Living room radio"
    primary.locationId = client.location_id
    primary.x = 5
    primary.y = 6
    primary.params["linkedMediaGroup"] = "test-house-radios"
    primary.params["stationPresets"] = presets
    primary.params["stationIndex"] = 0
    server.item_service.add_item(primary)

    kitchen = server.item_service.default_item(client, "radio_station")
    kitchen.id = "kitchen-radio"
    kitchen.title = "Kitchen radio"
    kitchen.locationId = "raywonder_house_kitchen"
    kitchen.params["linkedMediaGroup"] = "test-house-radios"
    kitchen.params["stationPresets"] = presets
    kitchen.params["stationIndex"] = 0
    server.item_service.add_item(kitchen)

    remote = server.item_service.default_item(client, "house_object")
    remote.id = "remote-1"
    remote.title = "Universal radio remote"
    remote.locationId = client.location_id
    remote.carrierId = client.id
    remote.params["objectKind"] = "remote"
    remote.params["description"] = "A programmable radio remote."
    remote.params["remoteControlLinkedRadios"] = False
    server.item_service.add_item(remote)

    sent_payloads: list[object] = []
    broadcast_items: list[str] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(getattr(item, "id", ""))

    async def fake_resolve(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_remote_control",
                "itemId": remote.id,
                "action": "station_next",
            }
        ),
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert result.message == "Remote tuned 1 connected radio to Two."
    assert primary.params["stationIndex"] == 1
    assert kitchen.params["stationIndex"] == 0
    assert broadcast_items == ["living-radio"]


@pytest.mark.asyncio
async def test_radio_remote_sync_all_uses_linked_playing_station_when_nearest_speaker_has_no_presets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    presets = [
        {"title": "One", "streamUrl": "https://example.com/one.mp3"},
        {"title": "Two", "streamUrl": "https://example.com/two.mp3"},
    ]

    speaker = server.item_service.default_item(client, "radio_station")
    speaker.id = "living-speaker"
    speaker.title = "Living room speaker"
    speaker.locationId = client.location_id
    speaker.x = 5
    speaker.y = 6
    speaker.params["linkedMediaGroup"] = "test-house-radios"
    speaker.params["speakerRole"] = "high"
    speaker.params["stationPresets"] = []
    speaker.params["streamUrl"] = "https://example.com/old.mp3"
    speaker.params["stationName"] = "Old"
    server.item_service.add_item(speaker)

    source = server.item_service.default_item(client, "radio_station")
    source.id = "kitchen-source-radio"
    source.title = "Kitchen source radio"
    source.locationId = "raywonder_house_kitchen"
    source.params["linkedMediaGroup"] = "test-house-radios"
    source.params["speakerRole"] = "primary"
    source.params["stationPresets"] = presets
    source.params["stationIndex"] = 1
    source.params["streamUrl"] = "https://example.com/two.mp3"
    source.params["stationName"] = "Two"
    source.params["enabled"] = True
    server.item_service.add_item(source)

    remote = server.item_service.default_item(client, "house_object")
    remote.id = "remote-1"
    remote.title = "Universal radio remote"
    remote.locationId = client.location_id
    remote.carrierId = client.id
    remote.params["objectKind"] = "remote"
    remote.params["description"] = "A programmable radio remote."
    server.item_service.add_item(remote)

    sent_payloads: list[object] = []
    broadcast_items: list[str] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(getattr(item, "id", ""))

    async def fake_resolve(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_resolve_radio_playback_before_broadcast", fake_resolve)

    await server._handle_message(
        client,
        json.dumps({"type": "item_secondary_use", "itemId": remote.id}),
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert result.message == "Synced 2 house radio speakers to Two."
    assert speaker.params["streamUrl"] == "https://example.com/two.mp3"
    assert speaker.params["stationName"] == "Two"
    assert source.params["stationIndex"] == 1
    assert set(broadcast_items) == {"living-speaker", "kitchen-source-radio"}


@pytest.mark.asyncio
async def test_carried_radio_remote_volume_down_syncs_connected_radios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    primary = server.item_service.default_item(client, "radio_station")
    primary.id = "living-radio"
    primary.title = "Living room radio"
    primary.locationId = client.location_id
    primary.x = 5
    primary.y = 6
    primary.params["linkedMediaGroup"] = "test-house-radios"
    primary.params["mediaVolume"] = 20
    server.item_service.add_item(primary)

    kitchen = server.item_service.default_item(client, "radio_station")
    kitchen.id = "kitchen-radio"
    kitchen.title = "Kitchen radio"
    kitchen.locationId = "raywonder_house_kitchen"
    kitchen.params["linkedMediaGroup"] = "test-house-radios"
    kitchen.params["mediaVolume"] = 70
    server.item_service.add_item(kitchen)

    remote = server.item_service.default_item(client, "house_object")
    remote.id = "remote-1"
    remote.title = "Universal radio remote"
    remote.locationId = client.location_id
    remote.carrierId = client.id
    remote.params["objectKind"] = "remote"
    remote.params["description"] = "A programmable radio remote."
    server.item_service.add_item(remote)

    sent_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_remote_control",
                "itemId": remote.id,
                "action": "volume_down",
            }
        ),
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert result.message == "Remote adjusted 2 connected radios by -5, range 15 to 65."
    assert primary.params["mediaVolume"] == 15
    assert kitchen.params["mediaVolume"] == 65


@pytest.mark.asyncio
async def test_carried_radio_remote_volume_can_boost_to_1000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    primary = server.item_service.default_item(client, "radio_station")
    primary.id = "living-radio"
    primary.title = "Living room radio"
    primary.locationId = client.location_id
    primary.x = 5
    primary.y = 6
    primary.params["linkedMediaGroup"] = "test-house-radios"
    primary.params["mediaVolume"] = 998
    server.item_service.add_item(primary)

    remote = server.item_service.default_item(client, "house_object")
    remote.id = "remote-1"
    remote.title = "Universal radio remote"
    remote.locationId = client.location_id
    remote.carrierId = client.id
    remote.params["objectKind"] = "remote"
    remote.params["description"] = "A programmable radio remote."
    server.item_service.add_item(remote)

    sent_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_remote_control",
                "itemId": remote.id,
                "action": "volume_up",
            }
        ),
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert result.message == "Remote adjusted 1 connected radio to volume 1000."
    assert primary.params["mediaVolume"] == 1000


@pytest.mark.asyncio
async def test_radio_remote_control_requires_remote_in_hand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="tester",
            location_id="raywonder_house_living_room",
            x=5,
            y=5,
        ),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    remote = server.item_service.default_item(client, "house_object")
    remote.id = "remote-1"
    remote.title = "Universal radio remote"
    remote.locationId = client.location_id
    remote.x = client.x
    remote.y = client.y
    remote.params["objectKind"] = "remote"
    remote.params["description"] = "A programmable radio remote."
    server.item_service.add_item(remote)

    sent_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_remote_control",
                "itemId": remote.id,
                "action": "station_next",
            }
        ),
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is False
    assert result.message == "The radio remote needs to be in your hand."


@pytest.mark.asyncio
async def test_pickup_allows_limited_multi_item_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=5),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    items = []
    for index in range(5):
        item = server.item_service.default_item(client, "house_object")
        item.id = f"carry-{index}"
        item.title = f"Carry {index}"
        item.x = client.x
        item.y = client.y
        item.params["objectKind"] = "book"
        server.item_service.add_item(item)
        items.append(item)

    sent_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        return None

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    for item in items[:4]:
        await server._handle_message(
            client, json.dumps({"type": "item_pickup", "itemId": item.id})
        )
        assert _last_packet_of_type(sent_payloads, ItemActionResultPacket).ok is True

    await server._handle_message(
        client, json.dumps({"type": "item_pickup", "itemId": items[4].id})
    )

    result = _last_packet_of_type(sent_payloads, ItemActionResultPacket)
    assert result.ok is False
    assert result.message == "You can carry up to 4 items at once."
    assert len(server.item_service.carried_items_for_client(client.id)) == 4


@pytest.mark.asyncio
async def test_carried_items_return_to_surface_when_leaving_house_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
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
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client

    table = server.item_service.default_item(client, "furniture")
    table.id = "living-table"
    table.title = "Living room table"
    table.x = client.x
    table.y = client.y
    table.params["furnitureKind"] = "table"
    table.params["supportsObjects"] = True
    table.params["surfaceSlots"] = 2
    server.item_service.add_item(table)
    for item in server.items.values():
        if item.type == "furniture" and item.id != table.id:
            item.x = 0
            item.y = 0

    remote = server.item_service.default_item(client, "house_object")
    remote.id = "remote-1"
    remote.title = "Universal radio remote"
    remote.carrierId = client.id
    remote.params["objectKind"] = "remote"
    remote.params["description"] = "A programmable radio remote."
    server.item_service.add_item(remote)

    sent_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        sent_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return None

    async def fake_broadcast_item(item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client, json.dumps({"type": "change_location", "locationId": "city"})
    )

    assert client.location_id == "city"
    assert remote.carrierId is None
    assert remote.locationId == "raywonder_house_living_room"
    assert remote.x == 19
    assert remote.y == 21
    assert remote.params["placement"] == "table"
    assert remote.params["surfaceId"] == table.id
    assert _last_packet_of_type(sent_payloads, LocationChangedPacket).locationId == "city"


@pytest.mark.asyncio
async def test_item_secondary_use_missing_handler_returns_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=5),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    dice = server.item_service.default_item(client, "dice")
    dice.x = 5
    dice.y = 5
    server.item_service.add_item(dice)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "item_secondary_use", "itemId": dice.id})
    )

    results = _packets_of_type(send_payloads, ItemActionResultPacket)
    assert results
    assert results[-1].ok is False
    assert results[-1].action == "secondary_use"
    assert "No secondary action" in results[-1].message


@pytest.mark.asyncio
async def test_game_service_link_use_broadcasts_same_square_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=5),
        permissions={"item.use"},
    )
    server.clients[ws] = client

    game = server.item_service.default_item(client, "service_link")
    game.title = "Moonstep Runner"
    game.x = 5
    game.y = 5
    game.params["serviceKind"] = "game"
    game.params["url"] = "https://example.test/moonstep/"
    game.params["targetLocation"] = ""
    server.item_service.add_item(game)

    send_payloads: list[object] = []
    broadcast_payloads: list[tuple[str, object, ServerConnection | None]] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append((location_id, packet, exclude))

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        client, json.dumps({"type": "item_use", "itemId": game.id})
    )

    result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert result.ok is True
    launch_packets = [
        (location_id, packet, exclude)
        for location_id, packet, exclude in broadcast_payloads
        if isinstance(packet, ItemGameLaunchPacket)
    ]
    assert len(launch_packets) == 1
    location_id, launch, exclude = launch_packets[0]
    assert location_id == game.locationId
    assert exclude is ws
    assert launch.itemId == game.id
    assert launch.title == "Moonstep Runner"
    assert launch.url == "https://example.test/moonstep/"
    assert launch.actorId == "u1"
    assert launch.x == 5
    assert launch.y == 5


def test_random_portal_resolves_destination_from_public_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    client = _activate_client(
        ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester", x=5, y=5),
        permissions={"item.use"},
    )
    portal = server.item_service.default_item(client, "service_link")
    portal.params.update(
        {
            "serviceKind": "portal",
            "targetLocation": "",
            "portalDestinationMode": "random",
            "portalLocationPool": "town,arcade,offices",
            "doorState": "unlocked",
            "portalState": "open",
            "enabled": True,
        }
    )
    chosen: list[list[str]] = []

    def fake_choice(pool: list[str]) -> str:
        chosen.append(pool)
        return "arcade"

    monkeypatch.setattr("app.server.SYSTEM_RANDOM", SimpleNamespace(choice=fake_choice))

    assert server._resolve_service_link_target_location(portal, "city") == "arcade"
    assert chosen == [["town", "arcade", "offices"]]


def test_static_portal_uses_configured_target_location() -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    client = _activate_client(
        ClientConnection(websocket=_fake_ws(), id="u1", nickname="tester", x=5, y=5),
        permissions={"item.use"},
    )
    portal = server.item_service.default_item(client, "service_link")
    portal.params.update(
        {
            "serviceKind": "portal",
            "targetLocation": "Town",
            "portalDestinationMode": "static",
            "doorState": "unlocked",
            "portalState": "open",
            "enabled": True,
        }
    )

    assert server._resolve_service_link_target_location(portal, "city") == "town"


def test_clock_alarm_announcement_sequence_shape() -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    params = {"timeZone": "America/Detroit", "use24Hour": False}

    alarm_sounds = server._build_clock_announcement_sounds(
        params, top_of_hour=False, alarm=True
    )
    assert alarm_sounds
    assert alarm_sounds[0] == "/sounds/clock/archive/bell-alert-gentle.ogg"
    assert alarm_sounds[1] == "/sounds/clock/el640/announcement.ogg"
    assert alarm_sounds[-1] == "/sounds/clock/el640/alarm.ogg"

    top_of_hour_sounds = server._build_clock_announcement_sounds(
        params, top_of_hour=True, alarm=False
    )
    assert top_of_hour_sounds
    assert top_of_hour_sounds[0] == "/sounds/clock/archive/bell-clear-single.ogg"
    assert top_of_hour_sounds[1] == "/sounds/clock/el640/hour1.ogg"
    assert top_of_hour_sounds[-1] == "/sounds/clock/el640/hour2.ogg"

    manual_sounds = server._build_clock_announcement_sounds(
        params, top_of_hour=False, alarm=False
    )
    assert manual_sounds
    assert manual_sounds[0] == "/sounds/clock/archive/chime-hint-soft.ogg"
    assert manual_sounds[1] == "/sounds/clock/el640/its.ogg"


def test_clock_auto_announce_interval_marker() -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    params = {"announceIntervalMinutes": 15}

    assert (
        server._clock_auto_announce_marker(datetime(2026, 7, 14, 10, 30, 1), params)
        == "2026-07-14-10-30"
    )
    assert (
        server._clock_auto_announce_marker(datetime(2026, 7, 14, 10, 31, 1), params)
        is None
    )
    assert (
        server._clock_auto_announce_marker(
            datetime(2026, 7, 14, 10, 30, 2), {"announceIntervalMinutes": 1}
        )
        is None
    )
    assert (
        server._clock_auto_announce_marker(
            datetime(2026, 7, 14, 10, 0, 0), {"announceIntervalMinutes": 60}
        )
        == "2026-07-14-10-00"
    )


@pytest.mark.asyncio
async def test_auth_login_uses_hash_offload(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    username = f"alpha_{uuid.uuid4().hex[:8]}"
    server.auth_service.register(username, "password99")
    ws = _fake_ws()
    client = ClientConnection(websocket=ws, id="u1", nickname="tester")

    send_payloads: list[object] = []
    offload_calls: list[str] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return None

    async def fake_run_auth_hash_task(func, /, *args, **kwargs):
        offload_calls.append(getattr(func, "__name__", "unknown"))
        return func(*args, **kwargs)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server, "_run_auth_hash_task", fake_run_auth_hash_task)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "auth_login", "username": username, "password": "password99"}
        ),
    )

    assert "login" in offload_calls
    auth_results = _packets_of_type(send_payloads, AuthResultPacket)
    assert auth_results
    assert auth_results[-1].ok is True


@pytest.mark.asyncio
async def test_auth_rate_limit_blocks_before_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = ClientConnection(websocket=ws, id="u1", nickname="tester")

    send_payloads: list[object] = []
    called_login = False

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    def fake_login(username: str, password: str):  # pragma: no cover - should never run
        nonlocal called_login
        called_login = True
        raise RuntimeError("unexpected login call")

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_sleep_auth_failure_jitter", lambda: asyncio.sleep(0))
    monkeypatch.setattr(server.auth_service, "login", fake_login)
    monkeypatch.setattr(server, "_is_auth_rate_limited", lambda _client, _packet: True)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "auth_login", "username": "alpha", "password": "wrongpass"}
        ),
    )

    assert called_login is False
    assert send_payloads
    auth_result = _last_packet_of_type(send_payloads, AuthResultPacket)
    assert auth_result.ok is False
    assert "too many" in auth_result.message.lower()


@pytest.mark.asyncio
async def test_auth_login_failure_message_is_generic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = ClientConnection(websocket=ws, id="u1", nickname="tester")
    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_sleep_auth_failure_jitter", lambda: asyncio.sleep(0))

    def fake_login(_username: str, _password: str):
        raise AuthError("Account is disabled.")

    monkeypatch.setattr(server.auth_service, "login", fake_login)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "auth_login", "username": "alpha", "password": "wrongpass"}
        ),
    )

    auth_results = _packets_of_type(send_payloads, AuthResultPacket)
    assert auth_results
    assert auth_results[-1].ok is False
    assert auth_results[-1].message == AUTH_LOGIN_FAILURE_MESSAGE


@pytest.mark.asyncio
async def test_auth_login_defers_activation_until_welcome_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    username = f"ready_{uuid.uuid4().hex[:8]}"
    server.auth_service.register(username, "password99")
    ws = _fake_ws()
    client = ClientConnection(websocket=ws, id="u1", nickname="tester")

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "auth_login", "username": username, "password": "password99"}
        ),
    )

    assert client.authenticated is True
    assert client.world_ready is False
    assert ws not in server.clients
    assert any(getattr(packet, "type", "") == "welcome" for packet in send_payloads)
    assert not any(
        "has logged in" in getattr(packet, "message", "")
        for packet in broadcast_payloads
    )

    await server._handle_message(client, json.dumps({"type": "welcome_ready"}))

    assert client.world_ready is True
    assert server.clients.get(ws) is client
    assert any(
        "has logged in" in getattr(packet, "message", "")
        for packet in broadcast_payloads
    )


@pytest.mark.asyncio
async def test_ping_works_before_welcome_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    username = f"ping_{uuid.uuid4().hex[:8]}"
    server.auth_service.register(username, "password99")
    ws = _fake_ws()
    client = ClientConnection(websocket=ws, id="u1", nickname="tester")

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "auth_login", "username": username, "password": "password99"}
        ),
    )
    assert client.world_ready is False

    await server._handle_message(
        client, json.dumps({"type": "ping", "clientSentAt": -1})
    )

    pong_packets = _packets_of_type(send_payloads, PongPacket)
    assert pong_packets
    assert pong_packets[-1].clientSentAt == -1


@pytest.mark.asyncio
async def test_auth_resume_failure_message_is_generic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = ClientConnection(websocket=ws, id="u1", nickname="tester")
    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_sleep_auth_failure_jitter", lambda: asyncio.sleep(0))

    def fake_resume(_token: str):
        raise AuthError("Session has expired.")

    monkeypatch.setattr(server.auth_service, "resume", fake_resume)

    await server._handle_message(
        client, json.dumps({"type": "auth_resume", "sessionToken": "expired-token"})
    )

    auth_results = _packets_of_type(send_payloads, AuthResultPacket)
    assert auth_results
    assert auth_results[-1].ok is False
    assert auth_results[-1].message == AUTH_RESUME_FAILURE_MESSAGE


@pytest.mark.asyncio
async def test_item_drop_rejects_out_of_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "dice")
    item.carrierId = client.id
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "item_drop", "itemId": item.id, "x": 999, "y": 999})
    )

    assert item.carrierId == client.id
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "out of bounds" in item_result.message.lower()


@pytest.mark.asyncio
async def test_house_object_pickup_and_floor_drop_clear_surface_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    mug = server.item_service.default_item(client, "house_object")
    mug.title = "Coffee mug"
    mug.params["placement"] = "table"
    mug.params["surfaceId"] = "table-1"
    mug.params["surfaceTitle"] = "Kitchen table"
    server.item_service.add_item(mug)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(_item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client, json.dumps({"type": "item_pickup", "itemId": mug.id})
    )

    assert mug.carrierId == client.id
    assert mug.params["placement"] == "carried"
    assert mug.params["surfaceId"] == ""
    assert mug.params["surfaceTitle"] == ""

    await server._handle_message(
        client, json.dumps({"type": "item_drop", "itemId": mug.id, "x": 8, "y": 9})
    )

    assert mug.carrierId is None
    assert (mug.x, mug.y) == (8, 9)
    assert mug.params["placement"] == "floor"
    assert mug.params["surfaceId"] == ""
    assert mug.params["surfaceTitle"] == ""
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "Dropped" in item_result.message


@pytest.mark.asyncio
async def test_house_object_place_on_furniture_respects_surface_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    table = server.item_service.default_item(client, "furniture")
    table.id = "table-1"
    table.title = "Kitchen table"
    table.params["surfaceSlots"] = 1
    server.item_service.add_item(table)

    first = server.item_service.default_item(client, "house_object")
    first.id = "mug-1"
    first.title = "First mug"
    first.carrierId = client.id
    first.params["placement"] = "carried"
    server.item_service.add_item(first)

    second = server.item_service.default_item(client, "house_object")
    second.id = "mug-2"
    second.title = "Second mug"
    second.carrierId = client.id
    second.params["placement"] = "carried"
    server.item_service.add_item(second)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(_item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_interact",
                "itemId": first.id,
                "targetItemId": table.id,
                "action": "place_on",
            }
        ),
    )

    assert first.carrierId is None
    assert first.params["placement"] == "table"
    assert first.params["surfaceId"] == table.id
    assert first.params["surfaceTitle"] == table.title
    first_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert first_result.ok is True

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_interact",
                "itemId": second.id,
                "targetItemId": table.id,
                "action": "place_on",
            }
        ),
    )

    assert second.carrierId == client.id
    assert second.params["placement"] == "carried"
    second_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert second_result.ok is False
    assert "no open surface space" in second_result.message


@pytest.mark.asyncio
async def test_surface_item_reorder_moves_left_right_without_leaving_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    shelf = server.item_service.default_item(client, "furniture")
    shelf.id = "shelf-1"
    shelf.title = "Living room shelf"
    shelf.params["furnitureKind"] = "shelf"
    shelf.params["surfaceSlots"] = 4
    server.item_service.add_item(shelf)

    mug = server.item_service.default_item(client, "house_object")
    mug.id = "mug-1"
    mug.title = "Mug"
    mug.params["placement"] = "shelf"
    mug.params["surfaceId"] = shelf.id
    mug.params["surfaceTitle"] = shelf.title
    mug.params["surfaceOrder"] = 0
    server.item_service.add_item(mug)

    radio = server.item_service.default_item(client, "radio_station")
    radio.id = "radio-1"
    radio.title = "Radio"
    radio.params["surfaceId"] = shelf.id
    radio.params["surfaceTitle"] = shelf.title
    radio.params["surfaceOrder"] = 1
    server.item_service.add_item(radio)

    send_payloads: list[object] = []
    broadcast_items: list[WorldItem] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: WorldItem) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_interact", "itemId": mug.id, "action": "move_surface_left"}
        ),
    )

    edge_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert edge_result.ok is True
    assert "left edge" in edge_result.message
    assert mug.params["surfaceId"] == shelf.id
    assert mug.params["surfaceOrder"] == 0
    assert radio.params["surfaceOrder"] == 1
    assert broadcast_items == []

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_interact", "itemId": mug.id, "action": "move_surface_right"}
        ),
    )

    move_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert move_result.ok is True
    assert "move Mug right" in move_result.message
    assert mug.params["surfaceId"] == shelf.id
    assert mug.params["surfaceTitle"] == shelf.title
    assert radio.params["surfaceId"] == shelf.id
    assert mug.params["surfaceOrder"] == 1
    assert radio.params["surfaceOrder"] == 0
    assert {item.id for item in broadcast_items} == {mug.id, radio.id}


@pytest.mark.asyncio
async def test_furniture_title_update_refreshes_surface_title_dependents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.edit.any"},
    )
    server.clients[ws] = client
    table = server.item_service.default_item(client, "furniture")
    table.id = "table-1"
    table.title = "Kitchen table"
    server.item_service.add_item(table)

    mug = server.item_service.default_item(client, "house_object")
    mug.id = "mug-1"
    mug.title = "Coffee mug"
    mug.params["placement"] = "table"
    mug.params["surfaceId"] = table.id
    mug.params["surfaceTitle"] = table.title
    server.item_service.add_item(mug)

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": table.id,
                "title": "Dining table",
            }
        ),
    )

    assert table.title == "Dining table"
    assert mug.params["surfaceTitle"] == "Dining table"
    assert [getattr(item, "id", "") for item in broadcast_items] == [
        table.id,
        mug.id,
    ]
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert item_result.message == "Updated Dining table."


@pytest.mark.asyncio
async def test_furniture_kind_update_renames_only_generic_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.edit.any"},
    )
    server.clients[ws] = client

    generic = server.item_service.default_item(client, "furniture")
    generic.id = "furniture-1"
    generic.title = "table"
    generic.params["furnitureKind"] = "table"
    server.item_service.add_item(generic)

    custom = server.item_service.default_item(client, "furniture")
    custom.id = "furniture-2"
    custom.title = "Coffee table"
    custom.params["furnitureKind"] = "table"
    server.item_service.add_item(custom)

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": generic.id,
                "params": {"furnitureKind": "chair"},
            }
        ),
    )
    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": custom.id,
                "params": {"furnitureKind": "chair"},
            }
        ),
    )

    assert generic.title == "chair"
    assert generic.params["furnitureKind"] == "chair"
    assert custom.title == "Coffee table"
    assert custom.params["furnitureKind"] == "chair"
    assert [getattr(item, "id", "") for item in broadcast_items] == [
        generic.id,
        custom.id,
    ]
    item_results = _packets_of_type(send_payloads, ItemActionResultPacket)
    assert item_results[-2].message == "Updated chair."
    assert item_results[-1].message == "Updated Coffee table."


@pytest.mark.asyncio
async def test_radio_can_be_placed_on_shelf_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    shelf = server.item_service.default_item(client, "furniture")
    shelf.id = "shelf-1"
    shelf.title = "Living room shelf"
    shelf.params["furnitureKind"] = "shelf"
    shelf.params["surfaceSlots"] = 4
    server.item_service.add_item(shelf)

    radio = server.item_service.default_item(client, "radio_station")
    radio.id = "radio-1"
    radio.title = "Portable radio"
    radio.carrierId = client.id
    server.item_service.add_item(radio)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(_item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_interact",
                "itemId": radio.id,
                "targetItemId": shelf.id,
                "action": "place_on",
            }
        ),
    )

    assert radio.carrierId is None
    assert (radio.x, radio.y) == (shelf.x, shelf.y)
    assert radio.params["surfaceId"] == shelf.id
    assert radio.params["surfaceTitle"] == shelf.title
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "Portable radio" in item_result.message
    assert "Living room shelf" in item_result.message


@pytest.mark.asyncio
async def test_shelf_can_hold_matched_multi_speaker_radio_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    shelf = server.item_service.default_item(client, "furniture")
    shelf.id = "shelf-1"
    shelf.title = "Speaker shelf"
    shelf.params["furnitureKind"] = "shelf"
    shelf.params["surfaceSlots"] = 4
    server.item_service.add_item(shelf)

    speakers = []
    for role in ("low", "mid", "high", "sub"):
        speaker = server.item_service.default_item(client, "radio_station")
        speaker.id = f"{role}-speaker"
        speaker.title = f"{role.title()} speaker"
        speaker.carrierId = client.id
        speaker.params["speakerRole"] = role
        speaker.params["linkedMediaGroup"] = "shelf-match"
        speaker.params["syncWithPrimary"] = role != "primary"
        speakers.append(speaker)
        server.item_service.add_item(speaker)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(_item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    for speaker in speakers:
        await server._handle_message(
            client,
            json.dumps(
                {
                    "type": "item_interact",
                    "itemId": speaker.id,
                    "targetItemId": shelf.id,
                    "action": "place_on",
                }
            ),
        )
        item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
        assert item_result.ok is True

    assert [speaker.params["speakerRole"] for speaker in speakers] == [
        "low",
        "mid",
        "high",
        "sub",
    ]
    assert all(speaker.carrierId is None for speaker in speakers)
    assert all((speaker.x, speaker.y) == (shelf.x, shelf.y) for speaker in speakers)
    assert all(speaker.params["surfaceId"] == shelf.id for speaker in speakers)
    assert all(speaker.params["surfaceTitle"] == shelf.title for speaker in speakers)


@pytest.mark.asyncio
async def test_drop_radio_onto_shelf_places_radio_on_shelf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    shelf = server.item_service.default_item(client, "furniture")
    shelf.id = "shelf-1"
    shelf.title = "Living room shelf"
    shelf.params["furnitureKind"] = "shelf"
    shelf.params["surfaceSlots"] = 4
    server.item_service.add_item(shelf)

    radio = server.item_service.default_item(client, "radio_station")
    radio.id = "radio-1"
    radio.title = "Portable radio"
    radio.carrierId = client.id
    server.item_service.add_item(radio)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(_item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps({"type": "item_drop", "itemId": radio.id, "x": shelf.x, "y": shelf.y}),
    )

    assert radio.carrierId is None
    assert (radio.x, radio.y) == (shelf.x, shelf.y)
    assert radio.params["surfaceId"] == shelf.id
    assert radio.params["surfaceTitle"] == shelf.title
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True


@pytest.mark.asyncio
async def test_drop_shelf_onto_loose_radio_places_radio_on_shelf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    shelf = server.item_service.default_item(client, "furniture")
    shelf.id = "shelf-1"
    shelf.title = "Living room shelf"
    shelf.params["furnitureKind"] = "shelf"
    shelf.params["surfaceSlots"] = 4
    shelf.carrierId = client.id
    server.item_service.add_item(shelf)

    radio = server.item_service.default_item(client, "radio_station")
    radio.id = "radio-1"
    radio.title = "Loose radio"
    radio.x = 8
    radio.y = 9
    server.item_service.add_item(radio)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(_item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps({"type": "item_drop", "itemId": shelf.id, "x": radio.x, "y": radio.y}),
    )

    assert shelf.carrierId is None
    assert (shelf.x, shelf.y) == (8, 9)
    assert radio.carrierId is None
    assert (radio.x, radio.y) == (8, 9)
    assert radio.params["surfaceId"] == shelf.id
    assert radio.params["surfaceTitle"] == shelf.title
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True


@pytest.mark.asyncio
async def test_surface_slots_count_house_objects_and_radios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.use"},
    )
    server.clients[ws] = client
    shelf = server.item_service.default_item(client, "furniture")
    shelf.id = "shelf-1"
    shelf.title = "Small shelf"
    shelf.params["furnitureKind"] = "shelf"
    shelf.params["surfaceSlots"] = 1
    server.item_service.add_item(shelf)

    mug = server.item_service.default_item(client, "house_object")
    mug.id = "mug-1"
    mug.title = "Shelf mug"
    mug.params["surfaceId"] = shelf.id
    mug.params["surfaceTitle"] = shelf.title
    server.item_service.add_item(mug)

    radio = server.item_service.default_item(client, "radio_station")
    radio.id = "radio-1"
    radio.title = "Portable radio"
    radio.carrierId = client.id
    server.item_service.add_item(radio)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(_item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_interact",
                "itemId": radio.id,
                "targetItemId": shelf.id,
                "action": "place_on",
            }
        ),
    )

    assert radio.carrierId == client.id
    assert radio.params["surfaceId"] == ""
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "no open surface space" in item_result.message


@pytest.mark.asyncio
async def test_radio_pickup_and_floor_drop_clear_surface_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    radio = server.item_service.default_item(client, "radio_station")
    radio.title = "Portable radio"
    radio.params["surfaceId"] = "shelf-1"
    radio.params["surfaceTitle"] = "Living room shelf"
    server.item_service.add_item(radio)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(_item: object) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client, json.dumps({"type": "item_pickup", "itemId": radio.id})
    )

    assert radio.carrierId == client.id
    assert radio.params["surfaceId"] == ""
    assert radio.params["surfaceTitle"] == ""

    await server._handle_message(
        client, json.dumps({"type": "item_drop", "itemId": radio.id, "x": 8, "y": 9})
    )

    assert radio.carrierId is None
    assert (radio.x, radio.y) == (8, 9)
    assert radio.params["surfaceId"] == ""
    assert radio.params["surfaceTitle"] == ""
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "Dropped" in item_result.message


@pytest.mark.asyncio
async def test_pickup_shelf_keeps_radio_on_shelf_until_radio_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    shelf = server.item_service.default_item(client, "furniture")
    shelf.id = "shelf-1"
    shelf.title = "Living room shelf"
    shelf.params["furnitureKind"] = "shelf"
    shelf.params["surfaceSlots"] = 4
    server.item_service.add_item(shelf)

    radio = server.item_service.default_item(client, "radio_station")
    radio.id = "radio-1"
    radio.title = "Shelf radio"
    radio.params["surfaceId"] = shelf.id
    radio.params["surfaceTitle"] = shelf.title
    radio.x = shelf.x
    radio.y = shelf.y
    server.item_service.add_item(radio)

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps({"type": "item_pickup", "itemId": shelf.id, "moveAttached": True}),
    )

    assert shelf.carrierId == client.id
    assert radio.carrierId == client.id
    assert radio.params["surfaceId"] == shelf.id
    assert radio.params["surfaceTitle"] == shelf.title
    assert {getattr(item, "id", "") for item in broadcast_items} == {
        shelf.id,
        radio.id,
    }

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_drop", "itemId": shelf.id, "x": 8, "y": 9, "moveAttached": True}
        ),
    )

    assert shelf.carrierId is None
    assert radio.carrierId is None
    assert (shelf.x, shelf.y) == (8, 9)
    assert (radio.x, radio.y) == (8, 9)
    assert radio.params["surfaceId"] == shelf.id
    assert radio.params["surfaceTitle"] == shelf.title
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "Dropped" in item_result.message


@pytest.mark.asyncio
async def test_community_house_repair_creates_full_interior_and_companions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=8, y=9),
        permissions={"item.create"},
    )
    client.location_id = "houses"
    server.clients[ws] = client
    fixed_now = 123_456
    monkeypatch.setattr(server.item_service, "now_ms", lambda: fixed_now)
    house = server.item_service.default_item(client, "house")
    house.title = "Demo house"
    house.params["houseName"] = "Demo House"
    house.params["ownerName"] = "Builder"
    server.item_service.add_item(house)

    notes = await server._repair_community_locations(broadcast=False)

    target_location = house.params["targetLocation"]
    assert target_location.startswith("community_house_demo_house_")
    assert target_location in server._community_locations
    assert "Demo House location" in notes

    interior_items = [
        item for item in server.items.values() if item.locationId == target_location
    ]
    by_title = {item.title: item for item in interior_items}
    assert by_title["Outside entrance"].type == "service_link"
    assert by_title["Outside entrance"].params["targetLocation"] == "houses"
    assert by_title["Balcony"].type == "room"
    assert by_title["Balcony"].params["targetLocation"] == (
        f"{target_location}_balcony"[:64].rstrip("_")
    )
    assert by_title["Front window"].type == "house_object"
    assert by_title["Front window"].params["objectKind"] == "window"
    assert by_title["Front window"].params["placement"] == "wall"
    assert by_title["Entry lamp"].params["objectKind"] == "lamp"
    assert by_title["House keys"].params["keyFor"] == "Demo House"


@pytest.mark.asyncio
async def test_item_pickup_default_moves_only_selected_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    house = server.item_service.default_item(client, "house")
    house.title = "Whole house"
    house.params["assemblyId"] = "house-1"
    house.params["itemSize"] = "large"
    porch = server.item_service.default_item(client, "room")
    porch.title = "Front porch"
    porch.params["assemblyId"] = "house-1"
    porch.x = 6
    porch.y = 6
    server.item_service.add_item(house)
    server.item_service.add_item(porch)

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client, json.dumps({"type": "item_pickup", "itemId": house.id})
    )

    assert house.carrierId == client.id
    assert porch.carrierId is None
    assert (house.x, house.y) == (5, 6)
    assert (porch.x, porch.y) == (6, 6)
    assert [getattr(item, "id", "") for item in broadcast_items] == [house.id]
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "linked part" not in item_result.message


@pytest.mark.asyncio
async def test_item_pickup_can_move_linked_assembly_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    house = server.item_service.default_item(client, "house")
    house.title = "Whole house"
    house.params["assemblyId"] = "house-1"
    house.params["itemSize"] = "large"
    porch = server.item_service.default_item(client, "room")
    porch.title = "Front porch"
    porch.params["assemblyId"] = "house-1"
    porch.x = 6
    porch.y = 6
    server.item_service.add_item(house)
    server.item_service.add_item(porch)

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps({"type": "item_pickup", "itemId": house.id, "moveAttached": True}),
    )

    assert house.carrierId == client.id
    assert porch.carrierId == client.id
    assert (house.x, house.y) == (5, 6)
    assert (porch.x, porch.y) == (6, 6)
    assert {getattr(item, "id", "") for item in broadcast_items} == {
        house.id,
        porch.id,
    }
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "linked part" in item_result.message


@pytest.mark.asyncio
async def test_item_drop_moves_linked_assembly_with_offsets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=10, y=10),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    radio = server.item_service.default_item(client, "radio_station")
    radio.title = "Radio body"
    radio.params["linkedMediaGroup"] = "station-rig"
    radio.carrierId = client.id
    radio.x = 10
    radio.y = 10
    speaker = server.item_service.default_item(client, "radio_station")
    speaker.title = "Left speaker"
    speaker.params["linkedMediaGroup"] = "station-rig"
    speaker.carrierId = client.id
    speaker.x = 9
    speaker.y = 10
    server.item_service.add_item(radio)
    server.item_service.add_item(speaker)

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_drop", "itemId": radio.id, "x": 20, "y": 20, "moveAttached": True}
        ),
    )

    assert radio.carrierId is None
    assert speaker.carrierId is None
    assert (radio.x, radio.y) == (20, 20)
    assert (speaker.x, speaker.y) == (19, 20)
    assert {getattr(item, "id", "") for item in broadcast_items} == {
        radio.id,
        speaker.id,
    }
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "linked part" in item_result.message


@pytest.mark.asyncio
async def test_dropped_linked_speaker_reconnects_to_currently_playing_radio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=10, y=10),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client

    primary = server.item_service.default_item(client, "radio_station")
    primary.id = "primary-radio"
    primary.title = "Primary radio"
    primary.params["linkedMediaGroup"] = "living-room-rig"
    primary.params["speakerRole"] = "primary"
    primary.params["enabled"] = True
    primary.params["stationIndex"] = 2
    primary.params["streamUrl"] = "https://example.com/current.mp3"
    primary.params["playbackUrl"] = "https://media.example.com/current-playback.m3u8"
    primary.params["stationName"] = "Current Station"
    primary.params["nowPlaying"] = "Current Song"
    primary.params["stationSwitchSound"] = "sounds/radio/station-switch/current.mp3"
    primary.x = 4
    primary.y = 4
    server.item_service.add_item(primary)

    speaker = server.item_service.default_item(client, "radio_station")
    speaker.id = "left-speaker"
    speaker.title = "Left speaker"
    speaker.params["linkedMediaGroup"] = "living-room-rig"
    speaker.params["speakerRole"] = "high"
    speaker.params["syncWithPrimary"] = True
    speaker.params["streamUrl"] = ""
    speaker.params["playbackUrl"] = ""
    speaker.params["stationName"] = ""
    speaker.params["nowPlaying"] = ""
    speaker.carrierId = client.id
    server.item_service.add_item(speaker)

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client, json.dumps({"type": "item_drop", "itemId": speaker.id, "x": 8, "y": 9})
    )

    assert speaker.carrierId is None
    assert (speaker.x, speaker.y) == (8, 9)
    assert speaker.params["streamUrl"] == primary.params["streamUrl"]
    assert speaker.params["playbackUrl"] == primary.params["playbackUrl"]
    assert speaker.params["stationIndex"] == primary.params["stationIndex"]
    assert speaker.params["stationName"] == primary.params["stationName"]
    assert speaker.params["nowPlaying"] == primary.params["nowPlaying"]
    assert speaker.params["speakerRole"] == "high"
    assert speaker.params["syncWithPrimary"] is True
    assert [getattr(item, "id", "") for item in broadcast_items] == [speaker.id]
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "Dropped Left speaker" in item_result.message


@pytest.mark.asyncio
async def test_dropped_blank_speaker_auto_links_to_nearby_playing_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=10, y=10),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client

    primary = server.item_service.default_item(client, "radio_station")
    primary.id = "nearby-primary-radio"
    primary.title = "Nearby primary radio"
    primary.params["linkedMediaGroup"] = "nearby-rig"
    primary.params["speakerRole"] = "primary"
    primary.params["enabled"] = True
    primary.params["streamUrl"] = "https://example.com/current.mp3"
    primary.params["stationName"] = "Nearby Station"
    primary.x = 8
    primary.y = 8
    server.item_service.add_item(primary)

    speaker = server.item_service.default_item(client, "radio_station")
    speaker.id = "blank-high-speaker"
    speaker.title = "Blank high speaker"
    speaker.params["linkedMediaGroup"] = ""
    speaker.params["speakerRole"] = "high"
    speaker.params["syncWithPrimary"] = False
    speaker.params["streamUrl"] = ""
    speaker.carrierId = client.id
    server.item_service.add_item(speaker)

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client, json.dumps({"type": "item_drop", "itemId": speaker.id, "x": 9, "y": 9})
    )

    assert speaker.params["linkedMediaGroup"] == "nearby-rig"
    assert speaker.params["syncWithPrimary"] is True
    assert speaker.params["streamUrl"] == primary.params["streamUrl"]
    assert speaker.params["stationName"] == primary.params["stationName"]
    assert [getattr(item, "id", "") for item in broadcast_items] == [speaker.id]
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert "Dropped Blank high speaker" in item_result.message


@pytest.mark.asyncio
async def test_radio_component_update_auto_links_blank_group_to_nearby_playing_radio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=10, y=10),
        permissions={"item.edit.any"},
    )
    server.clients[ws] = client

    primary = server.item_service.default_item(client, "radio_station")
    primary.id = "active-radio"
    primary.title = "Active radio"
    primary.params["linkedMediaGroup"] = "active-rig"
    primary.params["speakerRole"] = "primary"
    primary.params["enabled"] = True
    primary.params["streamUrl"] = "https://example.com/live.mp3"
    primary.params["stationName"] = "Live Station"
    primary.x = 9
    primary.y = 10
    server.item_service.add_item(primary)

    speaker = server.item_service.default_item(client, "radio_station")
    speaker.id = "editable-speaker"
    speaker.title = "Editable speaker"
    speaker.params["linkedMediaGroup"] = ""
    speaker.params["speakerRole"] = "primary"
    speaker.params["syncWithPrimary"] = False
    speaker.params["streamUrl"] = ""
    speaker.x = 10
    speaker.y = 10
    server.item_service.add_item(speaker)

    send_payloads: list[object] = []
    broadcast_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(item: object) -> None:
        broadcast_items.append(item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        client,
        json.dumps(
            {
                "type": "item_update",
                "itemId": speaker.id,
                "params": {"speakerRole": "sub", "linkedMediaGroup": ""},
            }
        ),
    )

    assert speaker.params["speakerRole"] == "sub"
    assert speaker.params["linkedMediaGroup"] == "active-rig"
    assert speaker.params["syncWithPrimary"] is True
    assert speaker.params["streamUrl"] == primary.params["streamUrl"]
    assert speaker.params["stationName"] == primary.params["stationName"]
    assert [getattr(item, "id", "") for item in broadcast_items] == [speaker.id]
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is True
    assert item_result.message == "Updated Editable speaker."


@pytest.mark.asyncio
async def test_item_drop_rejects_linked_assembly_out_of_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=39, y=39),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    root = server.item_service.default_item(client, "house")
    root.params["assemblyId"] = "wide-house"
    root.carrierId = client.id
    root.x = 39
    root.y = 39
    linked = server.item_service.default_item(client, "room")
    linked.title = "Right room"
    linked.params["assemblyId"] = "wide-house"
    linked.carrierId = client.id
    linked.x = 40
    linked.y = 39
    server.item_service.add_item(root)
    server.item_service.add_item(linked)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client,
        json.dumps(
            {"type": "item_drop", "itemId": root.id, "x": 40, "y": 39, "moveAttached": True}
        ),
    )

    assert root.carrierId == client.id
    assert linked.carrierId == client.id
    assert (root.x, root.y) == (39, 39)
    assert (linked.x, linked.y) == (40, 39)
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "out of bounds" in item_result.message.lower()


@pytest.mark.asyncio
async def test_item_pickup_rejects_fixed_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="builder", x=5, y=6),
        permissions={"item.pickup_drop.any"},
    )
    server.clients[ws] = client
    billboard = server.item_service.default_item(client, "billboard")
    billboard.params["itemMobility"] = "fixture"
    server.item_service.add_item(billboard)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "item_pickup", "itemId": billboard.id})
    )

    assert billboard.carrierId is None
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "fixed in place" in item_result.message


@pytest.mark.asyncio
async def test_item_transfer_updates_item_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    owner_ws = _fake_ws()
    target_ws = _fake_ws()
    owner = ClientConnection(
        websocket=owner_ws,
        id="u1",
        nickname="owner",
        authenticated=True,
        user_id="1",
        username="owner_user",
        permissions={"item.transfer.own"},
        x=5,
        y=6,
    )
    _activate_client(owner)
    target = ClientConnection(
        websocket=target_ws,
        id="u2",
        nickname="target",
        authenticated=True,
        user_id="2",
        username="target_user",
        permissions=set(),
        x=10,
        y=10,
    )
    _activate_client(target)
    server.clients[owner_ws] = owner
    server.clients[target_ws] = target
    item = server.item_service.default_item(owner, "dice")
    item.x = owner.x
    item.y = owner.y
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    broadcasted_items: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(broadcast_item: object) -> None:
        broadcasted_items.append(broadcast_item)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        owner,
        json.dumps(
            {"type": "item_transfer", "itemId": item.id, "targetUserId": target.user_id}
        ),
    )

    assert item.createdBy == target.user_id
    assert item.createdByName == target.username
    assert broadcasted_items
    assert send_payloads
    result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert result.action == "transfer"
    assert "you transferred" in result.message.lower()
    assert broadcast_payloads
    chat_packet = _last_packet_of_type(broadcast_payloads, BroadcastChatMessagePacket)
    assert "owner transferred" in chat_packet.message.lower()


@pytest.mark.asyncio
async def test_item_transfer_allows_self_target_for_transfer_any(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    owner_ws = _fake_ws()
    actor_ws = _fake_ws()
    owner = ClientConnection(
        websocket=owner_ws,
        id="u1",
        nickname="owner",
        authenticated=True,
        user_id="1",
        username="owner_user",
        permissions=set(),
        x=5,
        y=6,
    )
    _activate_client(owner)
    actor = ClientConnection(
        websocket=actor_ws,
        id="u3",
        nickname="actor",
        authenticated=True,
        user_id="3",
        username="actor_user",
        permissions={"item.transfer.any"},
        x=5,
        y=6,
    )
    _activate_client(actor)
    server.clients[owner_ws] = owner
    server.clients[actor_ws] = actor
    item = server.item_service.default_item(owner, "dice")
    item.x = actor.x
    item.y = actor.y
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    broadcasted_items: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_item(broadcast_item: object) -> None:
        broadcasted_items.append(broadcast_item)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_item", fake_broadcast_item)

    await server._handle_message(
        actor,
        json.dumps(
            {"type": "item_transfer", "itemId": item.id, "targetUserId": actor.user_id}
        ),
    )

    assert item.createdBy == actor.user_id
    assert item.createdByName == actor.username
    assert broadcasted_items
    result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert result.action == "transfer"


@pytest.mark.asyncio
async def test_item_transfer_accepts_offline_target_user_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = SignalingServer(
        "127.0.0.1", 8765, None, None, auth_db_path=tmp_path / "auth.db", grid_size=41
    )
    owner_session = server.auth_service.register("owner_test", "password99")
    actor_session = server.auth_service.register("actor_test", "password99")
    offline_session = server.auth_service.register("offline_test", "password99")
    owner_ws = _fake_ws()
    actor_ws = _fake_ws()
    owner = ClientConnection(
        websocket=owner_ws,
        id="u1",
        nickname="owner",
        authenticated=True,
        user_id=owner_session.user.id,
        username=owner_session.user.username,
        permissions=set(),
        x=5,
        y=6,
    )
    _activate_client(owner)
    actor = ClientConnection(
        websocket=actor_ws,
        id="u3",
        nickname="actor",
        authenticated=True,
        user_id=actor_session.user.id,
        username=actor_session.user.username,
        permissions={"item.transfer.any"},
        x=5,
        y=6,
    )
    _activate_client(actor)
    server.clients[owner_ws] = owner
    server.clients[actor_ws] = actor
    item = server.item_service.default_item(owner, "dice")
    item.x = actor.x
    item.y = actor.y
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        actor,
        json.dumps(
            {
                "type": "item_transfer",
                "itemId": item.id,
                "targetUserId": offline_session.user.id,
            }
        ),
    )

    assert item.createdBy == offline_session.user.id
    assert item.createdByName == offline_session.user.username
    result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert result.ok is True
    assert result.action == "transfer"


@pytest.mark.asyncio
async def test_item_transfer_targets_lists_online_and_offline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = SignalingServer(
        "127.0.0.1", 8765, None, None, auth_db_path=tmp_path / "auth.db", grid_size=41
    )
    owner_session = server.auth_service.register("owner_menu", "password99")
    actor_session = server.auth_service.register("actor_menu", "password99")
    online_session = server.auth_service.register("online_menu", "password99")
    offline_session = server.auth_service.register("offline_menu", "password99")
    owner_ws = _fake_ws()
    actor_ws = _fake_ws()
    online_ws = _fake_ws()
    owner = ClientConnection(
        websocket=owner_ws,
        id="u1",
        nickname="owner",
        authenticated=True,
        user_id=owner_session.user.id,
        username=owner_session.user.username,
        permissions=set(),
        x=5,
        y=6,
    )
    _activate_client(owner)
    actor = ClientConnection(
        websocket=actor_ws,
        id="u3",
        nickname="actor",
        authenticated=True,
        user_id=actor_session.user.id,
        username=actor_session.user.username,
        permissions={"item.transfer.any"},
        x=5,
        y=6,
    )
    _activate_client(actor)
    online = ClientConnection(
        websocket=online_ws,
        id="u4",
        nickname="online",
        authenticated=True,
        user_id=online_session.user.id,
        username=online_session.user.username,
        permissions=set(),
        x=10,
        y=10,
    )
    _activate_client(online)
    server.clients[owner_ws] = owner
    server.clients[actor_ws] = actor
    server.clients[online_ws] = online
    item = server.item_service.default_item(owner, "dice")
    item.x = actor.x
    item.y = actor.y
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        actor, json.dumps({"type": "item_transfer_targets", "itemId": item.id})
    )

    assert send_payloads
    result = _last_packet_of_type(send_payloads, ItemTransferTargetsResultPacket)
    usernames = {entry.username for entry in result.targets}
    assert owner_session.user.username not in usernames
    assert online_session.user.username in usernames
    assert offline_session.user.username in usernames
    by_username = {entry.username: entry for entry in result.targets}
    assert by_username[online_session.user.username].online is True
    assert by_username[offline_session.user.username].online is False


@pytest.mark.asyncio
async def test_item_delete_sends_others_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    owner_ws = _fake_ws()
    watcher_ws = _fake_ws()
    owner = ClientConnection(
        websocket=owner_ws,
        id="u1",
        nickname="owner",
        authenticated=True,
        user_id="1",
        username="owner_user",
        permissions={"item.delete.own"},
        x=5,
        y=6,
    )
    _activate_client(owner)
    watcher = ClientConnection(
        websocket=watcher_ws,
        id="u2",
        nickname="watcher",
        authenticated=True,
        user_id="2",
        username="watcher_user",
        permissions=set(),
        x=5,
        y=6,
    )
    _activate_client(watcher)
    server.clients[owner_ws] = owner
    server.clients[watcher_ws] = watcher
    item = server.item_service.default_item(owner, "dice")
    item.x = owner.x
    item.y = owner.y
    server.item_service.add_item(item)

    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        owner, json.dumps({"type": "item_delete", "itemId": item.id})
    )

    result_packets = _packets_of_type(send_payloads, ItemActionResultPacket)
    assert result_packets
    assert result_packets[-1].ok is True
    assert "you deleted" in result_packets[-1].message.lower()
    chat_packets = _packets_of_type(broadcast_payloads, BroadcastChatMessagePacket)
    assert chat_packets
    assert "owner deleted" in getattr(chat_packets[-1], "message", "").lower()


@pytest.mark.asyncio
async def test_item_transfer_rejects_when_not_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    owner_ws = _fake_ws()
    target_ws = _fake_ws()
    owner = ClientConnection(
        websocket=owner_ws,
        id="u1",
        nickname="owner",
        authenticated=True,
        user_id="1",
        username="owner_user",
        permissions={"item.use"},
        x=5,
        y=6,
    )
    _activate_client(owner)
    target = ClientConnection(
        websocket=target_ws,
        id="u2",
        nickname="target",
        authenticated=True,
        user_id="2",
        username="target_user",
        permissions=set(),
        x=10,
        y=10,
    )
    _activate_client(target)
    server.clients[owner_ws] = owner
    server.clients[target_ws] = target
    item = server.item_service.default_item(owner, "dice")
    item.x = owner.x
    item.y = owner.y
    server.item_service.add_item(item)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        owner,
        json.dumps(
            {"type": "item_transfer", "itemId": item.id, "targetUserId": target.user_id}
        ),
    )

    assert item.createdBy == owner.user_id
    assert send_payloads
    result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert result.ok is False
    assert result.action == "transfer"
    assert "not authorized" in result.message.lower()


@pytest.mark.asyncio
async def test_admin_user_delete_requires_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = ClientConnection(
        websocket=ws,
        id="u1",
        nickname="Tester",
        authenticated=True,
        user_id="1",
        username="tester",
        permissions={"user.ban_unban"},
    )
    _activate_client(client)
    server.clients[ws] = client

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "admin_user_delete", "username": "alpha"})
    )

    assert send_payloads
    packet = _last_packet_of_type(send_payloads, AdminActionResultPacket)
    assert packet.ok is False
    assert packet.action == "user_delete"
    assert "not authorized" in packet.message.lower()


@pytest.mark.asyncio
async def test_admin_user_delete_calls_auth_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = ClientConnection(
        websocket=ws,
        id="u1",
        nickname="Tester",
        authenticated=True,
        user_id="1",
        username="tester",
        permissions={"account.delete.any"},
    )
    _activate_client(client)
    server.clients[ws] = client

    send_payloads: list[object] = []
    calls: list[tuple[str, str | None]] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(
        server.auth_service, "get_user_id_by_username", lambda _username: None
    )

    def fake_delete_user(username: str, *, actor_user_id: str | None = None) -> str:
        calls.append((username, actor_user_id))
        return username

    monkeypatch.setattr(server.auth_service, "delete_user", fake_delete_user)

    await server._handle_message(
        client, json.dumps({"type": "admin_user_delete", "username": "alpha"})
    )

    assert calls == [("alpha", "1")]
    assert send_payloads
    packet = _last_packet_of_type(send_payloads, AdminActionResultPacket)
    assert packet.ok is True
    assert packet.action == "user_delete"


@pytest.mark.asyncio
async def test_broadcast_fanout_is_concurrent(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws1 = _fake_ws()
    ws2 = _fake_ws()
    server.clients[ws1] = ClientConnection(websocket=ws1, id="u1")
    server.clients[ws2] = ClientConnection(websocket=ws2, id="u2")

    send_started_at: dict[ServerConnection, float] = {}

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_started_at[websocket] = monotonic()
        if websocket is ws1:
            await asyncio.sleep(0.05)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._broadcast({"type": "noop"})

    assert ws1 in send_started_at
    assert ws2 in send_started_at
    assert abs(send_started_at[ws1] - send_started_at[ws2]) < 0.02


@pytest.mark.asyncio
async def test_item_add_rejects_unknown_type(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=6),
        permissions={"item.create"},
    )
    server.clients[ws] = client

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "item_add", "itemType": "not_a_type"})
    )

    assert send_payloads
    item_result = _last_packet_of_type(send_payloads, ItemActionResultPacket)
    assert item_result.ok is False
    assert "unknown item type" in item_result.message.lower()


@pytest.mark.asyncio
async def test_update_position_enforces_cumulative_budget_per_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    server.movement_tick_ms = 100
    server.movement_max_steps_per_tick = 2
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=5)
    )
    server.clients[ws] = client

    fixed_now = 10_000
    monkeypatch.setattr(server.item_service, "now_ms", lambda: fixed_now)

    broadcast_payloads: list[object] = []

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    # First 1-step move in this tick: allowed.
    await server._handle_message(
        client, json.dumps({"type": "update_position", "x": 6, "y": 5})
    )
    # Second 1-step move in the same tick: allowed (budget now exhausted at 2).
    await server._handle_message(
        client, json.dumps({"type": "update_position", "x": 7, "y": 5})
    )
    # Third 1-step move in the same tick: must be rejected.
    await server._handle_message(
        client, json.dumps({"type": "update_position", "x": 8, "y": 5})
    )

    assert client.x == 7
    assert client.y == 5
    assert len(broadcast_payloads) == 2


@pytest.mark.asyncio
async def test_teleport_complete_broadcasts_spatial_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=12, y=13)
    )
    server.clients[ws] = client

    broadcast_payloads: list[object] = []

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        return None

    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)
    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "teleport_complete", "x": 12, "y": 13})
    )

    position_packets = _packets_of_type(broadcast_payloads, BroadcastPositionPacket)
    teleport_packets = _packets_of_type(
        broadcast_payloads, BroadcastTeleportCompletePacket
    )
    assert len(position_packets) == 1
    assert len(teleport_packets) == 1
    assert position_packets[0].id == "u1"
    assert position_packets[0].x == 12
    assert position_packets[0].y == 13
    assert teleport_packets[0].id == "u1"
    assert teleport_packets[0].x == 12
    assert teleport_packets[0].y == 13


@pytest.mark.asyncio
async def test_update_position_rate_reject_sends_self_correction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="tester", x=5, y=5)
    )
    server.clients[ws] = client
    server.movement_tick_ms = 100
    server.movement_max_steps_per_tick = 1

    fixed_now = 10_000
    monkeypatch.setattr(server.item_service, "now_ms", lambda: fixed_now)

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        return None

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast", fake_broadcast)

    # 2-tile move exceeds per-window budget and should be rejected with correction.
    await server._handle_message(
        client, json.dumps({"type": "update_position", "x": 7, "y": 5})
    )

    assert client.x == 5
    assert client.y == 5
    assert send_payloads
    correction = _last_packet_of_type(send_payloads, BroadcastPositionPacket)
    assert correction.id == "u1"
    assert correction.x == 5
    assert correction.y == 5


@pytest.mark.asyncio
async def test_hand_release_requires_other_user_holding_your_hand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    actor_ws = _fake_ws()
    target_ws = _fake_ws()
    actor = _activate_client(
        ClientConnection(websocket=actor_ws, id="u1", nickname="Actor", x=5, y=5)
    )
    target = _activate_client(
        ClientConnection(websocket=target_ws, id="u2", nickname="Target", x=5, y=6)
    )
    server.clients[actor_ws] = actor
    server.clients[target_ws] = target
    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        actor,
        json.dumps(
            {"type": "user_action", "actionId": "take_left_hand", "targetId": "u2"}
        ),
    )

    assert target.hand_held_by_id == actor.id
    target_position = _last_packet_of_type(broadcast_payloads, BroadcastPositionPacket)
    assert target_position.id == target.id
    assert target_position.handHeldById == actor.id

    await server._handle_message(
        actor,
        json.dumps(
            {"type": "user_action", "actionId": "release_hand", "targetId": "u2"}
        ),
    )

    failed_release = _last_packet_of_type(send_payloads, UserActionResultPacket)
    assert failed_release.ok is False
    assert "not holding your hand" in failed_release.message
    assert target.hand_held_by_id == actor.id

    await server._handle_message(
        target,
        json.dumps(
            {"type": "user_action", "actionId": "release_hand", "targetId": "u1"}
        ),
    )

    successful_release = _last_packet_of_type(send_payloads, UserActionResultPacket)
    assert successful_release.ok is True
    assert target.hand_held_by_id is None


@pytest.mark.asyncio
async def test_walkto_broadcasts_each_step_instead_of_jump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None, grid_size=41)
    walker_ws = _fake_ws()
    target_ws = _fake_ws()
    walker = _activate_client(
        ClientConnection(websocket=walker_ws, id="u1", nickname="Walker", x=1, y=1),
        permissions={"chat.send"},
    )
    target = _activate_client(
        ClientConnection(websocket=target_ws, id="u2", nickname="Target", x=5, y=4)
    )
    server.clients[walker_ws] = walker
    server.clients[target_ws] = target
    send_payloads: list[object] = []
    broadcast_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        walker, json.dumps({"type": "chat_message", "message": "/walkto Target"})
    )

    self_positions = _packets_of_type(send_payloads, BroadcastPositionPacket)
    broadcast_positions = _packets_of_type(broadcast_payloads, BroadcastPositionPacket)
    assert [(packet.x, packet.y) for packet in self_positions] == [
        (2, 2),
        (3, 3),
        (4, 3),
    ]
    assert [(packet.x, packet.y) for packet in broadcast_positions] == [
        (2, 2),
        (3, 3),
        (4, 3),
    ]
    assert (walker.x, walker.y) == (4, 3)


@pytest.mark.asyncio
async def test_chat_me_command_broadcasts_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="Tester"),
        permissions={"chat.send"},
    )
    server.clients[ws] = client

    broadcast_payloads: list[object] = []
    send_payloads: list[object] = []

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)
    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "chat_message", "message": "/Me waves hello"})
    )

    assert send_payloads == []
    assert len(broadcast_payloads) == 1
    packet = _last_packet_of_type(broadcast_payloads, BroadcastChatMessagePacket)
    assert packet.action is True
    assert packet.system is False
    assert packet.message == "Tester waves hello"


@pytest.mark.asyncio
async def test_chat_up_command_sends_sender_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="Tester"),
        permissions={"chat.send"},
    )
    server.clients[ws] = client

    broadcast_payloads: list[object] = []
    send_payloads: list[object] = []

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_format_uptime", lambda: "1h 2m 3s")

    await server._handle_message(
        client, json.dumps({"type": "chat_message", "message": "/UP"})
    )

    assert broadcast_payloads == []
    assert len(send_payloads) == 1
    packet = _last_packet_of_type(send_payloads, BroadcastChatMessagePacket)
    assert packet.system is True
    assert packet.message == "Server uptime: 1h 2m 3s"


@pytest.mark.asyncio
async def test_chat_command_requires_leading_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="Tester"),
        permissions={"chat.send"},
    )
    server.clients[ws] = client

    broadcast_payloads: list[object] = []

    async def fake_broadcast_location(
        location_id: str, packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_broadcast_location", fake_broadcast_location)

    await server._handle_message(
        client, json.dumps({"type": "chat_message", "message": " /up"})
    )

    assert len(broadcast_payloads) == 1
    packet = _last_packet_of_type(broadcast_payloads, BroadcastChatMessagePacket)
    assert packet.system is False
    assert packet.action is False
    assert packet.message == " /up"


@pytest.mark.asyncio
async def test_chat_version_command_is_sender_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(websocket=ws, id="u1", nickname="Tester"),
        permissions={"chat.send"},
    )
    server.clients[ws] = client
    server.server_version = "2026.02.27 R293"

    broadcast_payloads: list[object] = []
    send_payloads: list[object] = []

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "chat_message", "message": "/version"})
    )

    assert broadcast_payloads == []
    assert len(send_payloads) == 1
    packet = _last_packet_of_type(send_payloads, BroadcastChatMessagePacket)
    assert packet.system is True
    assert packet.message == "Server version: 2026.02.27 R293"


@pytest.mark.asyncio
async def test_chat_reboot_requires_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = ClientConnection(
        websocket=ws,
        id="u1",
        nickname="Tester",
        authenticated=True,
        user_id="1",
        permissions={"chat.send"},
    )
    _activate_client(client)
    server.clients[ws] = client

    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(
        server, "_schedule_reboot", lambda _requested_by, _message: True
    )

    await server._handle_message(
        client, json.dumps({"type": "chat_message", "message": "/reboot patching"})
    )

    assert send_payloads
    packet = _last_packet_of_type(send_payloads, BroadcastChatMessagePacket)
    assert packet.system is True
    assert "not authorized" in packet.message.lower()


@pytest.mark.asyncio
async def test_chat_reboot_schedules_and_broadcasts_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = ClientConnection(
        websocket=ws,
        id="u1",
        nickname="Tester",
        authenticated=True,
        user_id="1",
        username="tester",
        permissions={"chat.send", "server.allow_reboot"},
    )
    _activate_client(client)
    server.clients[ws] = client

    broadcast_payloads: list[object] = []

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(
        server,
        "_schedule_reboot",
        lambda requested_by, message: (
            requested_by == "tester" and message == "maintenance"
        ),
    )

    await server._handle_message(
        client, json.dumps({"type": "chat_message", "message": "/reboot maintenance"})
    )

    assert len(broadcast_payloads) == 1
    packet = _last_packet_of_type(broadcast_payloads, BroadcastChatMessagePacket)
    assert packet.system is True
    assert packet.message == "Server rebooting in 5 seconds. maintenance"


@pytest.mark.asyncio
async def test_chat_reboot_already_in_progress_sends_sender_only_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = ClientConnection(
        websocket=ws,
        id="u1",
        nickname="Tester",
        authenticated=True,
        user_id="1",
        username="tester",
        permissions={"chat.send", "server.allow_reboot"},
    )
    _activate_client(client)
    server.clients[ws] = client

    broadcast_payloads: list[object] = []
    send_payloads: list[object] = []

    async def fake_broadcast(
        packet: object, exclude: ServerConnection | None = None
    ) -> None:
        broadcast_payloads.append(packet)

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_broadcast", fake_broadcast)
    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(
        server, "_schedule_reboot", lambda _requested_by, _message: False
    )

    await server._handle_message(
        client, json.dumps({"type": "chat_message", "message": "/reboot maintenance"})
    )

    assert broadcast_payloads == []
    assert len(send_payloads) == 1
    packet = _last_packet_of_type(send_payloads, BroadcastChatMessagePacket)
    assert packet.system is True
    assert packet.message == "Server reboot already in progress."


@pytest.mark.asyncio
async def test_platform_overview_includes_link_author_verification_and_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="Admin",
            user_id="admin-id",
            username="admin",
            permissions={"server.manage_settings"},
        )
    )
    server.clients[ws] = client
    item = server.item_service.default_item(client, "service_link")
    item.title = "Moonstep Runner"
    item.params.update(
        {
            "serviceKind": "game",
            "url": "https://blind.software/private/moonstep/",
            "softwareAuthor": "Clawdia",
            "verificationStatus": "author_verified",
        }
    )
    server.item_service.add_item(item)
    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "admin_platform_overview", "scope": "platform"})
    )

    result = _last_packet_of_type(send_payloads, AdminPlatformOverviewResultPacket)
    summary = next(entry for entry in result.links if entry.itemId == item.id)
    assert result.scope == "platform"
    assert result.serviceLinkCount >= 1
    assert summary.author == "Clawdia"
    assert summary.verificationStatus == "author_verified"
    assert summary.ownerName == "admin"
    assert summary.ownedByCurrentUser is True


@pytest.mark.asyncio
async def test_owned_content_overview_lists_only_current_users_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    owner = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="Owner",
            user_id="owner-id",
            username="owner",
            permissions={"item.edit.own"},
        )
    )
    other = _activate_client(
        ClientConnection(
            websocket=_fake_ws(),
            id="u2",
            nickname="Other",
            user_id="other-id",
            username="other",
            permissions={"item.edit.own"},
        )
    )
    server.clients[ws] = owner
    mine = server.item_service.default_item(owner, "billboard")
    mine.title = "Owner showcase"
    theirs = server.item_service.default_item(other, "service_link")
    theirs.title = "Other app"
    server.item_service.add_item(mine)
    server.item_service.add_item(theirs)
    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        owner,
        json.dumps({"type": "admin_platform_overview", "scope": "owned_content"}),
    )

    result = _last_packet_of_type(send_payloads, AdminPlatformOverviewResultPacket)
    assert result.scope == "owned_content"
    assert result.ownedContentCount == 1
    assert [entry.title for entry in result.links] == ["Owner showcase"]
    assert result.links[0].kind == "billboard"
    assert result.links[0].ownedByCurrentUser is True


@pytest.mark.asyncio
async def test_user_notifications_list_and_mark_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="Reader",
            user_id="reader-id",
            username="reader",
            permissions={"chat.send"},
        )
    )
    server.clients[ws] = client
    server.notification_service.add(
        now_ms=server.item_service.now_ms(),
        kind="item.transfer",
        title="Moonstep transferred to you",
        message="Owner transferred Moonstep to you.",
        target_user_id=client.user_id,
        actor_user_id="owner-id",
    )
    server.notification_service.add(
        now_ms=server.item_service.now_ms() + 1,
        kind="direct_message",
        title="Direct message from Someone Else",
        message="This belongs to another user.",
        target_user_id="other-user-id",
    )
    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "admin_notifications_list", "scope": "own"})
    )

    result = _last_packet_of_type(send_payloads, AdminNotificationsListResultPacket)
    assert result.scope == "own"
    assert result.unreadCount == 1
    assert [entry.title for entry in result.notifications] == [
        "Moonstep transferred to you"
    ]
    assert result.notifications[0].read is False

    await server._handle_message(
        client, json.dumps({"type": "admin_notification_mark_read", "scope": "own"})
    )

    action = _last_packet_of_type(send_payloads, AdminActionResultPacket)
    assert action.ok is True
    assert action.action == "notifications_mark_read"
    assert "1 notification" in action.message

    await server._handle_message(
        client, json.dumps({"type": "admin_notifications_list", "scope": "own"})
    )

    updated = _last_packet_of_type(send_payloads, AdminNotificationsListResultPacket)
    assert updated.unreadCount == 0
    assert updated.notifications[0].read is True


@pytest.mark.asyncio
async def test_admin_notifications_require_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="User",
            user_id="user-id",
            username="user",
            permissions={"chat.send"},
        )
    )
    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "admin_notifications_list", "scope": "admin"})
    )

    result = _last_packet_of_type(send_payloads, AdminActionResultPacket)
    assert result.ok is False
    assert result.action == "notifications_mark_read"
    assert "not authorized" in result.message.lower()


@pytest.mark.asyncio
async def test_admin_notifications_include_global_and_user_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="Admin",
            user_id="admin-id",
            username="admin",
            permissions={"notifications.read.any"},
        )
    )
    server.notification_service.add(
        now_ms=server.item_service.now_ms(),
        kind="blindsoftware.admin",
        title="BlindSoftware sync complete",
        message="Refreshed integrations.",
    )
    server.notification_service.add(
        now_ms=server.item_service.now_ms() + 1,
        kind="direct_message",
        title="Direct message",
        message="User message.",
        target_user_id="other-user-id",
    )
    send_payloads: list[object] = []

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "admin_notifications_list", "scope": "admin"})
    )

    result = _last_packet_of_type(send_payloads, AdminNotificationsListResultPacket)
    assert result.scope == "admin"
    assert result.unreadCount == 2
    assert {entry.title for entry in result.notifications} == {
        "BlindSoftware sync complete",
        "Direct message",
    }


@pytest.mark.asyncio
async def test_blindsoftware_admin_sync_uses_existing_billboard_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    ws = _fake_ws()
    client = _activate_client(
        ClientConnection(
            websocket=ws,
            id="u1",
            nickname="Admin",
            user_id="admin-id",
            username="admin",
            permissions={"server.manage_settings", "notifications.read.any"},
        )
    )
    item = server.item_service.default_item(client, "billboard")
    send_payloads: list[object] = []
    called = False

    async def fake_sync() -> list[object]:
        nonlocal called
        called = True
        return [item]

    async def fake_send(websocket: ServerConnection, packet: object) -> None:
        send_payloads.append(packet)

    monkeypatch.setattr(server, "_sync_blind_productions_billboards_once", fake_sync)
    monkeypatch.setattr(server, "_send", fake_send)

    await server._handle_message(
        client, json.dumps({"type": "admin_blindsoftware_sync"})
    )

    result = _last_packet_of_type(send_payloads, AdminActionResultPacket)
    assert called is True
    assert result.ok is True
    assert result.action == "blindsoftware_admin_sync"
    assert "1 billboard item changed" in result.message
    assert server.notification_service.unread_count(
        user_id=client.user_id or "", include_admin=True
    ) == 1
