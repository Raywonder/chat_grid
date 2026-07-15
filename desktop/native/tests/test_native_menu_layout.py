from pathlib import Path


def test_native_main_window_has_no_duplicate_status_strip():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert "self.status = wx.StaticText" not in source
    assert "self.SetStatusText(text)" in source


def test_audio_setup_is_file_menu_only_in_native_client():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert 'file_menu.AppendSubMenu(settings_menu, "&Settings")' in source
    assert 'settings_menu.Append(self.audio_settings_id, "&Audio setup...")' in source
    assert "#settingsButton{display:none!important}" in source
    assert "document.getElementById('settingsButton')?.click();" in source
