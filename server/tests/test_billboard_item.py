from __future__ import annotations

from app.items.types.billboard.actions import secondary_use_item, use_item
from app.items.types.billboard.validator import validate_update
from app.models import WorldItem


def _billboard_item() -> WorldItem:
    return WorldItem(
        id="billboard-1",
        type="billboard",
        title="Moonstep board",
        locationId="city",
        x=3,
        y=4,
        createdBy="u1",
        createdByName="dominique",
        updatedBy="u1",
        updatedByName="dominique",
        createdAt=1,
        updatedAt=1,
        version=1,
        capabilities=["editable", "carryable", "deletable", "usable"],
        params={
            "enabled": True,
            "billboardMode": "interactive",
            "itemVisibility": "visible",
            "headline": "Moonstep Runner",
            "body": "Walk over here to play the new game.",
            "url": "https://blind.software/private/moonstep-28c93ae33fd0e29d/",
            "announcementText": "Moonstep Runner has new location ambience.",
            "voiceName": "Clawdia",
            "voiceAssetUrl": "",
            "bannerText": "New game|MIDI support|Binaural footsteps",
            "rotationSeconds": 12,
            "emitRange": 12,
        },
    )


def test_billboard_use_speaks_interactive_details() -> None:
    result = use_item(_billboard_item(), "Dom", lambda _params: "")

    assert "Moonstep Runner" in result.self_message
    assert "Walk over here to play" in result.self_message
    assert "Rotating banners: New game; MIDI support; Binaural footsteps" in result.self_message
    assert "Clawdia says: Moonstep Runner has new location ambience" in result.self_message
    assert "https://blind.software/private/moonstep-28c93ae33fd0e29d/" in result.self_message
    assert result.others_message == ""


def test_billboard_display_only_reports_not_interactive() -> None:
    item = _billboard_item()
    item.params["billboardMode"] = "display_only"

    result = use_item(item, "Dom", lambda _params: "")
    details = secondary_use_item(item, "Dom", lambda _params: "")

    assert "Display only" in result.self_message
    assert "Display only" in details.self_message


def test_billboard_audio_only_prefers_announcement_voice() -> None:
    item = _billboard_item()
    item.params["billboardMode"] = "audio_only"
    item.params["itemVisibility"] = "hidden"

    result = use_item(item, "Dom", lambda _params: "")

    assert result.self_message == "Clawdia: Moonstep Runner has new location ambience."
    assert result.others_message == ""


def test_billboard_validation_normalizes_modes_and_bounds() -> None:
    item = _billboard_item()

    normalized = validate_update(
        item,
        {
            "enabled": "on",
            "billboardMode": "AUDIO_ONLY",
            "itemVisibility": "HIDDEN",
            "headline": "  Announcements  ",
            "body": "  Walk to the billboard to choose a link.  ",
            "url": "/chatgrid/",
            "announcementText": "  Spoken out by a voice.  ",
            "voiceName": "  Clawdia  ",
            "voiceAssetUrl": "  /sounds/billboards/clawdia-town.mp3  ",
            "bannerText": "  One | Two  ",
            "rotationSeconds": "20",
            "emitRange": "18",
            "ignored": "value",
        },
    )

    assert normalized == {
        "enabled": True,
        "billboardMode": "audio_only",
        "itemVisibility": "hidden",
        "headline": "Announcements",
        "body": "Walk to the billboard to choose a link.",
        "url": "/chatgrid/",
        "announcementText": "Spoken out by a voice.",
        "voiceName": "Clawdia",
        "voiceAssetUrl": "sounds/billboards/clawdia-town.mp3",
        "bannerText": "One | Two",
        "rotationSeconds": 20,
        "emitRange": 18,
    }


def test_billboard_validation_allows_public_voice_asset_url() -> None:
    item = _billboard_item()

    normalized = validate_update(
        item,
        {
            **item.params,
            "voiceAssetUrl": "https://blind.software/chatgrid/sounds/billboards/test.mp3",
        },
    )

    assert (
        normalized["voiceAssetUrl"]
        == "https://blind.software/chatgrid/sounds/billboards/test.mp3"
    )
