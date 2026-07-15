"""Billboard item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def _billboard_details(item: WorldItem) -> str:
    """Build a concise spoken summary for one billboard."""

    mode = str(item.params.get("billboardMode", "interactive")).strip() or "interactive"
    headline = str(item.params.get("headline", "")).strip()
    body = str(item.params.get("body", "")).strip()
    announcement = str(item.params.get("announcementText", "")).strip()
    voice_name = str(item.params.get("voiceName", "")).strip()
    voice_asset_url = str(item.params.get("voiceAssetUrl", "")).strip()
    banner_text = str(item.params.get("bannerText", "")).strip()
    url = str(item.params.get("url", "")).strip()
    parts = [headline or item.title]
    if body:
        parts.append(body)
    if banner_text:
        banners = [part.strip() for part in banner_text.split("|") if part.strip()]
        if banners:
            parts.append(f"Rotating banners: {'; '.join(banners)}")
    if announcement:
        voice_prefix = f"{voice_name} says: " if voice_name else "Announcement: "
        parts.append(f"{voice_prefix}{announcement}")
    if voice_asset_url:
        parts.append("Real voice asset attached")
    if mode == "display_only":
        parts.append("Display only.")
    elif mode == "audio_only":
        parts.append("Audio only.")
    if url:
        parts.append(f"URL: {url}")
    return ". ".join(parts) + "."


def use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak or open billboard content depending on billboard mode."""

    if item.params.get("enabled") is False:
        return ItemUseResult(self_message=f"{item.title} is off.", others_message="")

    mode = str(item.params.get("billboardMode", "interactive")).strip().lower()
    details = _billboard_details(item)
    if mode == "display_only":
        return ItemUseResult(
            self_message=f"{details} This billboard is display only.",
            others_message="",
        )
    if mode == "audio_only":
        announcement = str(item.params.get("announcementText", "")).strip()
        voice_name = str(item.params.get("voiceName", "")).strip()
        if announcement:
            prefix = f"{voice_name}: " if voice_name else ""
            return ItemUseResult(self_message=f"{prefix}{announcement}", others_message="")
    return ItemUseResult(self_message=details, others_message="")


def secondary_use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak full billboard details."""

    return ItemUseResult(self_message=_billboard_details(item), others_message="")
