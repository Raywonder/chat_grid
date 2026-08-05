from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")


def test_tray_menu_exposes_core_actions_and_is_keyboard_labelled():
    tray = SOURCE[SOURCE.index("class TrayIcon"):SOURCE.index("class SettingsDialog")]
    for label in (
        '"&Restore Indiginous"',
        '"&Reconnect"',
        '"&Focus world"',
        '"&App settings..."',
        '"&Desktop settings..."',
        '"Check for &updates"',
        '"&Credits and version"',
        '"E&xit Indiginous"',
    ):
        assert label in tray
    assert "menu.Bind(wx.EVT_MENU" in tray
    assert "self.Bind(wx.EVT_MENU" not in tray
