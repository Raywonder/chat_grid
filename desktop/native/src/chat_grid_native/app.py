"""Accessible wxPython shell around the shared Chat Grid client."""

from __future__ import annotations

import logging
import json
import os
from pathlib import Path
import sys
import threading

import wx
import wx.adv
import wx.html2

from . import __version__
from .config import APP_ID, APP_NAME, Settings, SettingsStore, app_data_dir
from .deeplink import resolve_launch_url
from .reconnect import ReconnectBackoff
from .screen_reader import ScreenReaderSpeech
from .startup import set_start_with_windows
from .updater import UpdateService


LOGGER = logging.getLogger(__name__)


class TrayIcon(wx.adv.TaskBarIcon):
    """Keyboard-accessible system tray/menu-bar control."""

    def __init__(self, frame: "MainFrame") -> None:
        super().__init__()
        self.frame = frame
        icon = wx.Icon()
        icon.CopyFromBitmap(wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, (32, 32)))
        self.SetIcon(icon, "Chat Grid — connected in the background")
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, lambda _event: frame.restore_from_tray())

    def CreatePopupMenu(self) -> wx.Menu:
        menu = wx.Menu()
        restore = menu.Append(wx.ID_ANY, "&Restore Chat Grid")
        menu.AppendSeparator()
        exit_item = menu.Append(wx.ID_EXIT, "E&xit Chat Grid")
        self.Bind(wx.EVT_MENU, lambda _event: self.frame.restore_from_tray(), restore)
        self.Bind(wx.EVT_MENU, lambda _event: self.frame.exit_application(), exit_item)
        return menu


