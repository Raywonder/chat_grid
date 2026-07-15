from pathlib import Path


def test_native_main_window_has_no_duplicate_status_strip():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert "self.status = wx.StaticText" not in source
    assert "self.SetStatusText(text)" in source


def test_audio_setup_is_file_menu_only_in_native_client():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert 'file_menu.Append(self.audio_settings_id, "&Audio setup...\\tCtrl+Shift+A")' in source
    assert "AppendSubMenu" not in source
    assert "#deviceSummary,#joinGuide,#appFooter{display:none!important}" in source
    assert "document.getElementById('settingsButton')?.click();" in source


def test_native_file_menu_does_not_use_single_item_submenus():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert 'file_menu.Append(wx.ID_REFRESH, "&Reconnect\\tCtrl+R")' in source
    assert 'file_menu.Append(wx.ID_ABOUT, "&Credits and version\\tCtrl+Shift+C")' in source
    assert "connection_menu" not in source
    assert "information_menu" not in source
    assert "self.browser_sign_in_item = file_menu.Append(" in source
    assert '"Sign in with &browser\\tCtrl+Shift+S"' in source
    assert 'label = "Sign &out\\tCtrl+Shift+S" if signed_in' in source


def test_native_world_surface_hides_web_chrome_but_keeps_navigation():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    for element_id in ("gridTitle", "connectionStatus", "authSessionView", "button-container", "deviceSummary", "joinGuide", "appFooter"):
        assert f"#{element_id}" in source
    assert "#gridDashboard" not in source
    assert "#gameCanvas" not in source
    assert "#interactiveItemPanel" not in source
