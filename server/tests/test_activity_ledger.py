from __future__ import annotations

import json

from app.activity_ledger import ActivityLedger


def test_activity_ledger_deduplicates_and_keeps_summary_only(tmp_path) -> None:
    path = tmp_path / "runtime" / "activity.jsonl"
    ledger = ActivityLedger(path)
    assert ledger.record("direct message", event_id="m1", sender="Dominique", message="private text")
    assert not ledger.record("direct message", event_id="m1", sender="Dominique")
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["type"] == "direct_message"
    assert record["sender"] == "Dominique"
    assert record["message"] == "private text"


def test_activity_ledger_reloads_ids_after_restart(tmp_path) -> None:
    path = tmp_path / "activity.jsonl"
    assert ActivityLedger(path).record("world_ready", event_id="w1", location="outside")
    restarted = ActivityLedger(path)
    assert not restarted.record("world_ready", event_id="w1", location="outside")
