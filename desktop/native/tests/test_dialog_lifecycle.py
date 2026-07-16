from pathlib import Path


def test_settings_dialog_owns_buttons_and_ends_modal_explicitly():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    panel_set = source.index("panel.SetSizer(layout)")
    buttons_created = source.index("buttons = self.CreateStdDialogButtonSizer")
    assert panel_set < buttons_created
    assert "self.EndModal(wx.ID_OK)" in source
    assert "self.EndModal(wx.ID_CANCEL)" in source


def test_file_dialogs_restore_focus_after_dismissal():
    source = (Path(__file__).parents[1] / "src" / "chat_grid_native" / "app.py").read_text(encoding="utf-8")
    assert source.count("if self.web.IsShown():") >= 2
    assert source.count("self.default_login.SetFocus()") >= 3
