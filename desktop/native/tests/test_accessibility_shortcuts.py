from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")


def test_native_shortcuts_are_explicitly_handled():
    assert "if key == wx.WXK_ALT:" not in SOURCE
    assert "SendMessageW" not in SOURCE
    assert "event.ControlDown() or event.MetaDown()" in SOURCE
    assert 'key == ord(",")' in SOURCE
    assert 'settings_shortcut = "Cmd+Alt+," if sys.platform == "darwin" else "Ctrl+Alt+,"' in SOURCE
    assert 'file_menu.Append(self.app_settings_id, f"&Settings...\\t{settings_shortcut}")' in SOURCE
    assert 'self._show_app_settings(event)' in SOURCE


def test_update_install_has_visible_countdown_and_cancel_path():
    assert "class UpdateInstallCountdown(wx.Dialog)" in SOURCE
    assert "self.remaining -= 1" in SOURCE
    assert '"Cancel update"' in SOURCE
    assert "service.install_after_exit(installer, manifest)" in SOURCE
    assert "self.force_exit = True" in SOURCE
    assert "seconds: int = 30" in SOURCE
    assert '"Install now"' in SOURCE
    assert 'self._announce("Indiginous is closing to install the verified update.", speak=True)' in SOURCE
    assert "self.exit_application()" not in SOURCE[SOURCE.index("def _prepare_update_install"):SOURCE.index("def _show_about")]
    assert "def _prepare_exit(self)" in SOURCE


def test_explicit_exit_does_not_present_an_update_dialog_and_forces_close():
    exit_start = SOURCE.index("    def exit_application")
    exit_source = SOURCE[exit_start:]
    assert 'self.force_exit = True' in exit_source
    assert 'self.Close(force=True)' in exit_source
    assert 'UpdateInstallCountdown(self, "exit Indiginous")' not in exit_source
    assert 'Exit cancelled. Indiginous will keep running.' not in exit_source


def test_update_controls_are_discoverable_and_respect_preferences():
    assert "Check for and install verified Indiginous updates automatically" in SOURCE
    assert 'help_menu.Append(updates_id, "Check for &updates")' in SOURCE
    assert "if self.settings.auto_update:" in SOURCE


def test_windows_installer_replaces_orphaned_files():
    installer = Path(__file__).parents[1] / "windows" / "installer" / "Indiginous.iss"
    source = installer.read_text(encoding="utf-8")
    assert 'Type: filesandordirs; Name: "{app}\\*"' in source
