"""Server-only ntfy delivery for opted-in Endiginous identities."""

from __future__ import annotations

import base64
import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LOGGER = logging.getLogger("chgrid.server.ntfy")
TOPIC_PATTERN = re.compile(r"^chatgrid-user-[a-f0-9]{32}$")


class NtfyPublisher:
    """Publish bounded notification payloads without exposing credentials to clients."""

    def __init__(self, *, base_url: str, username: str, password: str) -> None:
        """Initialize from deployment secrets; blank values disable publishing."""

        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    @property
    def configured(self) -> bool:
        """Return whether all required deployment values are present."""

        return bool(self.base_url and self.username and self.password)

    def publish(self, *, topic: str, title: str, message: str, click: str = "") -> bool:
        """Publish one notification to a validated private identity topic."""

        if not self.configured or not TOPIC_PATTERN.fullmatch(topic):
            return False
        payload: dict[str, str] = {
            "topic": topic,
            "title": str(title).strip()[:120] or "Endiginous notification",
            "message": str(message).strip()[:500] or "New Endiginous notification",
        }
        if click.startswith("https://"):
            payload["click"] = click
        credential = base64.b64encode(
            f"{self.username}:{self.password}".encode("utf-8")
        ).decode("ascii")
        request = Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Basic {credential}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=4) as response:
                return 200 <= int(response.status) < 300
        except (HTTPError, URLError, TimeoutError, OSError):
            LOGGER.warning("ntfy publish failed topic_prefix=chatgrid-user status=delivery_error")
            return False
