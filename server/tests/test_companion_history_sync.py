from __future__ import annotations

import json
from pathlib import Path

from app.claudia_writing import record_inworld_direct_message


def test_inworld_history_record_is_deduplicated(tmp_path, monkeypatch) -> None:
    journal = tmp_path / "Journal"
    monkeypatch.setattr("app.claudia_writing.JOURNAL_DIR", journal)
    first = record_inworld_direct_message(
        sender="Dominique",
        message="File menu still is not reading.",
        location_id="raywonder_house_bedroom",
        created_at=1234,
    )
    second = record_inworld_direct_message(
        sender="Dominique",
        message="File menu still is not reading.",
        location_id="raywonder_house_bedroom",
        created_at=1234,
    )
    assert first == second
    assert len(list(journal.glob("*.md"))) == 1
