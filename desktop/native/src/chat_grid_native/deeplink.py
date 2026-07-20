"""Validation for browser-to-desktop Endiginous handoff links."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .config import DEFAULT_URL


def resolve_launch_url(arguments: list[str], default_url: str = DEFAULT_URL) -> str:
    """Return an approved Endiginous URL from command-line protocol arguments."""
    links = [value for value in arguments if value.lower().startswith("chatgrid://")]
    if not links:
        return default_url
    outer = urlparse(links[-1])
    if outer.scheme.lower() != "chatgrid" or outer.netloc.lower() != "connect":
        return default_url
    candidate = parse_qs(outer.query).get("url", [default_url])[0]
    parsed = urlparse(candidate)
    if parsed.scheme.lower() != "https" or parsed.hostname != "blind.software":
        return default_url
    if not (parsed.path == "/chatgrid" or parsed.path.startswith("/chatgrid/")):
        return default_url
    return candidate
