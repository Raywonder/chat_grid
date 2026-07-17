from __future__ import annotations

from app.items.types.house.actions import secondary_use_item, use_item
from app.items.types.house.validator import validate_update
from app.items.types.house_alarm.actions import (
    evaluate_access as evaluate_house_alarm_access,
    use_with_credential as use_house_alarm_with_credential,
    secondary_use_item as secondary_use_house_alarm,
    use_item as use_house_alarm,
)


def test_house_alarm_keypad_keeps_invalid_code_out_of_visitor_identity() -> None:
    item = _house_alarm_item()
    item.params.update({"codeMode": "guest", "guestCode": "2468"})

    allowed = use_house_alarm_with_credential(item, "Visitor", "2468", lambda _params: "")
    denied = use_house_alarm_with_credential(item, "Visitor", "1111", lambda _params: "")

    assert allowed.self_message == "Access allowed."
    assert "2468" not in allowed.self_message + allowed.others_message
    assert "1111" not in denied.self_message + denied.others_message
    assert "Visitor: Visitor" in denied.others_message


def test_house_alarm_prefers_signed_in_account_identity_over_display_name() -> None:
    item = _house_alarm_item()
    item.params.update(
        {
            "authorizedNames": "Matthew",
            "authorizedUsernames": "matthew-whitaker",
        }
    )

    assert evaluate_house_alarm_access(item, "Someone Else", username="matthew-whitaker") == "authorized"
    assert evaluate_house_alarm_access(item, "Matthew", username="imposter") == "denied"
from app.items.types.house_alarm.validator import validate_update as validate_house_alarm
from app.items.types.house_keeper.actions import (
    secondary_use_item as secondary_use_house_keeper,
)
from app.items.types.house_keeper.validator import validate_update as validate_house_keeper
from app.items.types.cabin.validator import validate_update as validate_cabin
import pytest

from app.items.types.house_object.actions import (
    secondary_use_item as secondary_use_house_object,
    use_item as use_house_object,
)
from app.items.types.house_object.validator import validate_update as validate_house_object
from app.models import WorldItem


def _house_item() -> WorldItem:
    return WorldItem(
        id="house-1",
        type="house",
        title="House",
        locationId="houses",
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
        useSound="sounds/teleport_start.ogg",
        params={
            "houseName": "Dom's House",
            "ownerName": "Dom",
            "doorState": "unlocked",
            "description": "A warm little house.",
            "welcomeMessage": "Come on in.",
        },
    )


def _house_alarm_item() -> WorldItem:
    return WorldItem(
        id="alarm-1",
        type="house_alarm",
        title="Alarm panel",
        locationId="raywonder_house_entry",
        x=19,
        y=19,
        createdBy="u1",
        createdByName="dominique",
        updatedBy="u1",
        updatedByName="dominique",
        createdAt=1,
        updatedAt=1,
        version=1,
        capabilities=["editable", "carryable", "deletable", "usable"],
        useSound="sounds/notify.ogg",
        params={
            "alarmName": "Raywonder alarm",
            "houseName": "Raywonder House",
            "ownerName": "Dom",
            "alarmMode": "entry_guard",
            "armedState": "armed_home",
            "codeMode": "off",
            "residentCode": "",
            "accessSetupComplete": True,
            "accessMethod": "account",
            "enrolledUsername": "",
            "guestCode": "",
            "disarmCode": "",
            "duressCode": "",
            "codeHint": "",
            "authorizedNames": "Dom, Clawdia",
            "authorizedUsernames": "",
            "entryPrompt": "Please wait at the door.",
            "alertPrompt": "House alarm. Someone is at the door.",
            "allowPrompt": "Access allowed.",
            "denyPrompt": "Access denied.",
            "notificationMode": "in_grid",
            "ntfyTopic": "",
            "waNotifyTarget": "",
            "description": "A voice-enabled alarm panel.",
        },
    )


