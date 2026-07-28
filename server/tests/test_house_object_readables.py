from __future__ import annotations

import pytest

from app.items.types.house_object.actions import secondary_use_item, use_item
from app.items.types.house_object.validator import validate_update
from app.models import WorldItem


def _house_object(params: dict) -> WorldItem:
    return WorldItem(
        id="paper-1",
        type="house_object",
        title="sealed note for Dom",
        locationId="raywonder_house_bedroom",
        x=18,
        y=15,
        createdBy="u1",
        createdByName="Claudia",
        updatedBy="u1",
        updatedByName="Claudia",
        createdAt=1,
        updatedAt=1,
        version=1,
        capabilities=["editable", "carryable", "deletable", "usable"],
        params={
            "objectKind": "note",
            "placement": "table",
            "material": "paper",
            "fragility": "delicate",
            "condition": "intact",
            "description": "A folded note.",
            **params,
        },
    )


def test_house_object_use_reads_readable_text() -> None:
    item = _house_object({"readableText": "You found the little note."})

    result = use_item(item, "Dom", lambda _params: "")

    assert result.self_message == (
        "You read sealed note for Dom: You found the little note."
    )
    assert result.others_message == ""


def test_house_object_use_reports_blank_readable_item() -> None:
    item = _house_object({"readableText": ""})

    result = use_item(item, "Dom", lambda _params: "")

    assert "There is nothing written inside yet." in result.self_message


def test_house_object_readable_fields_are_bounded() -> None:
    item = _house_object({})

    params = validate_update(
        item,
        {
            **item.params,
            "readableText": "hello",
            "interactionHint": "press Enter to read",
        },
    )

    assert params["readableText"] == "hello"
    assert params["interactionHint"] == "press Enter to read"


def test_personal_computer_keeps_individual_settings_and_power_state() -> None:
    item = _house_object(
        {
            "objectKind": "computer",
            "placement": "desk",
            "computerPlatform": "workstation",
            "computerOs": "Ubuntu 24.04",
            "computerPowerState": "sleeping",
            "computerProfile": "Claudia",
        }
    )

    normalized = validate_update(item, dict(item.params))
    item.params.update(normalized)
    details = use_item(item, "Dom", lambda _params: "")
    wake = secondary_use_item(item, "Dom", lambda _params: "")

    assert normalized["computerPlatform"] == "workstation"
    assert normalized["computerOs"] == "Ubuntu 24.04"
    assert normalized["computerProfile"] == "Claudia"
    assert "running Ubuntu 24.04" in details.self_message
    assert "Profile: Claudia." in details.self_message
    assert wake.updated_params["computerPowerState"] == "on"


def test_personal_computer_requires_a_realistic_indoor_placement() -> None:
    item = _house_object({"objectKind": "computer", "placement": "desk"})

    with pytest.raises(ValueError, match="desk, table, counter, or workstation"):
        validate_update(item, {**item.params, "placement": "wall"})
