from types import SimpleNamespace

from app.server import SignalingServer


def test_media_guide_groups_tv_channels_and_lists_sources() -> None:
    item = SimpleNamespace(
        title="Living room TV",
        params={
            "stationPresets": [
                {"title": "BBC NEWS", "streamUrl": "https://example.test/news", "category": "News"},
                {"title": "Film4", "streamUrl": "https://example.test/film", "category": "Movies"},
            ],
            "tvProviderSources": [{"title": "Bema Media Player guide"}],
        },
    )

    message = SignalingServer._media_guide_message(item, tv=True)

    assert "TV guide for Living room TV." in message
    assert "News: 1 BBC NEWS" in message
    assert "Movies: 2 Film4" in message
    assert "Guide sources: Bema Media Player guide" in message
