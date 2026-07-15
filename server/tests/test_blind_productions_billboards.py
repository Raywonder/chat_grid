from app.blind_productions_billboards import (
    SYSTEM_USER_ID,
    BlindProductionsMessage,
    _ForumBoardParser,
    _MessageSummaryParser,
    upsert_blind_productions_billboards,
)


def test_forum_board_parser_finds_public_board_links() -> None:
    parser = _ForumBoardParser()
    parser.feed(
        """
        <a href="/forum/introductions/">Introductions</a>
        <a href="/forum/music-production/">Music</a>
        <a href="/accounts/login/">Log in</a>
        """
    )

    assert parser.links == ["/forum/introductions/", "/forum/music-production/"]


def test_message_summary_parser_extracts_thread_cards() -> None:
    parser = _MessageSummaryParser(source="introductions forum")
    parser.feed(
        """
        <article class="panel thread-summary" aria-labelledby="thread-1-title">
          <h2 class="thread-summary-title" id="thread-1-title">
            <a href="/forum/introductions/hello/">Hello there</a>
          </h2>
          <p class="thread-summary-meta muted">
            Started by Tony Gebhard &middot; 3 replies
            &middot; last activity <time datetime="2026-07-09T10:49:10-05:00">Jul 9</time>
          </p>
          <div class="thread-summary-preview prose">
            My name is Tony. I play music and play with AI.
          </div>
        </article>
        """
    )

    assert len(parser.messages) == 1
    message = parser.messages[0]
    assert message.title == "Hello there"
    assert message.author == "Tony Gebhard"
    assert message.url == "https://blind.productions/forum/introductions/hello/"
    assert message.preview == "My name is Tony. I play music and play with AI."
    assert message.updated == "2026-07-09T10:49:10-05:00"


def test_upsert_blind_productions_messages_as_billboards() -> None:
    messages = [
        BlindProductionsMessage(
            title="Creator update",
            url="https://blind.productions/forum/introductions/creator-update/",
            source="introductions forum",
            author="Mike B",
            preview="A public forum update from Blind Productions.",
            updated="2026-07-10T10:00:00-05:00",
        )
    ]
    items = {}

    changed = upsert_blind_productions_billboards(items, messages, now_ms=1234)

    assert len(changed) == 1
    item = changed[0]
    assert item.type == "billboard"
    assert item.createdBy == SYSTEM_USER_ID
    assert item.locationId == "town"
    assert item.params["billboardMode"] == "interactive"
    assert item.params["headline"] == "Creator update"
    assert item.params["url"] == messages[0].url
    assert "A public forum update" in item.params["body"]
    assert item.id in items

    changed_again = upsert_blind_productions_billboards(items, messages, now_ms=2234)
    assert changed_again == []
