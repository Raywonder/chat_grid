"""Built-in service/station items for the default Chat Grid world."""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import uuid

from .item_catalog import get_item_definition
from .models import WorldItem


@dataclass(frozen=True)
class SeedItem:
    """One built-in item that should exist unless a matching user item exists."""

    type: str
    title: str
    location_id: str
    x: int
    y: int
    params: dict
    id: str = ""


BUILTIN_WORLD_ITEMS: tuple[SeedItem, ...] = (
    SeedItem(
        id="seed-city-soulfoodradio",
        type="radio_station",
        title="SoulFoodRadio",
        location_id="city",
        x=5,
        y=10,
        params={
            "streamUrl": "https://aaastreamer.devinecreations.net/s/soulfoodradio-media",
            "enabled": False,
        },
    ),
    SeedItem(
        id="seed-city-divinecreations-radio",
        type="radio_station",
        title="DivineCreations radio",
        location_id="city",
        x=7,
        y=12,
        params={
            "streamUrl": "https://aaastreamer.devinecreations.net/s/main-stream",
            "enabled": False,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-1",
        type="radio_station",
        title="ACB Media 1",
        location_id="city",
        x=3,
        y=6,
        params={
            "streamUrl": "https://streaming.live365.com/a11911",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-2",
        type="radio_station",
        title="ACB Media 2",
        location_id="city",
        x=5,
        y=6,
        params={
            "streamUrl": "https://streaming.live365.com/a27778",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-3",
        type="radio_station",
        title="ACB Media 3",
        location_id="city",
        x=7,
        y=6,
        params={
            "streamUrl": "https://streaming.live365.com/a17972",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-4",
        type="radio_station",
        title="ACB Media 4",
        location_id="city",
        x=9,
        y=6,
        params={
            "streamUrl": "https://streaming.live365.com/a89697",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-5",
        type="radio_station",
        title="ACB Media 5",
        location_id="city",
        x=11,
        y=6,
        params={
            "streamUrl": "https://streaming.live365.com/a46090",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-6",
        type="radio_station",
        title="ACB Media 6",
        location_id="city",
        x=3,
        y=8,
        params={
            "streamUrl": "https://streaming.live365.com/a36240",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-7",
        type="radio_station",
        title="ACB Media 7",
        location_id="city",
        x=5,
        y=8,
        params={
            "streamUrl": "https://streaming.live365.com/a95398",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-8",
        type="radio_station",
        title="ACB Media 8",
        location_id="city",
        x=7,
        y=8,
        params={
            "streamUrl": "https://streaming.live365.com/a18975",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-9",
        type="radio_station",
        title="ACB Media 9",
        location_id="city",
        x=9,
        y=8,
        params={
            "streamUrl": "https://streaming.live365.com/a44175",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-acb-media-10",
        type="radio_station",
        title="ACB Media 10",
        location_id="city",
        x=11,
        y=8,
        params={
            "streamUrl": "https://streaming.live365.com/a85327",
            "enabled": False,
            "mediaVolume": 50,
        },
    ),
    SeedItem(
        id="seed-city-aaastreamer",
        type="service_link",
        title="AAAStreamer",
        location_id="city",
        x=9,
        y=12,
        params={
            "serviceKind": "service",
            "url": "https://aaastreamer.devinecreations.net/",
            "description": "Streaming service hub for hosted stations and radio tools.",
            "launchMessage": "AAAStreamer service hub.",
        },
    ),
    SeedItem(
        id="seed-city-blindsoftware",
        type="service_link",
        title="blind.software",
        location_id="city",
        x=12,
        y=10,
        params={
            "serviceKind": "site",
            "url": "https://blind.software/",
            "description": "Catalog and community space for accessible software, downloads, media, repos, and account-tied help.",
        },
    ),
    SeedItem(
        id="seed-city-tappedin",
        type="service_link",
        title="tappedin.fm",
        location_id="city",
        x=14,
        y=10,
        params={
            "serviceKind": "site",
            "url": "https://tappedin.fm/",
            "description": "TappedIn home for shows, services, and project entry points.",
        },
    ),
    SeedItem(
        id="seed-town-tcast",
        type="service_link",
        title="tCast",
        location_id="town",
        x=18,
        y=15,
        params={
            "serviceKind": "app",
            "url": "https://tappedin.fm/tcast-support/",
            "description": "Podcast and media player app support entry for tCast.",
        },
    ),
    SeedItem(
        id="seed-town-bema",
        type="service_link",
        title="Bema Media Player",
        location_id="town",
        x=21,
        y=15,
        params={
            "serviceKind": "app",
            "url": "https://bemamediaplayer.app/",
            "description": "Media player app entry for Bema Media Player.",
        },
    ),
    SeedItem(
        id="seed-town-thrive",
        type="service_link",
        title="Thrive Messenger",
        location_id="town",
        x=18,
        y=20,
        params={
            "serviceKind": "app",
            "description": "Messenger and agent backchannel space for approved conversations and coordination.",
        },
    ),
    SeedItem(
        id="seed-offices-voicelink",
        type="service_link",
        title="VoiceLink",
        location_id="offices",
        x=8,
        y=28,
        params={
            "serviceKind": "app",
            "description": "Voice room and communication app work area.",
        },
    ),
    SeedItem(
        id="seed-offices-openlink",
        type="service_link",
        title="OpenLink",
        location_id="offices",
        x=10,
        y=28,
        params={
            "serviceKind": "tool",
            "description": "Remote support and control tool work area.",
        },
    ),
    SeedItem(
        id="seed-offices-openclaw",
        type="service_link",
        title="OpenClaw and Clawdia",
        location_id="offices",
        x=8,
        y=31,
        params={
            "serviceKind": "service",
            "description": "Agent coordination, memory, repair, and creative work area.",
        },
    ),
    SeedItem(
        id="seed-offices-flexpbx",
        type="service_link",
        title="FlexPBX",
        location_id="offices",
        x=10,
        y=31,
        params={
            "serviceKind": "service",
            "description": "Hosted PBX and call-flow service area.",
        },
    ),
    SeedItem(
        id="seed-houses-raywonder",
        type="service_link",
        title="Raywonder",
        location_id="houses",
        x=30,
        y=12,
        params={
            "serviceKind": "site",
            "url": "https://raywonderis.me/",
            "description": "Raywonder family site and personal project entry.",
        },
    ),
    SeedItem(
        id="seed-arcade-moonstep-runner",
        type="service_link",
        title="Moonstep Runner",
        location_id="arcade",
        x=20,
        y=18,
        params={
            "serviceKind": "game",
            "url": "https://blind.software/private/moonstep-28c93ae33fd0e29d/",
            "description": "Clawdia's moonlit browser runner with directional movement sounds, chorus mode, and generated music.",
            "launchMessage": "Moonstep Runner is ready to play.",
        },
    ),
    SeedItem(
        id="seed-arcade-future-games",
        type="service_link",
        title="Future games shelf",
        location_id="arcade",
        x=22,
        y=18,
        params={
            "serviceKind": "game",
            "description": "A placeholder shelf for future Chat Grid games and playful experiments.",
            "launchMessage": "Future games will appear here as they are added.",
        },
    ),
    SeedItem(
        id="seed-arcade-clawdia-toolkit",
        type="service_link",
        title="Clawdia's toolkit",
        location_id="arcade",
        x=20,
        y=21,
        params={
            "serviceKind": "tool",
            "description": "A shared bundle spot for useful Clawdia-made toys, helpers, sounds, and experiments other logged-in users can try.",
            "launchMessage": "Clawdia's shared toolkit is open for useful little experiments.",
        },
    ),
)


def _matching_seed_exists(items: dict[str, WorldItem], seed: SeedItem) -> bool:
    """Return true if this built-in seed is already represented."""

    if seed.id and seed.id in items:
        return True
    seed_title = seed.title.casefold()
    for item in items.values():
        if item.type != seed.type:
            continue
        if item.locationId != seed.location_id:
            continue
        if item.title.casefold() == seed_title:
            return True
    return False


def build_seed_item(seed: SeedItem, *, now_ms: int) -> WorldItem:
    """Create one WorldItem from seed metadata and catalog defaults."""

    definition = get_item_definition(seed.type)
    params = deepcopy(definition.default_params)
    params.update(deepcopy(seed.params))
    return WorldItem(
        id=seed.id or str(uuid.uuid4()),
        type=seed.type,
        title=seed.title,
        locationId=seed.location_id,
        x=seed.x,
        y=seed.y,
        createdBy="system",
        createdByName="system",
        updatedBy="system",
        updatedByName="system",
        createdAt=now_ms,
        updatedAt=now_ms,
        version=1,
        capabilities=list(definition.capabilities),
        useSound=definition.use_sound,
        emitSound=definition.emit_sound,
        params=params,
        carrierId=None,
    )


def ensure_builtin_items(items: dict[str, WorldItem], *, now_ms: int) -> list[WorldItem]:
    """Insert missing built-in service/station items and return added items."""

    added: list[WorldItem] = []
    for seed in BUILTIN_WORLD_ITEMS:
        if _matching_seed_exists(items, seed):
            continue
        item = build_seed_item(seed, now_ms=now_ms)
        items[item.id] = item
        added.append(item)
    return added
