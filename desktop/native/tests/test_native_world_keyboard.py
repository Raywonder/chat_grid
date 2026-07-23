from __future__ import annotations

from pathlib import Path


APP_SOURCE = Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py"
HOOK_SOURCE = Path(__file__).parents[1] / "src" / "chat_grid_native" / "windows_keyboard.py"


def test_native_world_exposes_application_role_and_bridges_arrows() -> None:
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "aria-roledescription','interactive audio world" in source
    assert "wx.WXK_LEFT" in source
    assert "wx.WXK_RIGHT" in source
    assert "wx.WXK_UP" in source
    assert "wx.WXK_DOWN" in source
    assert "window.chatGridNativeKey" in source
    assert "self.web.Bind(wx.EVT_KEY_DOWN, self._on_world_key_down)" in source
    assert "Catch arrows at the WebView boundary" in source
    assert "runImmediateMovement" in (Path(__file__).parents[3] / "client/src/input/keyboardController.ts").read_text(encoding="utf-8")
    assert "ctrlKey" in source
    assert "wx.AcceleratorTable" in source
    assert "Focus world\\tF6" in source
    assert 'if key not in {"external_auth", "native_client"}' in source
    assert 'navigation_query.append(("native_client", __version__))' in source


def test_windows_hook_is_foreground_only_and_preserves_modified_arrows() -> None:
    source = HOOK_SOURCE.read_text(encoding="utf-8")

    assert "WH_KEYBOARD_LL" in source
    assert "_is_foreground_process()" in source
    assert "VK_CONTROL" in source
    assert "VK_MENU" in source
    assert "self.on_arrow" in source
