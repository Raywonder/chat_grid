from pathlib import Path


def test_native_auto_connect_waits_for_authenticated_enabled_button():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert "authenticated&&button&&!button.disabled" in source
    assert "attempts>=120" in source
