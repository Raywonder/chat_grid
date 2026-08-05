from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")


def test_browser_callback_always_continues_to_connect() -> None:
    assert "self.pending_external_auth = False" in SOURCE
    assert "self.pending_external_auth = True" in SOURCE
    assert "if self.pending_external_auth:" in SOURCE
    assert "self.settings.auto_connect" not in SOURCE[SOURCE.index("def _on_loaded"):SOURCE.index("def _focus_world")]
    assert "const button = document.getElementById('connectButton'); if (button) button.click();" in SOURCE


def test_callback_completion_does_not_depend_on_browser_query_visibility() -> None:
    assert "new URL(window.location.href).searchParams.has('external_auth')" not in SOURCE


def test_browser_callback_listener_starts_before_browser_opens() -> None:
    start = SOURCE.index("flow.start(self._finish_browser_auth, self._browser_auth_failed)")
    browser_open = SOURCE.index("webbrowser.open(flow.authorization_url, new=2)")
    assert start < browser_open
