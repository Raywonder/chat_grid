"""Accessible wxPython shell around the shared Chat Grid client."""

from __future__ import annotations

import logging
import json
import os
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit, urlunsplit

import wx
import wx.adv
import wx.html2

from . import __version__
from .config import APP_ID, APP_NAME, Settings, SettingsStore, app_data_dir
from .deeplink import resolve_launch_url
from .reconnect import ReconnectBackoff
from .screen_reader import ScreenReaderSpeech
from .spatial_audio import spatial_audio_script
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
        self.spatial_audio = wx.CheckBox(panel, label="Use binaural spatial audio for world sounds")
        self.spatial_audio.SetValue(settings.spatial_audio)
        layout.Add(self.spatial_audio, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        panel.SetSizer(layout)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        outer.Add(buttons, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(outer)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.startup.SetFocus()

    def _on_ok(self, _event: wx.CommandEvent) -> None:
        """Apply values and close reliably for keyboard and screen-reader activation."""
        self.apply()
        self.EndModal(wx.ID_OK)

    def _on_cancel(self, _event: wx.CommandEvent) -> None:
        """Dismiss without changing the supplied settings object."""
        self.EndModal(wx.ID_CANCEL)

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()

    def apply(self) -> None:
        """Copy control state into settings."""
        self.settings.start_with_windows = self.startup.GetValue()
        self.settings.start_minimized = self.minimized.GetValue()
        self.settings.auto_connect = self.connect.GetValue()
        self.settings.keep_in_tray = self.tray.GetValue()
        self.settings.spatial_audio = self.spatial_audio.GetValue()


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

        self.login_panel = wx.Panel(panel)
        login_layout = wx.BoxSizer(wx.VERTICAL)
        self.default_login = wx.Button(self.login_panel, label="&Sign in to Blind Software")
        login_layout.Add(self.default_login, 0, wx.EXPAND | wx.ALL, 8)
        domain_label = wx.StaticText(self.login_panel, label="Other Chat Grid server domain:")
        login_layout.Add(domain_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.domain = wx.TextCtrl(self.login_panel, value="", style=wx.TE_PROCESS_ENTER)
        self.domain.SetHint("example.com")
        login_layout.Add(self.domain, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.domain_login = wx.Button(self.login_panel, label="Sign in to this &server")
        login_layout.Add(self.domain_login, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.login_panel.SetSizer(login_layout)
        layout.Add(self.login_panel, 0, wx.EXPAND | wx.ALL, 12)

        if sys.platform == "win32":
            self.web = wx.html2.WebView.New(panel, backend=wx.html2.WebViewBackendEdge)
        else:
            self.web = wx.html2.WebView.New(panel)
        layout.Add(self.web, 1, wx.EXPAND)
        self.web.Hide()
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
        self.default_login.Bind(wx.EVT_BUTTON, self._login_default)
        self.domain_login.Bind(wx.EVT_BUTTON, self._login_domain)
        self.domain.Bind(wx.EVT_TEXT_ENTER, self._login_domain)

        if launch_url:
            self._open_grid(launch_url)
        else:
            self._announce("Choose a Chat Grid server and sign in.")
            self.default_login.SetFocus()
        if autostart and self.settings.start_minimized:
            self.Iconize(True)
        else:
            self.Show()
        wx.CallLater(5000, self._check_updates_background)

    def _build_menu(self) -> None:
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()

        connection_menu = wx.Menu()
        connection_menu.Append(wx.ID_REFRESH, "&Reconnect\tCtrl+R")
        file_menu.AppendSubMenu(connection_menu, "&Connection")

        settings_menu = wx.Menu()
        settings_menu.Append(wx.ID_PREFERENCES, "&Desktop settings...\tCtrl+,")
        self.audio_settings_id = wx.NewIdRef()
        settings_menu.Append(self.audio_settings_id, "&Audio setup...")
        file_menu.AppendSubMenu(settings_menu, "&Settings")

        information_menu = wx.Menu()
        information_menu.Append(wx.ID_ABOUT, "&Credits and version")
        file_menu.AppendSubMenu(information_menu, "&Information")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "E&xit\tAlt+F4")
        menu_bar.Append(file_menu, "&File")
        self.SetMenuBar(menu_bar)
        self.Bind(wx.EVT_MENU, lambda _event: self._reload(), id=wx.ID_REFRESH)
        self.Bind(wx.EVT_MENU, self._show_settings, id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, self._show_audio_settings, id=self.audio_settings_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.exit_application(), id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self._show_about, id=wx.ID_ABOUT)

    def _announce(self, text: str) -> None:
        self.SetStatusText(text)

    @staticmethod
    def _server_url(value: str) -> str:
        """Return an HTTPS Chat Grid URL for a user-entered domain."""
        candidate = value.strip()
        if not candidate:
            raise ValueError("Enter a server domain.")
        if "://" not in candidate:
            candidate = f"https://{candidate}"
        parsed = urlsplit(candidate)
        if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Enter a valid HTTPS server domain.")
        port = f":{parsed.port}" if parsed.port else ""
        return urlunsplit(("https", f"{parsed.hostname}{port}", "/chatgrid/", "", ""))

    def _open_grid(self, url: str) -> None:
        self.settings.grid_url = url
        self.store.save(self.settings)
        self.login_panel.Hide()
        self.web.Show()
        self.web.GetParent().Layout()
        self._announce("Opening secure browser sign-in.")
        self.web.LoadURL(url)
        self.web.SetFocus()

    def _login_default(self, _event: wx.CommandEvent) -> None:
        self._open_grid("https://blind.software/chatgrid/")

    def _login_domain(self, _event: wx.CommandEvent) -> None:
        try:
            url = self._server_url(self.domain.GetValue())
        except (ValueError, OverflowError):
            self._announce("Enter a valid HTTPS server domain, such as example.com.")
            self.domain.SetFocus()
            return
        self._open_grid(url)

    def _on_loaded(self, _event: wx.html2.WebViewEvent) -> None:
        self.reconnect_timer.Stop()
        self.backoff.reset()
        self._announce("Chat Grid loaded. Session and reconnect monitoring are active.")
        # The shared web client owns saved-session auto-connect. Injecting a
        # second Connect click races its cookie/auth startup and can create a
        # storm of short-lived websocket sessions.
        self.web.RunScript(
            "window.chatGridNativeSpeak=(text,options={})=>"
            "window.chrome?.webview?.postMessage(JSON.stringify({type:'speak',text:String(text),interrupt:!!options.interrupt}));"
        )
        self.web.RunScript(
            "(()=>{document.documentElement.classList.add('chatgrid-native');"
            "let style=document.getElementById('chatgridNativeChrome');"
            "if(!style){style=document.createElement('style');style.id='chatgridNativeChrome';"
            "style.textContent='#settingsButton{display:none!important}';document.head.appendChild(style);}})();"
        )
        self.web.RunScript(spatial_audio_script(self.settings.spatial_audio))

    def _on_script_message(self, event: wx.html2.WebViewEvent) -> None:
        """Accept bounded speech requests only from the approved Chat Grid origin."""
        expected = urlsplit(self.settings.grid_url)
        current = urlsplit(self.web.GetCurrentURL())
        if current.scheme != "https" or current.netloc != expected.netloc:
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
        self._open_grid(self.settings.grid_url)

    def _show_settings(self, _event: wx.CommandEvent) -> None:
        saved = False
        with SettingsDialog(self, self.settings) as dialog:
            saved = dialog.ShowModal() == wx.ID_OK
        if saved:
            self.store.save(self.settings)
            set_start_with_windows(self.settings.start_with_windows)
            self._announce("Desktop settings saved.")
        if self.web.IsShown():
            self.web.SetFocus()
        else:
            self.default_login.SetFocus()

    def _show_audio_settings(self, _event: wx.CommandEvent) -> None:
        """Open the shared audio dialog from the native File menu."""
        if not self.web.IsShown():
            self._announce("Sign in to a Chat Grid server before opening audio setup.")
            self.default_login.SetFocus()
            return
        self.web.RunScript("document.getElementById('settingsButton')?.click();")
        self.web.SetFocus()

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
        if self.web.IsShown():
            self.web.SetFocus()
        else:
            self.default_login.SetFocus()

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
