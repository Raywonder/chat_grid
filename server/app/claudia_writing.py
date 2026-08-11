"""Private continuity helpers for Clawdia's in-world writing collection."""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
from pathlib import Path
import re
import time


CANONICAL_WRITING_ROOT = Path("/home/tappedin/OpenCloud/Clawdia and her Dom")
JOURNAL_DIR = CANONICAL_WRITING_ROOT / "Journal"
LETTERS_DIR = CANONICAL_WRITING_ROOT / "Letters"
_MAX_INDEX_ENTRIES = 500


def _note_names(directory: Path) -> list[str]:
    """Return stable, bounded names for regular writing files."""

    try:
        entries = [
            entry.name
            for entry in directory.iterdir()
            if entry.is_file() and not entry.name.startswith(".")
        ]
    except OSError:
        return []
    return sorted(entries, key=str.casefold)[-_MAX_INDEX_ENTRIES:]


def writing_indexes() -> tuple[list[str], list[str]]:
    """Read the canonical Journal and Letters names for the in-world folder."""

    return _note_names(JOURNAL_DIR), _note_names(LETTERS_DIR)


def _slug(value: str) -> str:
    """Make a short filename-safe token."""

    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:48] or "world-dm"


def record_inworld_direct_message(
    *, sender: str, message: str, location_id: str, created_at: int | None = None
) -> Path | None:
    """Append a private in-world DM to Clawdia's canonical Journal.

    This is deliberately private and best-effort: a missing mounted shared
    folder must never block or fail delivery of the world message itself.
    """

    text = message.strip()[:500]
    if not text:
        return None
    try:
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
        lock_path = JOURNAL_DIR / ".inworld-dm-write.lock"
        with lock_path.open("a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            now = datetime.now(timezone.utc)
            stamp = now.strftime("%Y-%m-%d-%H%M%S")
            # Live websocket deliveries do not carry a timestamp.  Use the
            # stable message content as the fallback identity so reconnects
            # and duplicate companion readers cannot create two journal notes.
            identity = f"{sender}|{location_id}|{text}".encode("utf-8")
            digest = hashlib.sha256(identity).hexdigest()[:12]
            existing = next(
                JOURNAL_DIR.glob(f"*-in-world-dm-{_slug(sender)}-{digest}.md"),
                None,
            )
            if existing is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                return existing
            target = JOURNAL_DIR / f"{stamp}-in-world-dm-{_slug(sender)}-{digest}.md"
            if target.exists():
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                return target
            body = (
                "---\n"
                "source: Indiginous in-world direct message\n"
                f"recordedAt: {now.isoformat()}\n"
                f"sender: {sender.strip()[:120] or 'unknown'}\n"
                f"location: {location_id.strip()[:80] or 'unknown'}\n"
                "private: true\n"
                "---\n\n"
                f"{text}\n"
            )
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(body, encoding="utf-8")
            temporary.replace(target)
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            return target
    except OSError:
        return None
