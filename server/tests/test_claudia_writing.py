"""Tests for private in-world writing continuity."""

import pytest

from app import claudia_writing
from app.server import SignalingServer


def test_record_inworld_direct_message_is_private_and_recoverable(tmp_path, monkeypatch) -> None:
    """A world DM is written to the private Journal without exposing it elsewhere."""

    journal = tmp_path / "Journal"
    letters = tmp_path / "Letters"
    monkeypatch.setattr(claudia_writing, "JOURNAL_DIR", journal)
    monkeypatch.setattr(claudia_writing, "LETTERS_DIR", letters)

    path = claudia_writing.record_inworld_direct_message(
        sender="Dominique",
        message="Please check the bedroom radio and write this down.",
        location_id="raywonder_house_bedroom",
    )

    assert path is not None
    assert path.parent == journal
    text = path.read_text(encoding="utf-8")
    assert "private: true" in text
    assert "sender: Dominique" in text
    assert "Please check the bedroom radio" in text
    assert claudia_writing.writing_indexes()[0] == [path.name]


def test_writing_indexes_are_bounded_and_sorted(tmp_path, monkeypatch) -> None:
    """The world item receives stable safe filenames rather than arbitrary paths."""

    journal = tmp_path / "Journal"
    letters = tmp_path / "Letters"
    journal.mkdir()
    letters.mkdir()
    (journal / "z-note.md").write_text("z", encoding="utf-8")
    (journal / "A-note.md").write_text("a", encoding="utf-8")
    (journal / ".secret").write_text("hidden", encoding="utf-8")
    monkeypatch.setattr(claudia_writing, "JOURNAL_DIR", journal)
    monkeypatch.setattr(claudia_writing, "LETTERS_DIR", letters)

    assert claudia_writing.writing_indexes() == (["A-note.md", "z-note.md"], [])


@pytest.mark.asyncio
async def test_world_folder_sync_updates_the_real_item(monkeypatch) -> None:
    """The physical writing item follows the canonical source indexes."""

    server = SignalingServer("127.0.0.1", 8765, None, None)
    folder = server.items["seed-raywonder-bedroom-claudia-journal-folder"]
    broadcasted: list[object] = []
    monkeypatch.setattr(
        "app.server.writing_indexes", lambda: (["new-entry.md"], ["new-letter.md"])
    )
    monkeypatch.setattr(server.item_service, "now_ms", lambda: 456_000)

    async def broadcast(item: object) -> None:
        broadcasted.append(item)

    monkeypatch.setattr(server, "_broadcast_item", broadcast)
    assert await server._sync_claudia_writing_folder() is True
    assert folder.params["journalIndex"] == ["new-entry.md"]
    assert folder.params["letterIndex"] == ["new-letter.md"]
    assert broadcasted == [folder]