class SettingsDialog(wx.Dialog):
    """Accessible desktop behavior settings."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(parent, title="Chat Grid desktop settings")
        self.settings = settings
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)

        self.startup = wx.CheckBox(panel, label="Start Chat Grid when I sign in to this computer")
        self.startup.SetValue(settings.start_with_windows)
        layout.Add(self.startup, 0, wx.ALL, 8)
        self.minimized = wx.CheckBox(panel, label="Start minimized when the computer starts")
        self.minimized.SetValue(settings.start_minimized)
        layout.Add(self.minimized, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.connect = wx.CheckBox(panel, label="Connect automatically after sign-in")
        self.connect.SetValue(settings.auto_connect)
        layout.Add(self.connect, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.tray = wx.CheckBox(panel, label="Keep me signed in and running in the background when I close the window")
        self.tray.SetValue(settings.keep_in_tray)
        layout.Add(self.tray, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(layout)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)
        self.startup.SetFocus()

    def apply(self) -> None:
        """Copy control state into settings."""
        self.settings.start_with_windows = self.startup.GetValue()
        self.settings.start_minimized = self.minimized.GetValue()
        self.settings.auto_connect = self.connect.GetValue()
        self.settings.keep_in_tray = self.tray.GetValue()


class MainFrame(wx.Frame):
    """Main native window and resilient WebView host."""

    def __init__(self, settings_store: SettingsStore, autostart: bool = False, launch_url: str | None = None) -> None:
        super().__init__(None, title=APP_NAME, size=(1120, 820))
        self.store = settings_store
        self.settings = settings_store.load()
        self.backoff = ReconnectBackoff(self.settings.reconnect_initial_seconds, self.settings.reconnect_max_seconds)
        self.reconnect_timer = wx.Timer(self)
        self.update_thread: threading.Thread | None = None
        self.tray_icon: TrayIcon | None = None
        self.force_exit = False
        self.screen_reader = ScreenReaderSpeech()

        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(panel, label="Starting Chat Grid.")
        layout.Add(self.status, 0, wx.EXPAND | wx.ALL, 6)
        if sys.platform == "win32":
            self.web = wx.html2.WebView.New(panel, backend=wx.html2.WebViewBackendEdge)
        else:
            self.web = wx.html2.WebView.New(panel)
        layout.Add(self.web, 1, wx.EXPAND)
        self.web.AddScriptMessageHandler("chatgridNative")
        panel.SetSizer(layout)

        self._build_menu()
        self.CreateStatusBar()
        self.SetStatusText("Starting Chat Grid")
        self.Bind(wx.html2.EVT_WEBVIEW_LOADED, self._on_loaded, self.web)
        self.Bind(wx.html2.EVT_WEBVIEW_ERROR, self._on_error, self.web)
        self.Bind(wx.html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_script_message, self.web)
        self.Bind(wx.EVT_TIMER, self._on_reconnect_timer, self.reconnect_timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        self.web.LoadURL(launch_url or self.settings.grid_url)
        if autostart and self.settings.start_minimized:
            self.Iconize(True)
        else:
            self.Show()
        wx.CallLater(5000, self._check_updates_background)

    def _build_menu(self) -> None:
        menu_bar = wx.MenuBar()
        app_menu = wx.Menu()
        app_menu.Append(wx.ID_REFRESH, "&Reconnect\tCtrl+R")
        app_menu.Append(wx.ID_PREFERENCES, "&Settings...\tCtrl+,")
        app_menu.AppendSeparator()
        app_menu.Append(wx.ID_EXIT, "E&xit\tAlt+F4")
        menu_bar.Append(app_menu, "&Chat Grid")
        help_menu = wx.Menu()
        help_menu.Append(wx.ID_ABOUT, "&About Chat Grid")
        menu_bar.Append(help_menu, "&Help")
        self.SetMenuBar(menu_bar)
        self.Bind(wx.EVT_MENU, lambda _event: self._reload(), id=wx.ID_REFRESH)
        self.Bind(wx.EVT_MENU, self._show_settings, id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, lambda _event: self.exit_application(), id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self._show_about, id=wx.ID_ABOUT)

    def _announce(self, text: str) -> None:
        self.status.SetLabel(text)
        self.SetStatusText(text)

    def _on_loaded(self, _event: wx.html2.WebViewEvent) -> None:
        self.reconnect_timer.Stop()
        self.backoff.reset()
        self._announce("Chat Grid loaded. Session and reconnect monitoring are active.")
        if self.settings.auto_connect:
            self.web.RunScript("setTimeout(() => document.getElementById('connectButton')?.click(), 500);")
        self.web.RunScript(
            "window.chatGridNativeSpeak=(text,options={})=>"
            "window.chrome?.webview?.postMessage(JSON.stringify({type:'speak',text:String(text),interrupt:!!options.interrupt}));"
        )

    def _on_script_message(self, event: wx.html2.WebViewEvent) -> None:
        """Accept bounded speech requests only from the approved Chat Grid origin."""
        if not self.web.GetCurrentURL().startswith("https://blind.software/chatgrid/"):
            return
        try:
            message = json.loads(event.GetString())
        except (TypeError, ValueError):
            return
        if message.get("type") != "speak" or not isinstance(message.get("text"), str):
            return
        self.screen_reader.speak(message["text"], bool(message.get("interrupt")))

    def _on_error(self, event: wx.html2.WebViewEvent) -> None:
        LOGGER.warning("WebView load error: %s", event.GetString())
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        delay = self.backoff.next_delay()
        self._announce("Connection interrupted. Reconnecting quietly in the background.")
        self.reconnect_timer.StartOnce(max(250, int(delay * 1000)))

    def _on_reconnect_timer(self, _event: wx.TimerEvent) -> None:
        self.web.LoadURL(self.settings.grid_url)

    def _reload(self) -> None:
        self.backoff.reset()
        self.web.LoadURL(self.settings.grid_url)

    def _show_settings(self, _event: wx.CommandEvent) -> None:
        with SettingsDialog(self, self.settings) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            dialog.apply()
            self.store.save(self.settings)
            set_start_with_windows(self.settings.start_with_windows)
            self._announce("Desktop settings saved.")

    def _check_updates_background(self, interactive: bool = False) -> None:
        if self.update_thread and self.update_thread.is_alive():
            return

        def worker() -> None:
            try:
                service = UpdateService(self.settings.update_url, __version__, app_data_dir())
                manifest = service.check()
                if manifest is None:
                    if interactive:
                        wx.CallAfter(self._announce, "Chat Grid is up to date.")
                    return
                installer = service.download(manifest)
                service.install_after_exit(installer, manifest)
                wx.CallAfter(self._announce, f"Chat Grid {manifest.version} is verified and ready to install.")
                wx.CallAfter(self.exit_application)
            except Exception as error:
                LOGGER.warning("Update check failed: %s", error)
                if interactive:
                    wx.CallAfter(self._announce, "Update check failed. The current app will keep running.")

        self.update_thread = threading.Thread(target=worker, name="chat-grid-updater", daemon=True)
        self.update_thread.start()

    def _show_about(self, _event: wx.CommandEvent) -> None:
        wx.MessageBox(
            f"Chat Grid {__version__}\nOfficial accessible desktop client by Raywonder / TappedIn.",
            "About Chat Grid", wx.OK | wx.ICON_INFORMATION, self,
        )

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE and self.IsIconized():
            self.Iconize(False)
            self.Raise()
            return
        event.Skip()

    def _on_close(self, event: wx.CloseEvent) -> None:
        if self.settings.keep_in_tray and not self.force_exit and event.CanVeto():
            event.Veto()
            self.Hide()
            if self.tray_icon is None:
                self.tray_icon = TrayIcon(self)
            self._announce("Chat Grid is still connected and running in the background.")
            return
        self.reconnect_timer.Stop()
        if self.tray_icon is not None:
            self.tray_icon.RemoveIcon()
            self.tray_icon.Destroy()
            self.tray_icon = None
        event.Skip()

    def restore_from_tray(self) -> None:
        """Restore and focus the main window from its background state."""
        self.Show()
        self.Iconize(False)
        self.Raise()
        self.web.SetFocus()
        self._announce("Chat Grid window restored. You remained signed in.")

    def exit_application(self) -> None:
        """Fully stop Chat Grid, including any background session."""
        self.force_exit = True
        self.Close(force=True)


class ChatGridApp(wx.App):
    """Application entry point."""

    def OnInit(self) -> bool:
        if sys.platform == "win32":
            os.environ.setdefault("WEBVIEW2_USER_DATA_FOLDER", str(app_data_dir() / "WebView2"))
        autostart = "--autostart" in sys.argv
        launch_url = resolve_launch_url(sys.argv[1:])
        self.frame = MainFrame(SettingsStore(), autostart=autostart, launch_url=launch_url)
        self.SetTopWindow(self.frame)
        return True


def main() -> int:
    """Start the GUI."""
    root = app_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=root / "chat-grid.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = ChatGridApp(False)
    app.MainLoop()
    return 0
