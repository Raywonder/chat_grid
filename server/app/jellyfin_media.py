"""Jellyfin access and playback policy for Indiginous in-world media.

The world authenticates the person once, then applies a small, server-owned
media policy to every Jellyfin request.  A shared Jellyfin service account is
the default so the feature works without creating an account for every world
user.  Optional per-user provisioning can be enabled later without changing
the world protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from typing import Any
from urllib.parse import quote

LOGGER = logging.getLogger("chgrid.server.jellyfin")


@dataclass(frozen=True)
class JellyfinMediaAccess:
    """The media capabilities visible to one authenticated world user."""

    enabled: bool
    mode: str
    can_play_tv: bool
    can_play_radio: bool
    libraries: tuple[str, ...]
    universal_remotes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe capability summary for the client."""

        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "canPlayTv": self.can_play_tv,
            "canPlayRadio": self.can_play_radio,
            "libraries": list(self.libraries),
            "universalRemotes": list(self.universal_remotes),
        }


class JellyfinMediaService:
    """Resolve per-user Jellyfin policy without exposing Jellyfin credentials."""

    def __init__(self) -> None:
        self.base_url = os.getenv("CHGRID_JELLYFIN_URL", "").strip().rstrip("/")
        self.shared_user = os.getenv("CHGRID_JELLYFIN_USER", "indiginous-media").strip()
        self.shared_token = os.getenv("CHGRID_JELLYFIN_TOKEN", "").strip()
        self.provision_users = os.getenv("CHGRID_JELLYFIN_PROVISION_USERS", "0").strip().lower() in {
            "1", "true", "yes", "on"
        }
        self._policies = self._load_policies()

    @property
    def configured(self) -> bool:
        """Return whether Jellyfin playback is configured for this server."""

        return bool(self.base_url and self.shared_token)

    def _load_policies(self) -> dict[str, JellyfinMediaAccess]:
        raw = os.getenv("CHGRID_JELLYFIN_POLICIES", "").strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.error("Invalid CHGRID_JELLYFIN_POLICIES; using deny-by-default")
            return {}
        result: dict[str, JellyfinMediaAccess] = {}
        if not isinstance(payload, dict):
            return result
        for username, value in payload.items():
            if not isinstance(value, dict):
                continue
            libraries = tuple(str(item).strip() for item in value.get("libraries", []) if str(item).strip())
            remotes = tuple(str(item).strip() for item in value.get("universalRemotes", []) if str(item).strip())
            result[str(username).strip().casefold()] = JellyfinMediaAccess(
                enabled=bool(value.get("enabled", True)),
                mode=str(value.get("mode", "shared")).strip().lower() or "shared",
                can_play_tv=bool(value.get("canPlayTv", False)),
                can_play_radio=bool(value.get("canPlayRadio", False)),
                libraries=libraries,
                universal_remotes=remotes,
            )
        return result

    def access_for(self, username: str | None) -> JellyfinMediaAccess:
        """Return a user's policy, denying media unless explicitly allowed."""

        key = str(username or "").strip().casefold()
        configured = self._policies.get(key)
        if configured is not None:
            return configured
        return JellyfinMediaAccess(
            enabled=False,
            mode="shared",
            can_play_tv=False,
            can_play_radio=False,
            libraries=(),
            universal_remotes=(),
        )

    def playback_url(self, *, username: str | None, media_kind: str, item_id: str) -> str | None:
        """Return a short-lived server-side playback route for an allowed item.

        The route contains no Jellyfin token.  The actual proxy endpoint can
        exchange the server-held token when it is added to the deployment.
        """

        access = self.access_for(username)
        kind = media_kind.strip().lower()
        allowed = (kind == "tv" and access.can_play_tv) or (kind == "radio" and access.can_play_radio)
        if not self.configured or not access.enabled or not allowed or not item_id.strip():
            return None
        return f"{self.base_url}/Indiginous/Playback/{quote(item_id.strip(), safe='')}/{kind}"

    def provisioning_mode(self) -> str:
        """Describe whether this deployment uses shared or per-user accounts."""

        return "provisioned" if self.provision_users else "shared"

    @staticmethod
    def playback_plan(metadata: object) -> list[dict[str, Any]]:
        """Build a small sequential plan for a channel or programme.

        Jellyfin remains the source of truth for the media URLs.  Indiginous
        accepts optional ``intro``, ``break``, and ``chapters`` metadata so a
        TV can present a programme like a real channel: intro, content, then
        marked sections or a break before the next item.  Both ``Intros`` and
        ``intros`` folder labels are accepted by the catalogue importer.
        """

        if not isinstance(metadata, dict):
            return []
        plan: list[dict[str, Any]] = []
        for key, kind in (("intro", "intro"), ("Intros", "intro"), ("intros", "intro"), ("mediaUrl", "content"), ("break", "break"), ("Breaks", "break"), ("breaks", "break")):
            value = metadata.get(key)
            values = value if isinstance(value, list) else [value]
            for entry in values:
                if isinstance(entry, dict):
                    url = str(entry.get("url") or entry.get("playbackUrl") or "").strip()
                    title = str(entry.get("title") or kind.title()).strip()
                else:
                    url = str(entry or "").strip()
                    title = kind.title()
                if url:
                    plan.append({"kind": kind, "url": url, "title": title})
        chapters = metadata.get("chapters")
        if isinstance(chapters, list):
            plan.append({
                "kind": "chapters",
                "chapters": [
                    entry for entry in chapters
                    if isinstance(entry, dict) and str(entry.get("title") or "").strip()
                ],
            })
        return plan
