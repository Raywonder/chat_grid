from pathlib import Path


def test_native_continues_browser_auth_after_callback():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert "self.pending_external_auth = False" in source
    assert "self.pending_external_auth = True" in source
    assert "if self.pending_external_auth:" in source
    assert "connectButton')?.click()" in source


def test_native_auth_completion_does_not_depend_on_callback_query_surviving():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert "new URL(window.location.href).searchParams.has('external_auth')" not in source
