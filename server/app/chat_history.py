"""Small durable chat history store for Endiginous room and direct messages."""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import threading
import time
from typing import Any


class ChatHistory:
    """Append-only, bounded history that survives client reloads and server restarts."""

    def __init__(self, path: Path, max_entries: int = 5000) -> None:
        self.path = path
        self.max_entries = max(100, max_entries)
        self._lock = threading.Lock()
        self._entries: deque[dict[str, Any]] = deque(maxlen=self.max_entries)
        self._load()

    def _load(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(entry, dict) and entry.get("kind") in {"public", "direct"}:
                        self._entries.append(entry)
        except FileNotFoundError:
            return

    def append(self, entry: dict[str, Any]) -> None:
        record = {**entry, "createdAt": int(entry.get("createdAt") or time.time() * 1000)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._entries.append(record)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    def public_for_location(self, location_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(entry)
                for entry in self._entries
                if entry.get("kind") == "public" and entry.get("locationId") == location_id
            ][-limit:]

    def direct_for_user(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(entry)
                for entry in self._entries
                if entry.get("kind") == "direct"
                and user_id in {entry.get("senderUserId"), entry.get("targetUserId")}
            ][-limit:]
