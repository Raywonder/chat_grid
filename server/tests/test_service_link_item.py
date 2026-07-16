from __future__ import annotations

from app.items.types.service_link.actions import secondary_use_item, use_item
from app.items.types.service_link.portal_state import effective_portal_state
from app.items.types.service_link.validator import validate_update
from app.models import WorldItem


def _service_item() -> WorldItem:
    return WorldItem(
        id="service-1",
        type="service_link",
        title="blind.software",
        locationId="city",
        x=1,
        y=2,
        createdBy="u1",
        createdByName="dominique",
        updatedBy="u1",
        updatedByName="dominique",
        createdAt=1,
        updatedAt=1,
        version=1,
        capabilities=["editable", "carryable", "deletable", "usable"],
        params={
            "serviceKind": "site",
            "url": "https://blind.software/",
            "targetLocation": "",
            "doorState": "unlocked",
            "description": "Accessible software catalog.",
            "launchMessage": "",
            "enabled": True,
        },
    )


def test_service_link_use_speaks_details_and_url() -> None:
    result = use_item(_service_item(), "Dom", lambda _params: "")

    assert "blind.software is a site" in result.self_message
    assert "Accessible software catalog" in result.self_message
    assert "https://blind.software/" in result.self_message
    assert result.others_message == ""


def test_service_link_secondary_use_speaks_full_details() -> None:
    result = secondary_use_item(_service_item(), "Dom", lambda _params: "")

    assert "blind.software is a site" in result.self_message
    assert "URL: https://blind.software/" in result.self_message


def test_service_link_validation_normalizes_bool_and_kind() -> None:
    item = _service_item()
    normalized = validate_update(
        item,
        {
            "serviceKind": "APP",
            "url": "/local/service",
            "targetLocation": " Arcade ",
            "doorState": " LOCKED ",
            "description": "  Local service  ",
            "launchMessage": "  Open this service  ",
            "enabled": "off",
            "ignored": "value",
        },
    )

    assert normalized == {
        "serviceKind": "app",
        "url": "/local/service",
        "targetLocation": "arcade",
        "portalDestinationMode": "random",
        "portalLocationPool": "",
        "doorState": "locked",
        "requiredKeyId": "",
        "keyLocationHint": "",
        "portalState": "open",
        "portalOpenSeconds": 0,
        "portalClosedSeconds": 0,
        "softwareAuthor": "",
        "verificationStatus": "author_verified",
        "verificationAvailableAt": 0,
        "description": "Local service",
        "launchMessage": "Open this service",
        "enabled": False,
        "emitRange": 12,
        "emitVolume": 100,
        "emitSoundSpeed": 50,
        "emitSoundTempo": 50,
        "emitInitialDelay": 0,
        "emitLoopDelay": 0,
        "useSound": "",
        "emitSound": "",
    }


def test_service_link_validation_accepts_game_kind() -> None:
    item = _service_item()
    normalized = validate_update(
        item,
        {
            **item.params,
            "serviceKind": "GAME",
            "url": "https://blind.software/private/moonstep-28c93ae33fd0e29d/",
        },
    )

    assert normalized["serviceKind"] == "game"
    assert normalized["url"] == "https://blind.software/private/moonstep-28c93ae33fd0e29d/"


def test_service_link_speaks_author_and_verification_status() -> None:
    item = _service_item()
    item.params.update(
        {
            "softwareAuthor": "Clawdia",
            "verificationStatus": "author_verified",
        }
    )

    result = secondary_use_item(item, "Dom", lambda _params: "")

    assert "Author: Clawdia" in result.self_message
    assert "Verification: author verified" in result.self_message


def test_service_link_validation_accepts_portal_kind() -> None:
    item = _service_item()
    normalized = validate_update(
        item,
        {
            **item.params,
            "serviceKind": "PORTAL",
            "targetLocation": "Arcade",
            "portalState": "closed",
            "portalDestinationMode": "static",
            "portalLocationPool": "City; Arcade, Offices",
            "portalOpenSeconds": "75",
            "portalClosedSeconds": "12.5",
        },
    )

    assert normalized["serviceKind"] == "portal"
    assert normalized["targetLocation"] == "arcade"
    assert normalized["portalDestinationMode"] == "static"
    assert normalized["portalLocationPool"] == "city,arcade,offices"
    assert normalized["portalState"] == "closed"
    assert normalized["portalOpenSeconds"] == 75
    assert normalized["portalClosedSeconds"] == 12.5


def test_service_link_validation_normalizes_audio_params() -> None:
    item = _service_item()
    normalized = validate_update(
        item,
        {
            **item.params,
            "serviceKind": "portal",
            "targetLocation": "Houses",
            "emitRange": "11",
            "emitVolume": "45",
            "emitSoundSpeed": "48.5",
            "emitSoundTempo": "51.5",
            "emitInitialDelay": "0.3",
            "emitLoopDelay": "1.2",
            "useSound": "teleport_departure_whoosh.ogg",
            "emitSound": "/sounds/teleport_pad_loop.ogg",
        },
    )

    assert normalized["targetLocation"] == "houses"
    assert normalized["emitRange"] == 11
    assert normalized["emitVolume"] == 45
    assert normalized["emitSoundSpeed"] == 48.5
    assert normalized["emitSoundTempo"] == 51.5
    assert normalized["emitInitialDelay"] == 0.3
    assert normalized["emitLoopDelay"] == 1.2
    assert normalized["useSound"] == "sounds/teleport_departure_whoosh.ogg"
    assert normalized["emitSound"] == "sounds/teleport_pad_loop.ogg"


def test_service_link_locked_door_reports_locked() -> None:
    item = _service_item()
    item.title = "Bedroom door"
    item.params.update(
        {
            "serviceKind": "door",
            "targetLocation": "raywonder_house_bedroom",
            "doorState": "locked",
            "keyLocationHint": "The bedroom key might be on the doorknob.",
            "description": "Private room door.",
        }
    )

    result = use_item(item, "Dom", lambda _params: "")
    details = secondary_use_item(item, "Dom", lambda _params: "")

    assert result.self_message == "Bedroom door is locked. The bedroom key might be on the doorknob."
    assert "Door status: locked" in details.self_message
    assert "Key hint: The bedroom key might be on the doorknob." in details.self_message


def test_service_link_closed_portal_reports_closed() -> None:
    item = _service_item()
    item.title = "Town portal"
    item.params.update(
        {
            "serviceKind": "portal",
            "targetLocation": "town",
            "portalState": "closed",
            "portalDestinationMode": "static",
            "portalOpenSeconds": 0,
            "portalClosedSeconds": 0,
        }
    )

    result = use_item(item, "Dom", lambda _params: "")
    details = secondary_use_item(item, "Dom", lambda _params: "")

    assert result.self_message == "Town portal is closed."
    assert "Portal status: closed" in details.self_message
    assert "Destination mode: static" in details.self_message


def test_service_link_portal_cycle_alternates_from_anchor() -> None:
    item = _service_item()
    item.createdAt = 1_000
    item.updatedAt = 1_000
    item.params.update(
        {
            "serviceKind": "portal",
            "targetLocation": "town",
            "portalState": "open",
            "portalOpenSeconds": 10,
            "portalClosedSeconds": 5,
        }
    )

    assert effective_portal_state(item, now_ms=5_000) == "open"
    assert effective_portal_state(item, now_ms=12_000) == "closed"
    assert effective_portal_state(item, now_ms=17_000) == "open"
