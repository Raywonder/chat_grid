from __future__ import annotations

import asyncio

import pytest

from app.server import SignalingServer


def test_ui_definitions_are_complete_for_all_item_types() -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    definitions = server._build_ui_definitions()

    item_type_order = definitions.get("itemTypeOrder")
    item_types = definitions.get("itemTypes")
    assert isinstance(item_type_order, list)
    assert isinstance(item_types, list)
    assert item_type_order
    assert len(item_types) == len(item_type_order)
    assert [entry.get("type") for entry in item_types] == item_type_order
    assert {
        "qr_code",
        "room",
        "shack",
        "shed",
        "cabin",
        "ecrypto_bank",
        "ecrypto_wallet",
        "radio_remote",
    }.issubset(set(item_type_order))

    required_global_property_keys = {
        "useSound",
        "emitSound",
        "useCooldownMs",
        "emitRange",
        "directional",
        "emitSoundSpeed",
        "emitSoundTempo",
    }
    required_system_metadata_keys = {
        "type",
        "x",
        "y",
        "carrierId",
        "version",
        "createdBy",
        "updatedBy",
        "createdAt",
        "updatedAt",
        "capabilities",
    }

    for entry in item_types:
        assert isinstance(entry.get("type"), str)
        assert isinstance(entry.get("label"), str)
        assert isinstance(entry.get("editableProperties"), list)
        assert isinstance(entry.get("capabilities"), list)
        assert isinstance(entry.get("propertyMetadata"), dict)
        assert isinstance(entry.get("globalProperties"), dict)

        editable_properties = entry["editableProperties"]
        capabilities = entry["capabilities"]
        property_metadata = entry["propertyMetadata"]
        global_properties = entry["globalProperties"]

        assert capabilities
        assert required_global_property_keys.issubset(set(global_properties.keys()))
        assert required_system_metadata_keys.issubset(set(property_metadata.keys()))
        for property_key in editable_properties:
            if property_key == "title":
                continue
            assert property_key in property_metadata
            metadata = property_metadata[property_key]
            assert isinstance(metadata, dict)
            if metadata.get("valueType") == "list":
                options = metadata.get("options")
                assert isinstance(options, list)
                assert options

    by_type = {entry["type"]: entry for entry in item_types}
    assert by_type["radio_remote"]["label"] == "Universal radio remote"
    assert "objectKind" in by_type["radio_remote"]["editableProperties"]
    assert "single_room_studio" in by_type["room"]["propertyMetadata"]["roomLayout"]["options"]
    assert by_type["room"]["propertyMetadata"]["spaceKind"]["options"] == ["indoor", "outdoor"]
    assert by_type["room"]["propertyMetadata"]["widthSquares"]["range"]["max"] == 41
    assert "squareFeet" in by_type["room"]["editableProperties"]
    assert "ecrypto" in by_type["qr_code"]["propertyMetadata"]["payloadKind"]["options"]
    assert "wallets_transfers" in by_type["ecrypto_bank"]["propertyMetadata"]["serviceScope"]["options"]
    assert "enabled" not in by_type["ecrypto_bank"]["editableProperties"]
    assert "emitSound" not in by_type["ecrypto_bank"]["editableProperties"]
    assert "emitVolume" not in by_type["ecrypto_bank"]["editableProperties"]
    assert "targetLocation" in by_type["ecrypto_bank"]["editableProperties"]
    assert "carryable" not in by_type["ecrypto_bank"]["capabilities"]
    assert "carryable" in by_type["ecrypto_wallet"]["capabilities"]
    assert "enabled" not in by_type["ecrypto_wallet"]["editableProperties"]
    assert "real" in by_type["ecrypto_wallet"]["propertyMetadata"]["networkMode"]["options"]


@pytest.mark.asyncio
async def test_state_save_requests_are_debounced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SignalingServer("127.0.0.1", 8765, None, None)
    save_calls: list[str] = []

    def fake_save_state() -> None:
        save_calls.append("saved")

    monkeypatch.setattr(server.item_service, "save_state", fake_save_state)

    server._request_state_save()
    server._request_state_save()
    server._request_state_save()
    await asyncio.sleep(0.25)
    assert len(save_calls) == 1

    server._request_state_save()
    await asyncio.sleep(0.25)
    assert len(save_calls) == 2
