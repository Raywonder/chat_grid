"""Bounded local-model autonomy for Indiginous house keepers.

The model is an optional suggestion engine.  It never receives credentials,
private chat history, or arbitrary tool access, and its output is accepted
only when it matches the small action vocabulary below.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

LOGGER = logging.getLogger(__name__)

ALLOWED_ACTIONS = {"wait", "move", "inspect", "say", "task"}
DEFAULT_MODEL_URL = "http://127.0.0.1:11434/api/chat"
MAX_PROMPT_CHARS = 4000
MAX_SAY_CHARS = 240
MAX_TASK_CHARS = 240


@dataclass(frozen=True)
class KeeperDecision:
    """A validated, safe action suggested for one keeper cycle."""

    action: str = "inspect"
    message: str = ""
    task: str = ""


def _clean_text(value: object, limit: int) -> str:
    """Return bounded single-line text suitable for world state."""

    return " ".join(str(value or "").split())[:limit]


def parse_decision(payload: object) -> KeeperDecision:
    """Validate model JSON and fall back to a harmless inspection."""

    if not isinstance(payload, dict):
        return KeeperDecision()
    action = str(payload.get("action") or "inspect").strip().casefold()
    if action not in ALLOWED_ACTIONS:
        return KeeperDecision()
    return KeeperDecision(
        action=action,
        message=_clean_text(payload.get("message"), MAX_SAY_CHARS),
        task=_clean_text(payload.get("task"), MAX_TASK_CHARS),
    )


def build_prompt(snapshot: dict[str, Any]) -> str:
    """Build a privacy-bounded prompt from an in-world snapshot."""

    body = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    body = body[:MAX_PROMPT_CHARS]
    return (
        "You are a small, kind housekeeper NPC in Indiginous. "
        "Choose exactly one safe action and return JSON only. "
        "Allowed actions: wait, move, inspect, say, task. "
        "Never request credentials, outside messages, shell commands, purchases, "
        "or physical-world actions. Use task only for a useful in-world idea "
        "that a larger agent can review later. JSON keys: action, message, task.\n"
        f"World snapshot: {body}"
    )


def load_reviewed_discoveries(path: str, *, limit: int = 12) -> list[str]:
    """Load reviewed web-discovery ideas from a local JSON handoff file.

    A separate web-capable worker may write this file.  The world server only
    consumes short task text; it never follows URLs or executes the ideas.
    """

    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as handle:  # noqa: PTH123
            payload = json.load(handle)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        payload = payload.get("discoveries", [])
    if not isinstance(payload, list):
        return []
    ideas: list[str] = []
    for value in payload:
        text = _clean_text(value, MAX_TASK_CHARS)
        if text and text not in ideas:
            ideas.append(text)
    return ideas[:limit]


def _request_json(url: str, model: str, prompt: str, timeout: float) -> object:
    """Call a local Ollama-compatible endpoint without exposing secrets."""

    request = urllib.request.Request(
        url,
        data=json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        response_payload = json.loads(response.read().decode("utf-8"))
    content = response_payload.get("message", {}).get("content", "")
    try:
        return json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _is_loopback_url(url: str) -> bool:
    """Permit only local HTTP model endpoints."""

    parsed = urlsplit(url)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


async def suggest_local_decision(
    snapshot: dict[str, Any],
    *,
    url: str = DEFAULT_MODEL_URL,
    model: str = "llama3.2:3b",
    timeout: float = 2.5,
) -> KeeperDecision:
    """Ask an optional local model without blocking the event loop."""

    if not _is_loopback_url(url):
        LOGGER.warning("refusing non-loopback housekeeper model URL")
        return KeeperDecision()
    try:
        payload = await asyncio.wait_for(
            asyncio.to_thread(_request_json, url, model, build_prompt(snapshot), timeout),
            timeout=timeout + 0.25,
        )
    except (OSError, TimeoutError, asyncio.TimeoutError, urllib.error.URLError) as exc:
        LOGGER.debug("local housekeeper model unavailable: %s", exc)
        return KeeperDecision()
    return parse_decision(payload)