def _house_keeper_item() -> WorldItem:
    return WorldItem(
        id="keeper-1",
        type="house_keeper",
        title="House keeper",
        locationId="raywonder_house_entry",
        x=19,
        y=20,
        createdBy="u1",
        createdByName="dominique",
        updatedBy="u1",
        updatedByName="dominique",
        createdAt=1,
        updatedAt=1,
        version=1,
        capabilities=["editable", "carryable", "deletable", "usable"],
        useSound="sounds/actions/ui-confirm.mp3",
        params={
            "keeperName": "Raywonder helper",
            "houseName": "Raywonder House",
            "repairMode": "auto_repair",
            "targetKinds": "radio, object",
            "authorizedNames": "",
            "voicePrompt": "I can check the radio.",
            "description": "A little helper agent.",
        },
    )


def test_house_use_welcomes_when_unlocked() -> None:
    result = use_item(_house_item(), "Clawdia", lambda _params: "")

    assert "Come on in." in result.self_message
    assert "Owner: Dom." in result.self_message
    assert result.others_message == "Clawdia opens Dom's House."


def test_house_use_reports_locked() -> None:
    item = _house_item()
    item.params["doorState"] = "locked"

    result = use_item(item, "Clawdia", lambda _params: "")
    details = secondary_use_item(item, "Clawdia", lambda _params: "")

    assert result.self_message == "Dom's House owned by Dom is locked."
    assert "Door: locked." in details.self_message


def test_house_validation_normalizes_door_and_text() -> None:
    normalized = validate_update(
        _house_item(),
        {
            "houseName": "  Studio House  ",
            "ownerName": "  Clawdia  ",
            "doorState": "private",
            "targetLocation": "  Studio_Inside  ",
            "requiredKeyId": "  studio-key  ",
            "keyLocationHint": "  Ask Clawdia.  ",
            "description": "  Creative room  ",
            "welcomeMessage": "  Knock knock  ",
            "ignored": "value",
        },
    )

    assert normalized == {
        "houseName": "Studio House",
        "ownerName": "Clawdia",
        "doorState": "locked",
        "targetLocation": "studio_inside",
        "requiredKeyId": "studio-key",
        "keyLocationHint": "Ask Clawdia.",
        "description": "Creative room",
        "welcomeMessage": "Knock knock",
    }


def test_cabin_validation_preserves_custom_community_target_location() -> None:
    item = WorldItem(
        id="cabin-1",
        type="cabin",
        title="Cabin",
        locationId="houses",
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
            "placeName": "Pine Cabin",
            "ownerName": "",
            "doorState": "unlocked",
            "targetLocation": "",
            "description": "",
            "zoneNotes": "",
            "welcomeMessage": "You enter the cabin.",
        },
    )

    normalized = validate_cabin(
        item,
        {
            "placeName": "Pine Cabin",
            "targetLocation": "Pine_Cabin_Inside",
            "doorState": "unlocked",
        },
    )

    assert normalized["targetLocation"] == "pine_cabin_inside"


def test_house_alarm_triggers_for_unknown_visitor() -> None:
    result = use_house_alarm(_house_alarm_item(), "Visitor", lambda _params: "")

    assert "Please wait at the door." in result.self_message
    assert result.others_message == (
        "House alarm. Someone is at the door. Visitor: Visitor. Location: Raywonder House."
    )
    assert result.updated_params == {"armedState": "triggered"}
    assert "waiting for an owner" in (result.delayed_self_message or "")


def test_house_alarm_allows_authorized_name() -> None:
    result = use_house_alarm(_house_alarm_item(), "Clawdia", lambda _params: "")

    assert result.self_message == "Access allowed."
    assert result.others_message == "Raywonder alarm recognizes Clawdia at Raywonder House."
    assert result.updated_params is None


