from pathlib import Path


def test_native_does_not_race_web_saved_session_auto_connect():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert "button.click()" not in source
    assert "shared web client owns saved-session auto-connect" in source
