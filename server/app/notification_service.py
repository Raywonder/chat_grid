"""Runtime notification storage for Chat Grid account/admin events."""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid


@dataclass
class NotificationRecord:
    """One notification visible to a user or to admins."""

    id: str
    created_at_ms: int
    kind: str
    title: str
    message: str
    target_user_id: str | None = None
    actor_user_id: str | None = None
    read_by: set[str] = field(default_factory=set)

    def is_read_for(self, user_id: str) -> bool:
        """Return whether the notification has been read by this user."""

        return user_id in self.read_by


class NotificationService:
    """Keeps bounded runtime notifications and per-user read state."""

    def __init__(self, *, max_records: int = 500) -> None:
        """Initialize an empty bounded notification store."""

        self.max_records = max(1, int(max_records))
        self._records: list[NotificationRecord] = []

    def add(
        self,
        *,
        now_ms: int,
        kind: str,
        title: str,
        message: str,
        target_user_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> NotificationRecord:
        """Append one notification and return it."""

        record = NotificationRecord(
            id=str(uuid.uuid4()),
            created_at_ms=now_ms,
            kind=str(kind).strip()[:64] or "general",
            title=str(title).strip()[:120] or "Notification",
            message=str(message).strip()[:500],
            target_user_id=(
                str(target_user_id).strip() or None
                if target_user_id is not None
                else None
            ),
            actor_user_id=(
                str(actor_user_id).strip() or None
                if actor_user_id is not None
                else None
            ),
        )
        self._records.append(record)
        if len(self._records) > self.max_records:
            self._records = self._records[-self.max_records :]
        return record

    def list_for_user(
        self, *, user_id: str, include_admin: bool = False, limit: int = 20
    ) -> list[NotificationRecord]:
        """Return newest notifications visible to one user."""

        normalized_user_id = str(user_id).strip()
        if not normalized_user_id:
            return []
        if include_admin:
            candidates = self._records
        else:
            candidates = [
                record
                for record in self._records
                if record.target_user_id == normalized_user_id
            ]
        max_items = max(1, min(int(limit), 100))
        return sorted(
            candidates, key=lambda record: record.created_at_ms, reverse=True
        )[:max_items]

    def mark_read(
        self,
        *,
        user_id: str,
        notification_id: str | None = None,
        include_admin: bool = False,
    ) -> int:
        """Mark one or more visible notifications as read for this user."""

        changed = 0
        normalized_user_id = str(user_id).strip()
        wanted_id = str(notification_id or "").strip()
        for record in self.list_for_user(
            user_id=normalized_user_id, include_admin=include_admin, limit=self.max_records
        ):
            if wanted_id and record.id != wanted_id:
                continue
            if normalized_user_id not in record.read_by:
                record.read_by.add(normalized_user_id)
                changed += 1
            if wanted_id:
                break
        return changed

    def unread_count(self, *, user_id: str, include_admin: bool = False) -> int:
        """Return unread visible notification count for one user."""

        normalized_user_id = str(user_id).strip()
        return sum(
            1
            for record in self.list_for_user(
                user_id=normalized_user_id,
                include_admin=include_admin,
                limit=self.max_records,
            )
            if not record.is_read_for(normalized_user_id)
        )
