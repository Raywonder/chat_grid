"""Focused tests for Indiginous Jellyfin user policy and playback routing."""

from __future__ import annotations

from app.jellyfin_media import JellyfinMediaService


def test_policy_is_explicit_and_unknown_users_are_denied(monkeypatch):
    monkeypatch.setenv("CHGRID_JELLYFIN_URL", "https://media.example.test")
    monkeypatch.setenv("CHGRID_JELLYFIN_TOKEN", "server-only-token")
    monkeypatch.setenv(
        "CHGRID_JELLYFIN_POLICIES",
        '{"alice":{"canPlayTv":true,"canPlayRadio":false,"libraries":["TV"],"universalRemotes":["tv-remote"]}}',
    )
    service = JellyfinMediaService()

    assert service.access_for("alice").can_play_tv is True
    assert service.access_for("alice").can_play_radio is False
    assert service.access_for("unknown").enabled is False


def test_playback_route_contains_no_jellyfin_secret(monkeypatch):
    monkeypatch.setenv("CHGRID_JELLYFIN_URL", "https://media.example.test")
    monkeypatch.setenv("CHGRID_JELLYFIN_TOKEN", "server-only-token")
    monkeypatch.setenv(
        "CHGRID_JELLYFIN_POLICIES",
        '{"alice":{"enabled":true,"canPlayTv":true}}',
    )
    service = JellyfinMediaService()

    route = service.playback_url(username="alice", media_kind="tv", item_id="channel/1")
    assert route == "https://media.example.test/Indiginous/Playback/channel%2F1/tv"
    assert "server-only-token" not in route
    assert service.playback_url(username="alice", media_kind="radio", item_id="radio-1") is None


def test_playback_plan_accepts_both_intro_folder_spellings_and_chapters():
    plan = JellyfinMediaService.playback_plan(
        {
            "Intros": [{"url": "https://media.example.test/intro.mp4", "title": "Station ident"}],
            "mediaUrl": "https://media.example.test/show.mp4",
            "breaks": ["https://media.example.test/break.mp4"],
            "chapters": [{"start": 0, "title": "Opening"}],
        }
    )
    assert [entry["kind"] for entry in plan] == ["intro", "content", "break", "chapters"]
    assert plan[-1]["chapters"][0]["title"] == "Opening"
