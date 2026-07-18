"""Item persistence, hydration, and local mutation helpers."""

from __future__ import annotations

import json
import logging
import time
import uuid
from copy import deepcopy
from pathlib import Path
from .client import ClientConnection
from .item_catalog import get_item_definition
from .models import PersistedWorldItem, WorldItem
from .seed_items import ensure_builtin_items

LOGGER = logging.getLogger("chgrid.server")


class ItemService:
    """Owns world-item storage, lifecycle, and persistence to disk."""

    def __init__(
        self, state_file: Path | None = None, *, seed_builtin_items: bool = False
    ):
        """Create service and eagerly load persisted state when configured."""

        self.state_file = state_file
        self.piano_songs_file = (
            state_file.with_name("piano_songs.json") if state_file else None
        )
        self.items: dict[str, WorldItem] = {}
        self.piano_songs: dict[str, dict] = {}
        self.load_state()
        if seed_builtin_items:
            changed = self.ensure_builtin_items()
            if changed:
                LOGGER.info("seeded or updated %d built-in world items", len(changed))
                self.save_state()
        self.load_piano_songs()

    @staticmethod
    def now_ms() -> int:
        """Return current Unix time in milliseconds."""

        return int(time.time() * 1000)

    def default_item(self, client: ClientConnection, item_type: str) -> WorldItem:
        """Create a new server-authoritative item at the caller's position."""

        # The add menu exposes this as a first-class choice, but it remains a
        # house_object at runtime so all existing remote, carrying, transfer,
        # and item-management behavior stays shared and compatible.
        runtime_item_type = "house_object" if item_type == "radio_remote" else item_type
        item_def = get_item_definition(runtime_item_type)
        now = self.now_ms()
        actor_id = client.user_id or client.id
        actor_name = client.username or client.nickname or actor_id
        params = deepcopy(item_def.default_params)
        title = item_def.default_title
        if item_type == "radio_remote":
            title = "Universal radio remote"
            params.update(
                {
                    "objectKind": "remote",
                    "placement": "table",
                    "description": "A universal radio remote for nearby and linked radios.",
                    "replacementHint": "A programmable universal radio remote.",
                    "remoteControlLinkedRadios": True,
                    "remoteControlLinkedTvs": False,
                }
            )
        return WorldItem(
            id=str(uuid.uuid4()),
            type=runtime_item_type,
            title=title,
            locationId=client.location_id,
            x=client.x,
            y=client.y,
            createdBy=actor_id,
            createdByName=actor_name,
            updatedBy=actor_id,
            updatedByName=actor_name,
            createdAt=now,
            updatedAt=now,
            version=1,
            capabilities=list(item_def.capabilities),
            useSound=item_def.use_sound,
            emitSound=item_def.emit_sound,
            params=params,
            carrierId=None,
        )

    def ensure_builtin_items(self) -> list[WorldItem]:
        """Insert/update built-in world items and return changed items."""

        return ensure_builtin_items(self.items, now_ms=self.now_ms())

    def add_item(self, item: WorldItem) -> None:
        """Insert or replace an item in in-memory state."""

        self.items[item.id] = item

    def remove_item(self, item_id: str) -> None:
        """Remove an item by id when present."""

        if item_id in self.items:
            del self.items[item_id]

    def find_carried_item(self, client_id: str) -> WorldItem | None:
        """Return the currently carried item for a client, if any."""

        for item in self.items.values():
            if item.carrierId == client_id:
                return item
        return None

    def carried_items_for_client(self, client_id: str) -> list[WorldItem]:
        """Return all items currently carried by a client."""

        return [item for item in self.items.values() if item.carrierId == client_id]

    @staticmethod
    def _clean_group_value(value: object) -> str:
        """Return a normalized item relationship key."""

        if not isinstance(value, str):
            return ""
        return value.strip()

    @classmethod
    def assembly_key_for_item(cls, item: WorldItem) -> str:
        """Return the key that makes an item move with linked parts."""

        explicit_key = cls._clean_group_value(item.params.get("assemblyId"))
        if explicit_key:
            return f"assembly:{item.locationId}:{explicit_key}"

        if item.type == "radio_station":
            media_group = cls._clean_group_value(item.params.get("linkedMediaGroup"))
            if media_group:
                return f"radio:{item.locationId}:{media_group}"

        return ""

    def linked_assembly_for_item(self, root: WorldItem) -> list[WorldItem]:
        """Return same-location items that should relocate with the root item."""

        assembly_key = self.assembly_key_for_item(root)
        if not assembly_key:
            return [root]

        linked = [
            item
            for item in self.items.values()
            if item.locationId == root.locationId
            and self.assembly_key_for_item(item) == assembly_key
        ]
        linked.sort(key=lambda item: (item.id != root.id, item.id))
        return linked or [root]

    def items_on_square(self, x: int, y: int) -> list[WorldItem]:
        """Return non-carried items occupying a specific world coordinate."""

        return [
            item
            for item in self.items.values()
            if item.carrierId is None and item.x == x and item.y == y
        ]

    def drop_carried_items_for_disconnect(
        self, client: ClientConnection
    ) -> list[WorldItem]:
        """Drop all items carried by a disconnected client onto their last tile."""

        changed: list[WorldItem] = []
        for item in self.items.values():
            if item.carrierId == client.id:
                item.carrierId = None
                item.x = client.x
                item.y = client.y
                item.updatedAt = self.now_ms()
                item.updatedBy = "system"
                item.updatedByName = "system"
                changed.append(item)
        return changed

    def recover_stale_carried_items(
        self, active_client_ids: set[str] | None = None
    ) -> list[WorldItem]:
        """Clear carrier ids that do not belong to currently connected clients."""

        active = active_client_ids or set()
        changed: list[WorldItem] = []
        for item in self.items.values():
            if item.carrierId is None or item.carrierId in active:
                continue
            item.carrierId = None
            item.updatedAt = self.now_ms()
            item.updatedBy = "system"
            item.updatedByName = "system"
            changed.append(item)
        return changed

    def load_state(self) -> None:
        """Load persisted item instances and rehydrate global fields from catalog."""

        if not self.state_file:
            return
        try:
            if not self.state_file.exists():
                return
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return
            loaded: dict[str, WorldItem] = {}
            for entry in raw:
                persisted = PersistedWorldItem.model_validate(entry)
                item_def = get_item_definition(persisted.type)
                item = WorldItem(
                    id=persisted.id,
                    type=persisted.type,
                    title=persisted.title,
                    locationId=persisted.locationId,
                    x=persisted.x,
                    y=persisted.y,
                    createdBy=persisted.createdBy,
                    createdByName=persisted.createdByName or persisted.createdBy,
                    updatedBy=persisted.updatedBy or persisted.createdBy,
                    updatedByName=persisted.updatedByName
                    or persisted.updatedBy
                    or persisted.createdBy,
                    createdAt=persisted.createdAt,
                    updatedAt=persisted.updatedAt,
                    version=persisted.version,
                    capabilities=list(item_def.capabilities),
                    useSound=item_def.use_sound,
                    emitSound=item_def.emit_sound,
                    params=persisted.params,
                    carrierId=persisted.carrierId,
                )
                loaded[item.id] = item
            self.items = loaded
            LOGGER.info(
                "loaded %d persisted items from %s", len(self.items), self.state_file
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to load persisted item state from %s: %s", self.state_file, exc
            )

    def load_piano_songs(self) -> None:
        """Load persisted piano song registry used by piano items."""

        if not self.piano_songs_file:
            return
        try:
            if not self.piano_songs_file.exists():
                return
            raw = json.loads(self.piano_songs_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            loaded: dict[str, dict] = {}
            for song_id, payload in raw.items():
                if not isinstance(song_id, str) or not song_id.strip():
                    continue
                if not isinstance(payload, dict):
                    continue
                loaded[song_id] = payload
            self.piano_songs = loaded
            LOGGER.info(
                "loaded %d persisted piano songs from %s",
                len(self.piano_songs),
                self.piano_songs_file,
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to load piano songs from %s: %s", self.piano_songs_file, exc
            )

    def save_state(self) -> None:
        """Persist instance-only item data to configured state file."""

        if not self.state_file:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = [
                PersistedWorldItem(
                    id=item.id,
                    type=item.type,
                    title=item.title,
                    locationId=item.locationId,
                    x=item.x,
                    y=item.y,
                    createdBy=item.createdBy,
                    createdByName=item.createdByName,
                    updatedBy=item.updatedBy,
                    updatedByName=item.updatedByName,
                    createdAt=item.createdAt,
                    updatedAt=item.updatedAt,
                    version=item.version,
                    params=item.params,
                    carrierId=item.carrierId,
                ).model_dump(exclude_none=True)
                for item in self.items.values()
            ]
            self.state_file.write_text(
                json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
                encoding="utf-8",
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to persist item state to %s: %s", self.state_file, exc
            )

    def save_piano_songs(self) -> None:
        """Persist compact piano song registry payload to configured storage file."""

        if not self.piano_songs_file:
            return
        try:
            self.piano_songs_file.parent.mkdir(parents=True, exist_ok=True)
            self.piano_songs_file.write_text(
                json.dumps(self.piano_songs, ensure_ascii=True, separators=(",", ":")),
                encoding="utf-8",
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to persist piano songs to %s: %s", self.piano_songs_file, exc
            )
