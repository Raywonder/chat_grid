import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import blindsoftware_clawdia_chat_worker as worker


def make_db(tmp_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(tmp_path / "chat.sqlite")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, email TEXT);
        CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER,
          recipient_id INTEGER, body TEXT, created_at TEXT, context_snapshot TEXT DEFAULT '');
        CREATE TABLE notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
          type TEXT, title TEXT, body TEXT, url TEXT, is_read INTEGER, created_at TEXT);
        INSERT INTO users VALUES(1, 'One', 'one@example.test');
        INSERT INTO users VALUES(2, 'Two', 'two@example.test');
        INSERT INTO users VALUES(9, 'Clawdia', 'clawdia@tappedin.fm');
        """
    )
    worker.ensure_schema(db)
    return db


def test_parse_reply_uses_text_not_agent_name() -> None:
    raw = json.dumps({"status": "ok", "result": {"payloads": [
        {"name": "Clawdia", "displayName": "Clawdia", "text": "Clawdia: Actual reply"}
    ]}})
    assert worker.parse_reply(raw) == "Actual reply"


def test_parse_reply_rejects_name_only() -> None:
    raw = json.dumps({"status": "ok", "result": {"payloads": [{"text": "Clawdia"}]}})
    try:
        worker.parse_reply(raw)
    except RuntimeError as exc:
        assert "name-only" in str(exc)
    else:
        raise AssertionError("name-only reply was accepted")


def test_conversation_is_user_scoped(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    db.execute("INSERT INTO messages(sender_id,recipient_id,body,created_at) VALUES(1,9,'one inbound','t')")
    db.execute("INSERT INTO messages(sender_id,recipient_id,body,created_at) VALUES(9,1,'one reply','t')")
    db.execute("INSERT INTO messages(sender_id,recipient_id,body,created_at) VALUES(2,9,'two private','t')")
    history = worker.conversation_for_user(db, user_id=1, agent_id=9, before_id=999)
    assert [entry["text"] for entry in history] == ["one inbound", "one reply"]


def test_save_reply_keeps_body_separate_from_sender(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    cursor = db.execute("INSERT INTO messages(sender_id,recipient_id,body,created_at) VALUES(1,9,'hello','t')")
    message_id = int(cursor.lastrowid)
    worker.mark_attempt(db, message_id)
    reply_id = worker.save_reply(
        db, message_id=message_id, user_id=1, agent_id=9, reply="The actual reply body"
    )
    row = db.execute("SELECT sender_id,recipient_id,body FROM messages WHERE id=?", (reply_id,)).fetchone()
    assert tuple(row) == (9, 1, "The actual reply body")
    other_visible = db.execute(
        "SELECT count(*) FROM messages WHERE id=? AND recipient_id=2", (reply_id,)
    ).fetchone()[0]
    assert other_visible == 0
