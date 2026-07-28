from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")


def test_browser_callback_always_continues_to_connect() -> None:
    assert "self.pending_external_auth = False" in SOURCE
    assert "self.pending_external_auth = True" in SOURCE
    assert "if self.pending_external_auth or self.settings.auto_connect:" in SOURCE
    assert "connectButton')?.click()" in SOURCE


def test_callback_completion_does_not_depend_on_browser_query_visibility() -> None:
    assert "new URL(window.location.href).searchParams.has('external_auth')" not in SOURCE
