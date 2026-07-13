"""Server-owned world location definitions and lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_LOCATION_ID = "city"


@dataclass(frozen=True)
class WorldLocation:
    """One travel destination/room in the larger Chat Grid world."""

    id: str
    name: str
    kind: str
    description: str
    spawn_x: int
    spawn_y: int

    def as_dict(self) -> dict[str, str | int]:
        """Return the public metadata advertised to clients."""

        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "spawnX": self.spawn_x,
            "spawnY": self.spawn_y,
        }


WORLD_LOCATIONS: tuple[WorldLocation, ...] = (
    WorldLocation(
        id="city",
        name="Main City",
        kind="city",
        description="The central plaza where new arrivals start and people gather.",
        spawn_x=20,
        spawn_y=20,
    ),
    WorldLocation(
        id="forest",
        name="Forest",
        kind="forest",
        description="A quieter wooded grid for slower chats, wandering, and ambient items.",
        spawn_x=12,
        spawn_y=28,
    ),
    WorldLocation(
        id="town",
        name="Town",
        kind="town",
        description="A small neighborhood square for casual rooms and local meetups.",
        spawn_x=18,
        spawn_y=18,
    ),
    WorldLocation(
        id="arcade",
        name="Arcade",
        kind="arcade",
        description="A playful game room for Moonstep Runner and future playable experiments.",
        spawn_x=20,
        spawn_y=20,
    ),
    WorldLocation(
        id="offices",
        name="Offices",
        kind="offices",
        description="Work rooms for support, planning, project chats, and focused sessions.",
        spawn_x=8,
        spawn_y=32,
    ),
    WorldLocation(
        id="houses",
        name="Houses",
        kind="houses",
        description="Private-feeling home grids for smaller groups and personal spaces.",
        spawn_x=30,
        spawn_y=12,
    ),
)

WORLD_LOCATION_BY_ID = {location.id: location for location in WORLD_LOCATIONS}


def normalize_location_id(value: object) -> str:
    """Return a valid location id, falling back to the main city."""

    candidate = str(value or "").strip().casefold()
    if candidate in WORLD_LOCATION_BY_ID:
        return candidate
    for location in WORLD_LOCATIONS:
        if candidate == location.name.casefold():
            return location.id
    return DEFAULT_LOCATION_ID


def get_location(value: object) -> WorldLocation:
    """Resolve a location by id/name, returning the default city when unknown."""

    return WORLD_LOCATION_BY_ID[normalize_location_id(value)]


def location_options_text() -> str:
    """Return a concise human-readable list of available travel destinations."""

    return ", ".join(f"{location.id} ({location.name})" for location in WORLD_LOCATIONS)
