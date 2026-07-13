from __future__ import annotations

from app.items.types.service_link.actions import secondary_use_item, use_item
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
            "description": "  Local service  ",
            "launchMessage": "  Open this service  ",
            "enabled": "off",
            "ignored": "value",
        },
    )

    assert normalized == {
        "serviceKind": "app",
        "url": "/local/service",
        "description": "Local service",
        "launchMessage": "Open this service",
        "enabled": False,
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
