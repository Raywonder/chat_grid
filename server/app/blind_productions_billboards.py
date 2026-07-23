"""Blind Productions public-message billboard sync."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from .item_catalog import get_item_definition
from .models import WorldItem


BLIND_PRODUCTIONS_BASE_URL = "https://blind.productions/"
SYSTEM_USER_ID = "system:blind-productions"
SYSTEM_USER_NAME = "Blind Productions"
MAX_BILLBOARDS = 8
FETCH_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class BlindProductionsMessage:
    """One public Blind Productions message suitable for billboard display."""

    title: str
    url: str
    source: str
    author: str
    preview: str
    updated: str = ""
    expires_at_ms: int = 0
    max_rotations: int = 0
    location_id: str = "town"


class _ForumBoardParser(HTMLParser):
    """Extract public forum board links from the forum index."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = _attrs_dict(attrs).get("href", "")
        if re.fullmatch(r"/forum/[-a-z0-9]+/", href or ""):
            self.links.append(href)


class _MessageSummaryParser(HTMLParser):
    """Extract thread/news summary cards from public Blind Productions pages."""

    def __init__(self, *, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.messages: list[BlindProductionsMessage] = []
        self._article_depth = 0
        self._capture: str | None = None
        self._capture_depth = 0
        self._link_for_title = ""
        self._title_parts: list[str] = []
        self._preview_parts: list[str] = []
        self._meta_parts: list[str] = []
        self._updated = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = _attrs_dict(attrs)
        classes = set((attr.get("class") or "").split())

        if tag == "article" and (
            "thread-summary" in classes or "news-item" in classes
        ):
            self._article_depth = 1
            self._link_for_title = ""
            self._title_parts = []
            self._preview_parts = []
            self._meta_parts = []
            self._updated = ""
            return

        if self._article_depth <= 0:
            return

        self._article_depth += 1
        if tag in {"h2", "h3"} and (
            "thread-summary-title" in classes or "news-title" in classes
        ):
            self._start_capture("title")
        elif tag == "p" and (
            "thread-summary-meta" in classes
            or "board-meta" in classes
            or "news-date" in classes
        ):
            self._start_capture("meta")
        elif tag == "div" and (
            "thread-summary-preview" in classes or "news-body" in classes
        ):
            self._start_capture("preview")
        elif tag == "time" and not self._updated:
            self._updated = attr.get("datetime", "")

        if self._capture == "title" and tag == "a":
            href = attr.get("href", "")
            if href:
                self._link_for_title = urljoin(BLIND_PRODUCTIONS_BASE_URL, href)

    def handle_endtag(self, tag: str) -> None:
        if self._article_depth <= 0:
            return
        if self._capture is not None:
            self._capture_depth -= 1
            if self._capture_depth <= 0:
                self._capture = None
        self._article_depth -= 1
        if tag == "article" or self._article_depth <= 0:
            self._finish_article()
            self._article_depth = 0

    def handle_data(self, data: str) -> None:
        if self._capture == "title":
            self._title_parts.append(data)
        elif self._capture == "preview":
            self._preview_parts.append(data)
        elif self._capture == "meta":
            self._meta_parts.append(data)

    def _start_capture(self, name: str) -> None:
        self._capture = name
        self._capture_depth = 1

    def _finish_article(self) -> None:
        title = _clean_text(" ".join(self._title_parts))
        preview = _clean_text(" ".join(self._preview_parts))
        author = _extract_author(_clean_text(" ".join(self._meta_parts)))
        if not title or not self._link_for_title:
            return
        self.messages.append(
            BlindProductionsMessage(
                title=title,
                url=self._link_for_title,
                source=self.source,
                author=author,
                preview=preview,
                updated=self._updated,
            )
        )


def fetch_public_messages(
    *,
    base_url: str = BLIND_PRODUCTIONS_BASE_URL,
    max_messages: int = MAX_BILLBOARDS,
    timeout: int = FETCH_TIMEOUT_SECONDS,
) -> list[BlindProductionsMessage]:
    """Fetch public Blind Productions forum/news summaries."""

    base_url = base_url.rstrip("/") + "/"
    forum_html = _fetch_text(urljoin(base_url, "forum/"), timeout=timeout)
    board_parser = _ForumBoardParser()
    board_parser.feed(forum_html)

    messages: list[BlindProductionsMessage] = []
    for href in _unique(board_parser.links)[:8]:
        html = _fetch_text(urljoin(base_url, href), timeout=timeout)
        source = _source_from_forum_path(href)
        parser = _MessageSummaryParser(source=f"{source} forum")
        parser.feed(html)
        messages.extend(parser.messages)

    news_html = _fetch_text(urljoin(base_url, "news/"), timeout=timeout)
    news_parser = _MessageSummaryParser(source="news")
    news_parser.feed(news_html)
    messages.extend(news_parser.messages)

    messages.sort(key=lambda message: message.updated or "", reverse=True)
    return _unique_messages(messages)[:max_messages]


def upsert_blind_productions_billboards(
    items: dict[str, WorldItem],
    messages: list[BlindProductionsMessage],
    *,
    now_ms: int,
) -> list[WorldItem]:
    """Create/update system billboards for public Blind Productions messages."""

    changed: list[WorldItem] = []
    for index, message in enumerate(messages[:MAX_BILLBOARDS]):
        item_id = _message_item_id(message.url)
        params = _message_params(message)
        existing = items.get(item_id)
        if existing is None:
            item = _build_billboard_item(
                item_id=item_id,
                message=message,
                params=params,
                index=index,
                now_ms=now_ms,
            )
            items[item.id] = item
            changed.append(item)
            continue
        if existing.createdBy != SYSTEM_USER_ID:
            continue
        updated = False
        target_x, target_y = _billboard_position(index)
        if existing.locationId != message.location_id:
            existing.locationId = message.location_id
            updated = True
        if existing.x != target_x or existing.y != target_y:
            existing.x = target_x
            existing.y = target_y
            updated = True
        title = _item_title(message)
        if existing.title != title:
            existing.title = title
            updated = True
        for key, value in params.items():
            if existing.params.get(key) != value:
                existing.params[key] = value
                updated = True
        if updated:
            existing.updatedAt = now_ms
            existing.updatedBy = SYSTEM_USER_ID
            existing.updatedByName = SYSTEM_USER_NAME
            existing.version += 1
            changed.append(existing)
    return changed


def _fetch_text(url: str, *, timeout: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "EndiginousBlindProductionsBillboardSync/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _build_billboard_item(
    *,
    item_id: str,
    message: BlindProductionsMessage,
    params: dict[str, str | int | bool],
    index: int,
    now_ms: int,
) -> WorldItem:
    item_def = get_item_definition("billboard")
    x, y = _billboard_position(index)
    return WorldItem(
        id=item_id,
        type="billboard",
        title=_item_title(message),
        locationId=message.location_id,
        x=x,
        y=y,
        createdBy=SYSTEM_USER_ID,
        createdByName=SYSTEM_USER_NAME,
        updatedBy=SYSTEM_USER_ID,
        updatedByName=SYSTEM_USER_NAME,
        createdAt=now_ms,
        updatedAt=now_ms,
        version=1,
        capabilities=list(item_def.capabilities),
        useSound=item_def.use_sound,
        emitSound=item_def.emit_sound,
        params={**item_def.default_params, **params},
        carrierId=None,
    )


def _message_params(message: BlindProductionsMessage) -> dict[str, str | int | bool]:
    headline = _truncate(message.title, 120)
    body_source = message.preview or (
        f"New public {message.source} update from Blind Productions."
    )
    author_text = f" Posted by {message.author}." if message.author else ""
    body = _truncate(
        f"{body_source}{author_text} Come a little closer if you'd like more details.",
        360,
    )
    announcement = _truncate(
        f"Hey, passerby! Here's something interesting from {message.source}: "
        f"{message.title}. Come a little closer if you'd like more details. "
        f"{body_source}",
        500,
    )
    banner = " | ".join(
        part
        for part in (
            "Blind Productions",
            message.source.title(),
            message.title,
        )
        if part
    )
    return {
        "enabled": True,
        "billboardMode": "interactive",
        "itemVisibility": "visible",
        "headline": headline,
        "body": body,
        "url": _safe_public_url(message.url),
        "announcementText": announcement,
        "voiceName": "Clawdia",
        "bannerText": _truncate(banner, 500),
        "rotationSeconds": 18,
        "emitRange": 14,
        "expiresAtMs": message.expires_at_ms,
        "maxRotations": message.max_rotations,
    }


def _attrs_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name: value or "" for name, value in attrs}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _extract_author(meta: str) -> str:
    match = re.search(r"\bStarted by\s+(.+?)(?:\s*[·.]\s*|\s+\d+\s+repl|$)", meta)
    if not match:
        return ""
    return _truncate(match.group(1).strip(), 80)


def _item_title(message: BlindProductionsMessage) -> str:
    return _truncate(f"Blind Productions: {message.title}", 80)


def _message_item_id(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return f"bp-message-{digest}"


def _billboard_position(index: int) -> tuple[int, int]:
    positions = (
        (9, 10),
        (11, 10),
        (13, 10),
        (15, 10),
        (9, 12),
        (11, 12),
        (13, 12),
        (15, 12),
    )
    return positions[index % len(positions)]


def _source_from_forum_path(path: str) -> str:
    slug = path.strip("/").split("/")[-1]
    return slug.replace("-", " ").strip() or "community"


def _safe_public_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "blind.productions":
        return BLIND_PRODUCTIONS_BASE_URL
    return url


def _truncate(text: str, max_length: int) -> str:
    text = _clean_text(text)
    if len(text) <= max_length:
        return text
    return text[: max(0, max_length - 1)].rstrip() + "..."


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _unique_messages(
    messages: list[BlindProductionsMessage],
) -> list[BlindProductionsMessage]:
    seen: set[str] = set()
    unique_messages: list[BlindProductionsMessage] = []
    for message in messages:
        if message.url in seen:
            continue
        seen.add(message.url)
        unique_messages.append(message)
    return unique_messages
