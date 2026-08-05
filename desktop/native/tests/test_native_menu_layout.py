from pathlib import Path


def test_native_main_window_has_no_duplicate_status_strip():
    source = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")
    assert "self.status = wx.StaticText" not in source
    assert "self.SetStatusText(text)" in source


def test_shared_settings_are_file_menu_only_in_native_client():
    source = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")
    assert 'settings_shortcut = "Cmd+Alt+," if sys.platform == "darwin" else "Ctrl+Alt+,"' in source
    assert 'file_menu.Append(self.app_settings_id, f"&Settings...\\t{settings_shortcut}")' in source
    assert 'file_menu.Append(wx.ID_PREFERENCES, "&Desktop settings...")' in source
    assert "AppendSubMenu" not in source
    assert "#loginView,#authSessionView" in source
    assert "window.indiginousNativeOpenSettings?.();" in source
    assert "self.SetMenuBar(menu_bar)" in source
    assert "event.Skip()" in source
    assert 'self.SetName("Indiginous main window")' in source
    assert "EVT_MENU_OPEN" in source
    assert "EVT_MENU_CLOSE" in source
    assert "SetForegroundWindow" in source
    assert "SingleInstanceActivation" in source


def test_native_file_menu_does_not_use_single_item_submenus():
    source = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")
    assert 'file_menu.Append(wx.ID_REFRESH, "&Reconnect")' in source
    assert '"KeyR", ctrl=True' in source
    assert 'file_menu.Append(wx.ID_ABOUT, "&Credits and version")' in source
    assert "connection_menu" not in source
    assert "information_menu" not in source
    assert "self.browser_sign_in_item = file_menu.Append(" in source
    assert '"Sign in to &server\\tCtrl+Shift+S"' in source
    assert '"Sign in to another &server..."' in source
    assert "self.login_panel.Hide()" in source
    assert "_schedule_automatic_browser_auth" in source
    assert "Secure browser sign-in will start in 5 seconds." in source
    assert 'subprocess.Popen(["open", flow.authorization_url])' in source
    assert 'subprocess.Popen(["open", "-g", flow.authorization_url])' not in source
    assert 'Use File, Sign in to server to try again.' in source
    assert 'self._announce(f"{message} Use File, Sign in to server to try again.", speak=True)' in source
    assert 'label = "Sign &out\\tCtrl+Shift+S" if signed_in' in source


def test_public_links_are_menu_actions_not_startup_window_chrome():
    source = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")
    assert 'help_menu.Append(website_id, "Open Indiginous &website")' in source
    assert 'help_menu.Append(blindsoftware_id, "Open &blind.software")' in source
    assert 'https://blind.software/indiginous/' in source


def test_native_menu_highlight_is_spoken():
    source = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")
    assert "EVT_MENU_HIGHLIGHT" in source
    assert "GetMenuItem" in source
    assert "self._announce_menu(label)" in source
    assert 'name="indiginous-menu-speech"' in source
    assert "menu.FindItem(event.GetMenuId())" in source


def test_native_world_arrows_do_not_steal_open_menu_navigation():
    source = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")
    assert "if self.native_menu_open:" in source
    assert "self.native_menu_open = False" in source


def test_native_world_surface_hides_web_chrome_but_keeps_navigation():
    source = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")
    for element_id in ("gridTitle", "connectionStatus", "authSessionView", "button-container", "deviceSummary", "joinGuide", "appFooter"):
        assert f"#{element_id}" in source
    assert "#gridDashboard" not in source
    assert "#gameCanvas" not in source
    assert "#interactiveItemPanel" not in source


def test_native_audio_settings_are_applied_to_shared_client():
    source = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")
    assert "indiginousNativeApplyAudioSettings" in source
