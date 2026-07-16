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
    ambience_key: str
    ambience_name: str

    def as_dict(self) -> dict[str, str | int]:
        """Return the public metadata advertised to clients."""

        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "spawnX": self.spawn_x,
            "spawnY": self.spawn_y,
            "ambienceKey": self.ambience_key,
            "ambienceName": self.ambience_name,
        }


WORLD_LOCATIONS: tuple[WorldLocation, ...] = (
    WorldLocation(
        id="city",
        name="Main City",
        kind="city",
        description="The central plaza where new arrivals start and people gather.",
        spawn_x=20,
        spawn_y=20,
        ambience_key="city_plaza",
        ambience_name="City plaza",
    ),
    WorldLocation(
        id="forest",
        name="Forest",
        kind="forest",
        description="A quieter wooded grid for slower chats, wandering, and ambient items.",
        spawn_x=12,
        spawn_y=28,
        ambience_key="forest_canopy",
        ambience_name="Forest canopy",
    ),
    WorldLocation(
        id="town",
        name="Town",
        kind="town",
        description="A small neighborhood square for casual rooms and local meetups.",
        spawn_x=18,
        spawn_y=18,
        ambience_key="town_square",
        ambience_name="Town square",
    ),
    WorldLocation(
        id="town_cafe",
        name="Town Square Café",
        kind="cafe",
        description=(
            "A public café off Town Square with accessible tables, chairs, "
            "counters, and a live FIFA World Cup score board in the TV corner."
        ),
        spawn_x=20,
        spawn_y=22,
        ambience_key="town_cafe",
        ambience_name="Café conversation and soft kitchen clatter",
    ),
    WorldLocation(
        id="arcade",
        name="Arcade",
        kind="arcade",
        description="A playful game room for Moonstep Runner and future playable experiments.",
        spawn_x=20,
        spawn_y=20,
        ambience_key="arcade_glow",
        ambience_name="Arcade glow",
    ),
    WorldLocation(
        id="offices",
        name="Offices",
        kind="offices",
        description="Work rooms for support, planning, project chats, and focused sessions.",
        spawn_x=8,
        spawn_y=32,
        ambience_key="office_focus",
        ambience_name="Office focus",
    ),
    WorldLocation(
        id="ecrypto_bank_lobby",
        name="eCrypto Bank Lobby",
        kind="bank",
        description=(
            "A walk-in eCrypto bank interior where users and agents can gather, "
            "check wallet links, and make modeled test-chain transactions."
        ),
        spawn_x=20,
        spawn_y=22,
        ambience_key="office_focus",
        ambience_name="Quiet bank lobby",
    ),
    WorldLocation(
        id="houses",
        name="Houses",
        kind="houses",
        description=(
            "A neighborhood grid where each house is one front-door item with "
            "its connected rooms and personal spaces inside."
        ),
        spawn_x=30,
        spawn_y=12,
        ambience_key="neighborhood_evening",
        ambience_name="Neighborhood evening",
    ),
    WorldLocation(
        id="raywonder_house_entry",
        name="Raywonder House Entry",
        kind="house",
        description="The front entry inside the Raywonder house, with doors leading deeper in.",
        spawn_x=20,
        spawn_y=20,
        ambience_key="front_entry",
        ambience_name="Front entry",
    ),
    WorldLocation(
        id="raywonder_house_living_room",
        name="Raywonder Living Room",
        kind="room",
        description="A warm living room for relaxed conversation and nearby guests.",
        spawn_x=18,
        spawn_y=20,
        ambience_key="living_room_warmth",
        ambience_name="Living room warmth",
    ),
    WorldLocation(
        id="raywonder_house_studio",
        name="Raywonder Studio",
        kind="room",
        description=(
            "A project studio for music, accessibility work, audio tests, "
            "and creative tools."
        ),
        spawn_x=22,
        spawn_y=20,
        ambience_key="studio_current",
        ambience_name="Studio current",
    ),
    WorldLocation(
        id="raywonder_house_kitchen",
        name="Raywonder Kitchen",
        kind="room",
        description="A kitchen room for casual hangouts and domestic side chatter.",
        spawn_x=20,
        spawn_y=23,
        ambience_key="kitchen_soft_clatter",
        ambience_name="Kitchen soft clatter",
    ),
    WorldLocation(
        id="raywonder_house_bedroom",
        name="Raywonder Bedroom",
        kind="room",
        description="A quieter private room. The door can stay locked unless invited.",
        spawn_x=20,
        spawn_y=18,
        ambience_key="bedroom_quiet",
        ambience_name="Bedroom quiet",
    ),
    WorldLocation(
        id="raywonder_house_relaxation_room",
        name="Raywonder Relaxation Room",
        kind="room",
        description=(
            "A calm room for ocean sounds, relaxation tracks, meditation audio, "
            "and quiet radio listening."
        ),
        spawn_x=20,
        spawn_y=20,
        ambience_key="relaxation_ocean",
        ambience_name="Relaxation ocean",
    ),
)

WORLD_LOCATION_BY_ID = {location.id: location for location in WORLD_LOCATIONS}


def is_known_location_id(value: object) -> bool:
    """Return whether a value names a built-in world location."""

    candidate = str(value or "").strip().casefold()
    if candidate in WORLD_LOCATION_BY_ID:
        return True
    return any(candidate == location.name.casefold() for location in WORLD_LOCATIONS)


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
