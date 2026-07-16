from __future__ import annotations

import json
from typing import Any

from app.items.types.radio_station import aaastreamer


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, *_args: object) -> bytes:
        return self._body


def test_resolve_aaastreamer_playback_from_public_station_page(
    monkeypatch,
) -> None:
    station_url = "https://aaastreamer.devinecreations.net/s/soulfoodradio-media"
    hls_url = "https://aaastreamer.devinecreations.net/hls/live/key/index.m3u8"
    page = '<video data-stream-id="str_123" data-current-playback-url="/fallback.m3u8"></video>'
    api_payload: dict[str, Any] = {
        "success": True,
        "stream": {
            "title": "SoulFoodRadio",
            "playbackUrl": hls_url,
            "nowPlaying": {"title": "SoulFoodRadio Shoutcast relay"},
        },
    }

    def fake_validate(url: str, *, field_name: str = "url") -> str:
        return url

    def fake_open(url: str, **_kwargs: object) -> _FakeResponse:
        if url == station_url:
            return _FakeResponse(page)
        if url == "https://aaastreamer.devinecreations.net/api/streams/str_123":
            return _FakeResponse(json.dumps(api_payload))
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(aaastreamer, "validate_public_media_url", fake_validate)
    monkeypatch.setattr(aaastreamer, "open_validated_public_url", fake_open)

    resolved = aaastreamer.resolve_aaastreamer_playback(station_url)

    assert resolved is not None
    assert resolved.title == "SoulFoodRadio"
    assert resolved.now_playing == "SoulFoodRadio Shoutcast relay"
    assert resolved.playback_url == hls_url


def test_resolve_aaastreamer_playback_uses_page_fallback_when_api_fails(
    monkeypatch,
) -> None:
    station_url = "https://aaastreamer.devinecreations.net/s/main-stream"
    fallback_url = "https://aaastreamer.devinecreations.net/hls/live/key/index.m3u8"
    page = (
        '<video data-stream-id="str_123" '
        f'data-current-playback-url="{fallback_url}"></video>'
    )

    def fake_validate(url: str, *, field_name: str = "url") -> str:
        return url

    def fake_open(url: str, **_kwargs: object) -> _FakeResponse:
        if url == station_url:
            return _FakeResponse(page)
        if url == "https://aaastreamer.devinecreations.net/api/streams/str_123":
            raise OSError("api unavailable")
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(aaastreamer, "validate_public_media_url", fake_validate)
    monkeypatch.setattr(aaastreamer, "open_validated_public_url", fake_open)

    resolved = aaastreamer.resolve_aaastreamer_playback(station_url)

    assert resolved is not None
    assert resolved.playback_url == fallback_url


def test_resolve_aaastreamer_playback_supports_other_station_hosts(
    monkeypatch,
) -> None:
    station_url = "https://radio.example.net/s/soul-food-radio"
    page = (
        '<video data-stream-id="station-42" '
        'data-current-playback-url="/fallback.m3u8"></video>'
    )
    api_payload: dict[str, Any] = {
        "success": True,
        "stream": {
            "title": "Soul Food Radio",
            "playbackUrl": "/hls/live/key/index.m3u8",
            "nowPlaying": "Direct AAAStreamer page",
        },
    }

    def fake_validate(url: str, *, field_name: str = "url") -> str:
        return url

    def fake_open(url: str, **_kwargs: object) -> _FakeResponse:
        if url == station_url:
            return _FakeResponse(page)
        if url == "https://radio.example.net/api/streams/station-42":
            return _FakeResponse(json.dumps(api_payload))
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(aaastreamer, "validate_public_media_url", fake_validate)
    monkeypatch.setattr(aaastreamer, "open_validated_public_url", fake_open)

    resolved = aaastreamer.resolve_aaastreamer_playback(station_url)

    assert resolved is not None
    assert resolved.title == "Soul Food Radio"
    assert resolved.now_playing == "Direct AAAStreamer page"
    assert resolved.playback_url == "https://radio.example.net/hls/live/key/index.m3u8"


def test_resolve_aaastreamer_ignores_non_station_page_paths(monkeypatch) -> None:
    opened: list[str] = []

    def fake_validate(url: str, *, field_name: str = "url") -> str:
        return url

    def fake_open(url: str, **_kwargs: object) -> _FakeResponse:
        opened.append(url)
        return _FakeResponse("")

    monkeypatch.setattr(aaastreamer, "validate_public_media_url", fake_validate)
    monkeypatch.setattr(aaastreamer, "open_validated_public_url", fake_open)

    assert (
        aaastreamer.resolve_aaastreamer_playback("https://radio.example.net/live.mp3")
        is None
    )
    assert opened == []


def test_resolve_aaastreamer_playback_reads_large_station_page(monkeypatch) -> None:
    station_url = "https://aaastreamer.devinecreations.net/s/main-stream"
    fallback_url = "https://aaastreamer.devinecreations.net/hls/live/key/index.m3u8"
    page = (
        (" " * 300_000)
        + '<video data-stream-id="str_123" '
        + f'data-current-playback-url="{fallback_url}"></video>'
    )

    def fake_validate(url: str, *, field_name: str = "url") -> str:
        return url

    def fake_open(url: str, **_kwargs: object) -> _FakeResponse:
        if url == station_url:
            return _FakeResponse(page)
        if url == "https://aaastreamer.devinecreations.net/api/streams/str_123":
            raise OSError("api unavailable")
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(aaastreamer, "validate_public_media_url", fake_validate)
    monkeypatch.setattr(aaastreamer, "open_validated_public_url", fake_open)

    resolved = aaastreamer.resolve_aaastreamer_playback(station_url)

    assert resolved is not None
    assert resolved.playback_url == fallback_url
