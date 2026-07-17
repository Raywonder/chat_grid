#!/usr/bin/env python3
"""Generate the fixed Chat Grid alarm-system voice prompt library."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path


ENV_FILE = Path("/etc/asterisk/clawdia-pbx.env")
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "client/public/sounds/alarm"
PROMPTS = {
    "setup-required.mp3": "Welcome. This alarm system needs first-use access setup by its owner.",
    "setup-complete.mp3": "Access setup complete. Your private security settings are now active.",
    "access-granted.mp3": "Identity confirmed. Access granted.",
    "access-denied.mp3": "Access denied. Please wait outside for an authorized resident.",
    "alarm-triggered.mp3": "Security alert. A visitor is waiting at the protected entrance.",
}


def load_env() -> dict[str, str]:
    """Read the private voice configuration without logging its values."""

    values: dict[str, str] = {}
    for raw in ENV_FILE.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    """Generate every voice prompt using the configured Claudia voice."""

    env = load_env()
    api_key = env.get("ELEVENLABS_API_KEY", "")
    voice_id = env.get("CLAWDIA_ELEVENLABS_VOICE_ID") or env.get("ELEVENLABS_VOICE_ID", "")
    if not api_key or not voice_id:
        raise RuntimeError("Configured ElevenLabs key and Claudia voice are required")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, text in PROMPTS.items():
        payload = {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {
                "stability": 0.67,
                "similarity_boost": 0.84,
                "style": 0.18,
                "use_speaker_boost": True,
            },
        }
        request = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            audio = response.read()
        if len(audio) < 1_000:
            raise RuntimeError(f"Generated prompt is unexpectedly small: {filename}")
        (OUTPUT_DIR / filename).write_bytes(audio)
    print(f"generated {len(PROMPTS)} alarm voice prompts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