def test_house_alarm_validation_normalizes_hooks_and_aliases() -> None:
    normalized = validate_house_alarm(
        _house_alarm_item(),
        {
            "alarmName": "  Front panel  ",
            "houseName": "  Dom house  ",
            "ownerName": "  Dominique  ",
            "alarmMode": "privacy",
            "armedState": "away",
            "codeMode": "both",
            "guestCode": " 12-34 ",
            "disarmCode": " 9999 ",
            "duressCode": "*911#",
            "codeHint": "Ask for the porch code.",
            "authorizedNames": " Dom, Clawdia ",
            "entryPrompt": " Wait here. ",
            "alertPrompt": " Alert. ",
            "allowPrompt": " Come in. ",
            "denyPrompt": " Stay out. ",
            "notificationMode": "ntfy wa",
            "ntfyTopic": " house-door ",
            "waNotifyTarget": " owner-wa ",
            "description": " Security panel. ",
            "ignored": "value",
        },
    )
    details = secondary_use_house_alarm(
        _house_alarm_item(), "Visitor", lambda _params: ""
    )

    assert normalized == {
        "alarmName": "Front panel",
        "houseName": "Dom house",
        "ownerName": "Dominique",
        "alarmMode": "privacy",
        "armedState": "armed_away",
        "codeMode": "guest_disarm",
        "residentCode": "",
        "accessSetupComplete": False,
        "accessMethod": "account",
        "enrolledUsername": "",
        "guestCode": "1234",
        "disarmCode": "9999",
        "duressCode": "*911#",
        "codeHint": "Ask for the porch code.",
        "authorizedNames": "Dom, Clawdia",
        "authorizedUsernames": "",
        "entryPrompt": "Wait here.",
        "alertPrompt": "Alert.",
        "allowPrompt": "Come in.",
        "denyPrompt": "Stay out.",
        "notificationMode": "ntfy_whatsapp",
        "ntfyTopic": "house-door",
        "waNotifyTarget": "owner-wa",
        "description": "Security panel.",
    }
    assert "Raywonder alarm protects Raywonder House." in details.self_message
    assert "In-grid alert only." in details.self_message


def test_house_alarm_first_use_enrolls_account_and_resident_code() -> None:
    item = _house_alarm_item()
    item.params["accessSetupComplete"] = False

    result = use_house_alarm_with_credential(
        item,
        "Dominique",
        "setup:identity:2468",
        lambda _params: "",
        username="dominique",
        allow_setup=True,
    )

    assert result.updated_params == {
        "accessSetupComplete": True,
        "accessMethod": "account_keypad",
        "enrolledUsername": "dominique",
        "authorizedUsernames": "dominique",
        "residentCode": "2468",
    }
    assert "2468" not in result.self_message
    item.params.update(result.updated_params)
    assert evaluate_house_alarm_access(item, "Visitor", credential="2468") == "resident"


def test_house_alarm_setup_rejects_unapproved_visitor() -> None:
    item = _house_alarm_item()
    item.params["accessSetupComplete"] = False

    result = use_house_alarm_with_credential(
        item,
        "Visitor",
        "setup:identity",
        lambda _params: "",
        username="visitor",
        allow_setup=False,
    )

    assert result.updated_params is None
    assert "restricted" in result.self_message


def test_house_alarm_accepts_guest_code_without_speaking_code() -> None:
    item = _house_alarm_item()
    item.params.update(
        {
            "codeMode": "guest_disarm",
            "guestCode": "1234",
            "disarmCode": "9999",
            "duressCode": "*911#",
            "codeHint": "Ask for the porch code.",
        }
    )

    result = use_house_alarm(item, "1234", lambda _params: "")
    details = secondary_use_house_alarm(item, "Visitor", lambda _params: "")

    assert result.self_message == "Access allowed."
    assert result.others_message == "Raywonder alarm accepts a guest code at Raywonder House."
    assert result.updated_params is None
    assert "configured codes: guest, disarm, duress" in details.self_message
    assert "Code hint: Ask for the porch code." in details.self_message
    assert "1234" not in details.self_message
    assert "9999" not in details.self_message
    assert "*911#" not in details.self_message


