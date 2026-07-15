"""AAAStreamer station-page helpers for radio tiles."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import json
import re
from urllib.error import URLError
from urllib.parse import urljoin, urlsplit

from ....network_security import open_validated_public_url, validate_public_media_url

STATION_PAGE_MAX_BYTES = 1_048_576
API_RESPONSE_MAX_BYTES = 262_144
_STREAM_ID_RE = re.compile(r'data-stream-id=["\']([^"\']+)["\']')
_PLAYBACK_URL_RE = re.compile(r'data-current-playback-url=["\']([^"\']+)["\']')


@dataclass(frozen=True)
class AaaStreamerPlayback:
    """Resolved current playback metadata for one public AAAStreamer station page."""

    title: str
    now_playing: str
    playback_url: str


def is_aaastreamer_station_url(url: str) -> bool:
    """Return whether a URL has the public AAAStreamer station-page shape.

    AAAStreamer installs can live on more than one hostname. The stable public
    station-page contract is the `/s/<slug>` path plus page/API metadata; the
    resolver confirms that contract by parsing the fetched page before returning
    a playback URL.
    """

    try:
        parts = urlsplit(validate_public_media_url(url, field_name="streamUrl"))
    except ValueError:
        return False
    path_parts = [part for part in parts.path.split("/") if part]
    return len(path_parts) == 2 and path_parts[0] == "s"


def _stream_id_from_html(html_text: str) -> str:
    """Extract the public stream id embedded in one AAAStreamer station page."""

    match = _STREAM_ID_RE.search(html_text)
    return unescape(match.group(1)).strip() if match else ""


def _playback_url_from_html(html_text: str, station_url: str) -> str:
    """Extract a fallback playback URL embedded in one AAAStreamer station page."""

    match = _PLAYBACK_URL_RE.search(html_text)
    if not match:
        return ""
    return validate_public_media_url(
        urljoin(station_url, unescape(match.group(1)).strip()),
        field_name="playbackUrl",
    )


def _playback_from_api_payload(
    payload: object, *, station_url: str
) -> AaaStreamerPlayback | None:
    """Build playback metadata from one AAAStreamer public API payload."""

    if not isinstance(payload, dict) or payload.get("success") is not True:
        return None
    stream = payload.get("stream")
    if not isinstance(stream, dict):
        return None
    playback_url = str(stream.get("playbackUrl") or stream.get("hlsUrl") or "").strip()
    if not playback_url:
        return None
    playback_url = validate_public_media_url(
        urljoin(station_url, playback_url), field_name="playbackUrl"
    )
    now_playing = stream.get("nowPlaying")
    now_title = ""
    if isinstance(now_playing, dict):
        now_title = str(
            now_playing.get("title") or now_playing.get("label") or ""
        ).strip()
    elif isinstance(now_playing, str):
        now_title = now_playing.strip()
    title = str(stream.get("title") or "").strip()
    return AaaStreamerPlayback(
        title=title[:160],
        now_playing=now_title[:200],
        playback_url=playback_url,
    )


def resolve_aaastreamer_playback(
    station_url: str, *, timeout: float = 6.0
) -> AaaStreamerPlayback | None:
    """Resolve a public AAAStreamer station page to its current playback URL."""

    if not is_aaastreamer_station_url(station_url):
        return None
    try:
        with open_validated_public_url(
            station_url,
            headers={"User-Agent": "ChatGrid"},
            timeout=timeout,
        ) as response:
            html_text = response.read(STATION_PAGE_MAX_BYTES).decode(
                "utf-8", errors="ignore"
            )
        stream_id = _stream_id_from_html(html_text)
        fallback_playback_url = _playback_url_from_html(html_text, station_url)
        if stream_id:
            api_url = urljoin(station_url, f"/api/streams/{stream_id}")
            try:
                with open_validated_public_url(
                    api_url,
                    headers={"Accept": "application/json", "User-Agent": "ChatGrid"},
                    timeout=timeout,
                ) as response:
                    payload = json.loads(
                        response.read(API_RESPONSE_MAX_BYTES).decode("utf-8")
                    )
                resolved = _playback_from_api_payload(payload, station_url=station_url)
                if resolved is not None:
                    return resolved
            except (OSError, URLError, ValueError, json.JSONDecodeError):
                pass
        if fallback_playback_url:
            return AaaStreamerPlayback(
                title="",
                now_playing="",
                playback_url=fallback_playback_url,
            )
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None
    return None
