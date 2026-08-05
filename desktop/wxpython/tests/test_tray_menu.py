from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "src" / "indiginous_native" / "app.py").read_text(encoding="utf-8")


def test_tray_menu_exposes_core_actions_and_is_keyboard_labelled():
    tray = SOURCE[SOURCE.index("class IndiginousTrayIcon"):SOURCE.index("class SettingsDialog")]
    for label in (
        '"&Open Indiginous"',
        '"&Settings..."',
        '"Check for &updates"',
        '"Open Indiginous &website"',
        '"&About Indiginous"',
        '"&Quit Indiginous"',
    ):
        assert label in tray
    assert "menu.Bind(wx.EVT_MENU" in tray
    assert "self.Bind(wx.EVT_MENU" not in tray
    assert "self.frame._focus_world()" not in tray
    assert '"&Reconnect Indiginous"' not in tray
