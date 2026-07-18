"""ElevenLabs TTS synthesis and same-origin voice audio file management.

Stores generated MP3 files under ``runtime/voice/`` (gitignored) and
returns safe same-origin URLs for the client to fetch.  Credentials are
read from environment variables and never logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("chgrid.voice")

# ---------------------------------------------------------------------------
# Environment variable names.  CHGRID_* overrides are useful for isolated
# deployments; the existing OpenClaw voice environment remains the fallback.
# ---------------------------------------------------------------------------
ENV_API_KEY = "CHGRID_VOICE_API_KEY"
ENV_VOICE_ID = "CHGRID_VOICE_ID"
FALLBACK_API_KEY_NAMES = ("ELEVENLABS_API_KEY",)
FALLBACK_VOICE_ID_NAMES = ("CLAWDIA_ELEVENLABS_VOICE_ID", "ELEVENLABS_VOICE_ID")

# Same-origin URL prefix the client expects to fetch audio from.
VOICE_URL_PREFIX = "/voice/"

# Maximum text length sent to the TTS endpoint (safety cap).
MAX_TEXT_LENGTH = 2000

# Sanitised filename pattern – hex + timestamp, no user content leaks.
_SAFE_NAME_RE = re.compile(r"[^a-z0-9._-]")

# Default sub-directory under the server runtime root.
DEFAULT_VOICE_DIR = Path("runtime/voice")


def _sanitize_filename(stem: str, ext: str = ".mp3") -> str:
    """Return a safe filesystem name from a raw stem string."""

    safe = _SAFE_NAME_RE.sub("", stem.lower())[:80]
    return (safe or "voice") + ext


def _voice_dir_for(runtime_root: Path | None) -> Path:
    """Resolve the voice audio output directory, creating it if needed."""

    directory = (runtime_root or Path.cwd()) / DEFAULT_VOICE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _resolve_credentials() -> tuple[str, str]:
    """Return (api_key, voice_id) from environment.  Raises ValueError when missing."""

    api_key = os.getenv(ENV_API_KEY, "").strip()
    if not api_key:
        api_key = next((os.getenv(name, "").strip() for name in FALLBACK_API_KEY_NAMES if os.getenv(name)), "")
    voice_id = os.getenv(ENV_VOICE_ID, "").strip()
    if not voice_id:
        voice_id = next((os.getenv(name, "").strip() for name in FALLBACK_VOICE_ID_NAMES if os.getenv(name)), "")
    if not api_key:
        raise ValueError(
            f"{ENV_API_KEY} environment variable is required for TTS synthesis."
        )
    if not voice_id:
        raise ValueError(
            f"{ENV_VOICE_ID} environment variable is required for TTS synthesis."
        )
    return api_key, voice_id


def _elevenlabs_rest_url(voice_id: str) -> str:
    """Return the ElevenLabs v1 text-to-speech REST endpoint for one voice."""

    return f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def synthesize_to_file(
    text: str,
    *,
    runtime_root: Path | None = None,
    api_key: str | None = None,
    voice_id: str | None = None,
) -> tuple[Path, str]:
    """Synthesize *text* to an MP3 file and return ``(path, same_origin_url)``.

    Raises ``ValueError`` on input problems and ``RuntimeError`` on network /
    API failures so callers can decide policy.

    Parameters
    ----------
    text:
        The spoken text.  Truncated to ``MAX_TEXT_LENGTH``.
    runtime_root:
        Base directory for the ``voice/`` sub-directory.  Defaults to cwd.
    api_key / voice_id:
        Optional overrides (primarily for testing).  When ``None`` the
        values are resolved from environment variables.
    """

    text = (text or "").strip()
    if not text:
        raise ValueError("Text must not be empty.")
    text = text[:MAX_TEXT_LENGTH]

    resolved_api_key = api_key or ""
    resolved_voice_id = voice_id or ""
    if not resolved_api_key or not resolved_voice_id:
        env_key, env_voice = _resolve_credentials()
        resolved_api_key = resolved_api_key or env_key
        resolved_voice_id = resolved_voice_id or env_voice

    # Build a deterministic-ish filename: timestamp + content hash
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    timestamp = int(time.time())
    filename = _sanitize_filename(f"agent_{timestamp}_{content_hash}", ".mp3")

    voice_dir = _voice_dir_for(runtime_root)
    output_path = voice_dir / filename

    url = _elevenlabs_rest_url(resolved_voice_id)
    payload = json.dumps(
        {
            "text": text,
            "model_id": os.getenv("CHGRID_VOICE_MODEL", "eleven_multilingual_v2"),
            "output_format": "mp3_44100_128",
        }
    ).encode("utf-8")

    request = Request(
        url,
        data=payload,
        headers={
            "xi-api-key": resolved_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )

    LOGGER.info("synthesizing %d chars of TTS audio", len(text))

    try:
        with urlopen(request, timeout=30) as response:
            audio_bytes = response.read()
    except Exception as exc:
        raise RuntimeError(f"TTS synthesis failed: {exc}") from exc

    if not audio_bytes:
        raise RuntimeError("TTS endpoint returned empty audio data.")

    output_path.write_bytes(audio_bytes)
    os.chmod(output_path, 0o644)

    public_url = VOICE_URL_PREFIX + filename
    LOGGER.info(
        "TTS audio saved %s (%d bytes) url=%s",
        output_path.name,
        len(audio_bytes),
        public_url,
    )
    return output_path, public_url


def voice_file_path(filename: str, *, runtime_root: Path | None = None) -> Path | None:
    """Resolve one voice filename to a safe filesystem path if it exists.

    The *filename* may or may not include an ``.mp3`` extension.  Only
    sanitisation characters are stripped – no extra extension is appended.
    """

    p = Path(filename)
    ext = p.suffix or ".mp3"
    stem = _SAFE_NAME_RE.sub("", p.stem.lower())[:80]
    safe = (stem or "voice") + ext
    candidate = _voice_dir_for(runtime_root) / safe
    if candidate.is_file():
        return candidate
    return None
