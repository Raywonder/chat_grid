from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")


def test_file_menu_exposes_auth_without_manual_reconnect():
    file_menu = SOURCE[SOURCE.index("def _build_menu"):SOURCE.index("@staticmethod\n    def _open_external_url")]
    assert "Sign in to &Indiginous" in file_menu
    assert "Sign &out" not in file_menu  # label changes at runtime after auth
    assert "Reconnect to world" not in file_menu


def test_browser_sign_in_starts_world_connection_and_recovery_is_automatic():
    assert "self.pending_external_auth = True" in SOURCE
    assert "const button = document.getElementById('connectButton'); if (button) button.click();" in SOURCE
    assert "Connection interrupted. Reconnecting quietly in the background." in SOURCE
