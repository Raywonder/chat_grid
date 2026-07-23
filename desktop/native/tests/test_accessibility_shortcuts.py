from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")


def test_native_shortcuts_are_explicitly_handled():
    assert "if key == wx.WXK_ALT:" in SOURCE
    assert "SendMessageW" in SOURCE
    assert "event.ControlDown() or event.MetaDown()" in SOURCE
    assert 'key == ord(",")' in SOURCE
    assert 'settings_shortcut = "Cmd+," if sys.platform == "darwin" else "Ctrl+,"' in SOURCE
    assert 'file_menu.Append(self.app_settings_id, f"&Settings...\\t{settings_shortcut}")' in SOURCE
    assert 'self._show_app_settings(event)' in SOURCE


def test_update_install_has_visible_countdown_and_cancel_path():
    assert "class UpdateInstallCountdown(wx.Dialog)" in SOURCE
    assert "self.remaining -= 1" in SOURCE
    assert '"Cancel update"' in SOURCE
    assert "service.install_after_exit(installer, manifest)" in SOURCE
    assert "self.force_exit = True" in SOURCE
    assert 'self._announce("Endiginous is closing to install the verified update.", speak=True)' in SOURCE
    assert "self.exit_application()" not in SOURCE[SOURCE.index("def _prepare_update_install"):SOURCE.index("def _show_about")]
    assert "self._prepare_exit()" in SOURCE
    assert "Exit cancelled. Endiginous will keep running." in SOURCE
