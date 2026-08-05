"""Local Ollama game reasoning for Indiginous companions and game items."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from urllib.request import Request, urlopen
from typing import Any


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "qwen3:8b"
FALLBACK_MODEL = "qwen3:4b"
ALLOWED_ACTIONS = {"observe", "move", "speak", "interact", "use_item", "open_game", "wait"}


class GameAgentError(RuntimeError):
    """Raised when Ollama cannot provide a valid game decision."""


@dataclass(frozen=True)
class GameDecision:
    """Safe, model-generated intent for a caller to validate and execute."""

    say: str
    actions: tuple[dict[str, Any], ...]
    confidence: float
    needs_input: bool
    model: str


class OllamaGameAgent:
    """Ask a local Ollama model for structured game intent."""

    def __init__(self, *, endpoint: str | None = None, model: str | None = None) -> None:
        ollama_host = os.getenv("OLLAMA_HOST", "").strip().rstrip("/")
        host_endpoint = f"{ollama_host}/api/chat" if ollama_host else DEFAULT_OLLAMA_URL
        self.endpoint = endpoint or os.getenv("CHGRID_OLLAMA_URL", host_endpoint)
        self.model = model or os.getenv("CHGRID_OLLAMA_GAME_MODEL", DEFAULT_MODEL)
        self.fallback_model = os.getenv("CHGRID_OLLAMA_FALLBACK_MODEL", FALLBACK_MODEL)

    def decide(self, context: dict[str, Any]) -> GameDecision:
        """Return bounded game intent from the current world/game context."""

        payload = self._request(self.model, context)
        if payload is None and self.fallback_model != self.model:
            payload = self._request(self.fallback_model, context)
        if payload is None:
            raise GameAgentError("Ollama did not return a usable game decision")
        return self._parse(payload)

    def _request(self, model: str, context: dict[str, Any]) -> dict[str, Any] | None:
        system = (
            "You are the Indiginous game companion. Reason across accessible games, "
            "puzzles, arcade play, board play, exploration, and social world play. "
            "Return JSON only with keys say, actions, confidence, needs_input. "
            "Actions must be an array of objects whose type is one of: "
            "observe, move, speak, interact, use_item, open_game, wait. "
            "Never invent credentials, URLs, shell commands, or irreversible actions. "
            "When unsure, ask a short question and use needs_input=true."
        )
        body = json.dumps(
            {
                "model": model,
                "stream": False,
                "think": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "options": {"temperature": 0.2, "num_ctx": 8192},
            }
        ).encode()
        try:
            request = Request(self.endpoint, data=body, headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=45) as response:
                envelope = json.loads(response.read().decode("utf-8"))
            content = envelope.get("message", {}).get("content")
            return json.loads(content) if isinstance(content, str) else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _parse(self, raw: dict[str, Any]) -> GameDecision:
        say = str(raw.get("say", "")).strip()[:500]
        actions: list[dict[str, Any]] = []
        for action in raw.get("actions", []):
            if not isinstance(action, dict) or str(action.get("type", "")) not in ALLOWED_ACTIONS:
                continue
            actions.append({str(key): value for key, value in action.items() if str(key) != "command"})
            if len(actions) >= 8:
                break
        try:
            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
        return GameDecision(
            say=say,
            actions=tuple(actions),
            confidence=confidence,
            needs_input=bool(raw.get("needs_input", False)),
            model=self.model,
        )
