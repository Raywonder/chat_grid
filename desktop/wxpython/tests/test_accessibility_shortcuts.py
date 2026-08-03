from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")


def test_native_shortcuts_are_explicitly_handled():
    assert "if key == wx.WXK_ALT:" not in SOURCE
    assert "SendMessageW" not in SOURCE
    assert "event.ControlDown() or event.MetaDown()" in SOURCE
    assert 'key == ord(",")' in SOURCE
    assert 'settings_shortcut = "Cmd+Alt+," if sys.platform == "darwin" else "Ctrl+Alt+,"' in SOURCE


def test_update_install_has_visible_countdown_and_cancel_path():
    assert "class UpdateInstallCountdown(wx.Dialog)" in SOURCE
    assert "self.remaining -= 1" in SOURCE
    assert '"Cancel update"' in SOURCE
    assert "service.install_after_exit(installer, manifest)" in SOURCE
    assert "seconds: int = 30" in SOURCE
    assert '"Install now"' in SOURCE
    assert "Update cancelled. Indiginous will keep running." in SOURCE
    assert "def _quit_without_update" in SOURCE
    assert "No verified update available during quit" in SOURCE


def test_explicit_exit_does_not_present_an_update_dialog_and_forces_close():
    exit_source = SOURCE[SOURCE.index("    def request_exit"):SOURCE.index("    def _on_iconize")]
    assert 'self.force_quit = True' in exit_source
    assert 'self.Close()' in exit_source
    assert 'chat-grid-exit-update-check' not in exit_source
    assert 'UpdateInstallCountdown(self, "exit Indiginous")' not in exit_source
    assert 'Exit cancelled. Indiginous will keep running.' not in exit_source


def test_windows_installer_replaces_orphaned_files():
    installer = Path(__file__).parents[1] / "installer" / "ChatGrid.iss"
    source = installer.read_text(encoding="utf-8")
    assert 'Type: filesandordirs; Name: "{app}\\*"' in source


def test_windows_installer_shows_application_license_not_source_only_license():
    project_root = Path(__file__).parents[3]
    installer = Path(__file__).parents[1] / "installer" / "ChatGrid.iss"
    source = installer.read_text(encoding="utf-8")
    license_path = project_root / "INDIGINOUS_APPLICATION_LICENSE.txt"
    license_text = license_path.read_text(encoding="utf-8")
    assert "LicenseFile=..\\..\\..\\INDIGINOUS_APPLICATION_LICENSE.txt" in source
    assert "BLIND.SOFTWARE USE LICENSE" in license_text
    assert "separate from the MIT License" in license_text
    assert "does not grant rights to the" in license_text
    assert "blind.software account" in license_text


def test_settings_ok_and_cancel_explicitly_close_modal():
    assert "self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)" in SOURCE
    assert "self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)" in SOURCE
    assert "self.EndModal(wx.ID_OK)" in SOURCE
    assert "self.EndModal(wx.ID_CANCEL)" in SOURCE


def test_native_settings_owns_all_audio_controls_and_hides_duplicate_web_modal():
    for marker in (
        'wx.StaticBoxSizer(wx.VERTICAL, panel, "Audio")',
        'self.output_mode = wx.Choice',
        'self.master_volume = wx.Slider',
        'self.microphone_gain = wx.Slider',
        'self.voice_layer = wx.CheckBox',
        'self.item_layer = wx.CheckBox',
        'self.media_layer = wx.CheckBox',
        'self.world_layer = wx.CheckBox',
        'self.announcement_mode = wx.Choice',
        'self.radio_announcement_mode = wx.Choice',
        '#openSettingsButton,#settingsModal{display:none!important}',
    ):
        assert marker in SOURCE


def test_startup_keeps_public_links_in_help_menu_not_main_window():
    assert 'help_menu.Append(website_id, "Open Indiginous &website")' in SOURCE
    assert 'help_menu.Append(blindsoftware_id, "Open &blind.software")' in SOURCE
    assert 'self._open_external_url("https://blind.software/indiginous/")' in SOURCE
    assert 'self._open_external_url("https://blind.software/")' in SOURCE


def test_native_menu_highlight_is_spoken():
    assert "EVT_MENU_HIGHLIGHT" in SOURCE
    assert "GetMenuItem" in SOURCE
    assert "self._announce(label)" in SOURCE


def test_activation_rearms_world_focus_after_restore_and_alt_tab():
    assert 'self.Bind(wx.EVT_ACTIVATE, self._on_activate)' in SOURCE
    assert 'def _queue_world_focus' in SOURCE
    assert 'self._queue_world_focus(120)' in SOURCE


def test_signed_in_users_do_not_get_a_sign_in_menu_action():
    assert 'label = "Sign &out\\tCtrl+Shift+S" if signed_in' in SOURCE
    assert 'def _login_or_logout(self)' in SOURCE
    assert 'signed_in = bool(message.get("signedIn"))' in SOURCE
    assert 'self._announce(message["message"].strip())' in SOURCE


def test_native_world_arrows_do_not_steal_open_menu_navigation():
    assert "EVT_MENU_CLOSE" in SOURCE
    assert "menu.FindItem(event.GetMenuId())" in SOURCE
    assert "if self.native_menu_open:" in SOURCE


def test_native_settings_includes_real_input_and_output_device_choices():
    assert 'self.audio_input = wx.Choice' in SOURCE
    assert 'self.audio_output = wx.Choice' in SOURCE
    assert 'window.indiginousNativeRefreshAudioDevices' in SOURCE
    assert 'inputDeviceId' in SOURCE
    assert 'outputDeviceId' in SOURCE
