from __future__ import annotations

import socket

import pytest

from app.network_security import (
    normalize_origin,
    validate_media_reference,
    validate_public_media_url,
)


def test_normalize_origin_rejects_paths() -> None:
    with pytest.raises(ValueError):
        normalize_origin("https://example.com/chgrid")


def test_normalize_origin_normalizes_case_and_trailing_slash() -> None:
    assert normalize_origin("HTTPS://Example.COM:443/") == "https://example.com:443"


def test_validate_public_media_url_rejects_private_ip() -> None:
    with pytest.raises(ValueError):
        validate_public_media_url("http://127.0.0.1/audio")


def test_validate_public_media_url_resolves_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_getaddrinfo(host: str, port, type: int = 0):
        assert host == "radio.example.com"
        return [(socket.AF_INET, type, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    assert (
        validate_public_media_url("https://Radio.Example.com/live")
        == "https://radio.example.com/live"
    )


def test_validate_public_media_url_rejects_private_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_getaddrinfo(host: str, port, type: int = 0):
        assert host == "radio.example.com"
        return [(socket.AF_INET, type, 6, "", ("10.0.0.5", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError):
        validate_public_media_url("https://radio.example.com/live")


def test_validate_media_reference_allows_site_relative_path() -> None:
    assert (
        validate_media_reference("/chgrid/media_proxy.php?url=test")
        == "/chgrid/media_proxy.php?url=test"
    )
