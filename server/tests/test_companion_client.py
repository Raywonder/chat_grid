"""Tests for the durable companion presence receipt."""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from tools.companion_client import CompanionClient, _choose_auto_seat


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))


def test_write_state_publishes_current_world_receipt(tmp_path) -> None:
    """The state hook exposes enough fresh data to prove world presence."""

    state_file = tmp_path / "companion.state.json"
    client = CompanionClient(
        url="ws://example.invalid",
        origin="https://example.invalid",
        username="clawdia",
        password="secret-for-test",
        nickname="Claudia",
        command_file=tmp_path / "commands.jsonl",
        state_file=state_file,
    )
    client.client_id = "client-1"
    client.location_id = "raywonder_house_living_room"
    client.x = 19
    client.y = 20

    client._write_state(connected=True, detail="welcome_ready")

    receipt = json.loads(state_file.read_text(encoding="utf-8"))
    assert receipt["connected"] is True
    assert receipt["detail"] == "welcome_ready"
    assert receipt["locationId"] == "raywonder_house_living_room"
    assert receipt["x"] == 19
    assert receipt["y"] == 20
    assert receipt["updatedAt"]
    assert not state_file.with_suffix(".json.tmp").exists()


def test_choose_auto_seat_skips_full_chair_and_uses_roomy_couch() -> None:
    """Known occupants prevent collisions while shared furniture stays usable."""

    chair = {
        "id": "chair",
        "type": "furniture",
        "title": "Chair",
        "x": 20,
        "y": 20,
        "params": {"furnitureKind": "chair", "seatingCapacity": 1, "postureMode": "sit"},
    }
    couch = {
        "id": "couch",
        "type": "furniture",
        "title": "Couch",
        "x": 21,
        "y": 20,
        "params": {"furnitureKind": "couch", "seatingCapacity": 4, "postureMode": "sit"},
    }
    users = {"person": {"id": "person", "seatedItemId": "chair"}}

    chosen = _choose_auto_seat(
        items={"chair": chair, "couch": couch}, users=users, x=20, y=20
    )

    assert chosen is couch


def test_choose_auto_seat_skips_full_shared_furniture_and_bed_when_settled() -> None:
    """A full bench and bed are not automatic choices in a neutral mood."""

    bench = {
        "id": "bench",
        "type": "furniture",
        "title": "Bench",
        "x": 20,
        "y": 20,
        "params": {"furnitureKind": "bench", "seatingCapacity": 2, "postureMode": "sit"},
    }
    bed = {
        "id": "bed",
        "type": "furniture",
        "title": "Bed",
        "x": 20,
        "y": 21,
        "params": {"furnitureKind": "bed", "seatingCapacity": 2, "postureMode": "lie"},
    }
    users = {
        "one": {"id": "one", "seatedItemId": "bench"},
        "two": {"id": "two", "seatedItemId": "bench"},
    }

    assert _choose_auto_seat(
        items={"bench": bench, "bed": bed}, users=users, x=20, y=20
    ) is None


def test_choose_auto_seat_includes_bed_when_mood_suits_rest() -> None:
    """Beds become considerate automatic choices in a restful mood."""

    bed = {
        "id": "bed",
        "type": "furniture",
        "title": "Bedroom bed",
        "x": 20,
        "y": 20,
        "params": {"furnitureKind": "bed", "seatingCapacity": 2, "postureMode": "lie"},
    }

    assert _choose_auto_seat(
        items={"bed": bed}, users={}, x=20, y=20, mood="dreamy"
    ) is bed


def test_choose_auto_seat_allows_booth_with_room() -> None:
    """Booths participate in the same capacity-aware sharing rules."""

    booth = {
        "id": "booth",
        "type": "furniture",
        "title": "Corner booth",
        "x": 20,
        "y": 20,
        "params": {"furnitureKind": "booth", "seatingCapacity": 4, "postureMode": "sit"},
    }
    users = {
        "one": {"id": "one", "seatedItemId": "booth"},
        "two": {"id": "two", "seatedItemId": "booth"},
    }

    assert _choose_auto_seat(items={"booth": booth}, users=users, x=20, y=20) is booth


@pytest.mark.asyncio
async def test_companion_reacts_to_directed_social_action() -> None:
    """A directed action gets one bounded, reciprocal world action."""

    client = CompanionClient(
        url="ws://example.invalid",
        origin="https://example.invalid",
        username="clawdia",
        password="secret-for-test",
        nickname="Claudia",
        command_file=Path("commands.jsonl"),
        state_file=Path("state.json"),
    )
    client.client_id = "clawdia-id"
    client.users = {"dom-id": {"id": "dom-id", "nickname": "Dominique"}}
    socket = FakeWebSocket()

    await client._maybe_react_to_social_action(
        socket,
        {"actorId": "dom-id", "targetId": "clawdia-id", "actionId": "wave"},
    )

    assert socket.sent == [
        {"type": "user_action", "actionId": "wave", "targetId": "dom-id"}
    ]


@pytest.mark.asyncio
async def test_companion_reacts_to_nearby_person_lying_down() -> None:
    """A nearby person settling into bed gets a quiet listening response."""

    client = CompanionClient(
        url="ws://example.invalid",
        origin="https://example.invalid",
        username="clawdia",
        password="secret-for-test",
        nickname="Claudia",
        command_file=Path("commands.jsonl"),
        state_file=Path("state.json"),
    )
    client.client_id = "clawdia-id"
    client.x = 20
    client.y = 20
    socket = FakeWebSocket()

    await client._maybe_react_to_posture(
        socket,
        {"id": "dom-id", "x": 21, "y": 20, "posture": "lying"},
    )

    assert socket.sent == [
        {"type": "user_action", "actionId": "listen", "targetId": "dom-id"}
    ]
