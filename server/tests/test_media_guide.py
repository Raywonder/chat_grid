from types import SimpleNamespace

from app.models import MediaCastStatePacket
from app.server import SignalingServer


def test_media_guide_groups_tv_channels_and_lists_sources() -> None:
    item = SimpleNamespace(
        id="living-room-tv",
        locationId="living-room",
        title="Living room TV",
        params={
            "stationPresets": [
                {"title": "BBC NEWS", "streamUrl": "https://example.test/news", "category": "News"},
                {"title": "Film4", "streamUrl": "https://example.test/film", "category": "Movies"},
            ],
            "tvProviderSources": [{"title": "Bema Media Player guide"}],
        },
    )

    server = SignalingServer("127.0.0.1", 8765, None, None)
    message = server._media_guide_message(item, tv=True)

    assert "TV guide for Living room TV." in message
    assert "News: 1 BBC NEWS" in message
    assert "Movies: 2 Film4" in message
    assert "Guide sources: Bema Media Player guide" in message


def test_media_guide_lists_shared_screen_only_while_cast_is_active() -> None:
    item = SimpleNamespace(
        id="living-room-tv",
        locationId="living-room",
        title="Living room TV",
        params={"stationPresets": []},
    )
    server = SignalingServer("127.0.0.1", 8765, None, None)
    server._active_media_casts["living-room"] = {
        "caster-1": MediaCastStatePacket(
            type="media_cast_state",
            casterId="caster-1",
            casterNickname="Dom",
            targetItemId="living-room-tv",
            active=True,
            mediaKind="video",
            deviceName="Desktop screen",
            stationCode="CAST-ABC123",
            stationName="Desktop screen",
            title="Shared screen",
            artist="Dom",
        )
    }

    message = server._media_guide_message(item, tv=True)
    assert "Shared content: Shared screen from Dom (Desktop screen)" in message

    server._active_media_casts.clear()
    assert "Shared content:" not in server._media_guide_message(item, tv=True)
