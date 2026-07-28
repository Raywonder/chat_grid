"""Private, bounded activity continuity for the Indiginous companion.

The ledger is intentionally a summary stream rather than a transcript.  It
keeps enough durable state to recover after reconnects or restarts while
leaving ordinary public room chatter transient and out of private notes.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


MAX_ENTRIES = 500
MAX_BYTES = 2 * 1024 * 1024


class ActivityLedger:
    """Append-only bounded event ledger with stable duplicate suppression."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._event_ids: deque[str] = deque(maxlen=MAX_ENTRIES)
        self._load_ids()

    def _load_ids(self) -> None:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-MAX_ENTRIES:]
        except (FileNotFoundError, OSError):
            return
        for line in lines:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_id = str(value.get("eventId") or "").strip()
            if event_id:
                self._event_ids.append(event_id)

    def record(self, event_type: str, *, event_id: str = "", **details: Any) -> bool:
        """Record one summary event, returning false when it is a duplicate."""

        normalized_type = str(event_type).strip().lower().replace(" ", "_")[:80]
        stable_id = event_id.strip() or self._make_id(normalized_type, details)
        if stable_id in self._event_ids:
            return False
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "eventId": stable_id,
            "type": normalized_type,
            "recordedAt": now,
            **self._safe_details(details),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._event_ids.append(stable_id)
        self._trim()
        return True

    @staticmethod
    def _make_id(event_type: str, details: dict[str, Any]) -> str:
        payload = json.dumps(
            {"type": event_type, **details},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _safe_details(details: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in details.items():
            if value is None:
                continue
            if isinstance(value, bool | int | float):
                safe[key] = value
            elif isinstance(value, str):
                safe[key] = value[:240]
            else:
                safe[key] = str(value)[:240]
        return safe

    def _trim(self) -> None:
        """Keep the ledger recoverable and small without a destructive sweep."""

        try:
            if self.path.stat().st_size <= MAX_BYTES:
                return
            lines = self.path.read_text(encoding="utf-8").splitlines()[-MAX_ENTRIES:]
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            # Continuity is best-effort and must never interrupt the live world.
            return