def test_house_alarm_disarm_and_duress_codes_update_state() -> None:
    item = _house_alarm_item()
    item.params.update(
        {
            "codeMode": "guest_disarm",
            "guestCode": "1234",
            "disarmCode": "9999",
            "duressCode": "*911#",
        }
    )

    disarm_result = use_house_alarm(item, "9999", lambda _params: "")
    duress_result = use_house_alarm(item, "*911#", lambda _params: "")

    assert disarm_result.updated_params == {"armedState": "disarmed"}
    assert "accepts the disarm code" in disarm_result.self_message
    assert duress_result.self_message == "Access allowed."
    assert duress_result.updated_params == {"armedState": "triggered"}
    assert "Duress code used" in duress_result.others_message


def test_house_alarm_rejects_duplicate_or_invalid_codes() -> None:
    item = _house_alarm_item()

    normalized = validate_house_alarm(
        item,
        {
            **item.params,
            "codeMode": "guest",
            "guestCode": " 12-34 ",
            "disarmCode": "",
            "duressCode": "",
        },
    )
    assert normalized["guestCode"] == "1234"

    try:
        validate_house_alarm(
            item,
            {
                **item.params,
                "codeMode": "guest_disarm",
                "guestCode": "1234",
                "disarmCode": "1234",
            },
        )
    except ValueError as exc:
        assert "disarmCode must be different from guestCode" in str(exc)
    else:
        raise AssertionError("duplicate alarm codes should fail validation")

    try:
        validate_house_alarm(
            item,
            {
                **item.params,
                "codeMode": "guest",
                "guestCode": "secret",
            },
        )
    except ValueError as exc:
        assert "guestCode may contain only digits, star, and pound" in str(exc)
    else:
        raise AssertionError("non-keypad alarm code should fail validation")


def test_house_keeper_validation_and_secondary_use() -> None:
    item = _house_keeper_item()

    normalized = validate_house_keeper(
        item,
        {
            "keeperName": "  Radio helper  ",
            "houseName": "  Dom house  ",
            "repairMode": "inspect",
            "targetKinds": " radio, object ",
            "authorizedNames": " Dom, Clawdia ",
            "voicePrompt": " I can fix the radio if you ask. ",
            "description": " A little in-world helper. ",
            "ignored": "value",
        },
    )
    item.params.update(normalized)
    details = secondary_use_house_keeper(item, "Visitor", lambda _params: "")

    assert normalized == {
        "keeperName": "Radio helper",
        "houseName": "Dom house",
        "repairMode": "inspect",
        "backgroundChecksEnabled": True,
        "checkIntervalHours": 6,
        "targetKinds": "radio, object",
        "authorizedNames": "Dom, Clawdia",
        "voicePrompt": "I can fix the radio if you ask.",
        "description": "A little in-world helper.",
        "lastAutoCheckAt": 0,
        "lastAutoCheckSummary": "",
    }
    assert "Radio helper looks after Dom house." in details.self_message
    assert "Mode: inspect." in details.self_message


def test_house_object_window_toggles_and_reports_outside_ambience() -> None:
    item = WorldItem(
        id="window-1",
        type="house_object",
        title="Kitchen window",
        locationId="raywonder_house_kitchen",
        x=1,
        y=2,
        createdBy="system",
        createdByName="system",
        updatedBy="system",
        updatedByName="system",
        createdAt=1,
        updatedAt=1,
        version=1,
        capabilities=["editable", "carryable", "deletable", "usable"],
        params={
            "objectKind": "window",
            "placement": "wall",
            "material": "glass",
            "fragility": "delicate",
            "condition": "intact",
            "windowState": "closed",
            "description": "An outside-facing kitchen window.",
        },
    )

    inspect_closed = use_house_object(item, "Clawdia", lambda _params: "")
    toggle = secondary_use_house_object(item, "Clawdia", lambda _params: "")
    item.params.update(toggle.updated_params or {})
    inspect_open = use_house_object(item, "Clawdia", lambda _params: "")
    with pytest.raises(ValueError, match="Window objects must use wall placement"):
        validate_house_object(item, {**item.params, "placement": "counter"})

    assert "Outside ambience is muffled" in inspect_closed.self_message
    assert toggle.self_message == "You open Kitchen window."
    assert toggle.updated_params["windowState"] == "open"
    assert "Outside ambience can carry in from outdoors" in inspect_open.self_message
