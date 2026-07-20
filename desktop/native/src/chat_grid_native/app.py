"""Accessible wxPython shell around the shared Endiginous client."""

from __future__ import annotations

import logging
import json
import os
import ctypes
from pathlib import Path
import sys
import threading
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import webbrowser

import wx
import wx.adv
import wx.html2

from . import __version__
from .browser_auth import BrowserAuthFlow
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
        self.SetIcon(icon, "Endiginous — connected in the background")
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, lambda _event: frame.restore_from_tray())

    def CreatePopupMenu(self) -> wx.Menu:
        menu = wx.Menu()
        restore = menu.Append(wx.ID_ANY, "&Restore Endiginous")
        menu.AppendSeparator()
        exit_item = menu.Append(wx.ID_EXIT, "E&xit Endiginous")
        self.Bind(wx.EVT_MENU, lambda _event: self.frame.restore_from_tray(), restore)
        self.Bind(wx.EVT_MENU, lambda _event: self.frame.exit_application(), exit_item)
        return menu


class SettingsDialog(wx.Dialog):
    """Accessible desktop behavior settings."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(parent, title="Endiginous desktop settings")
        self.settings = settings
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)

        self.startup = wx.CheckBox(panel, label="Start Endiginous when I sign in to this computer")
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


class UpdateInstallCountdown(wx.Dialog):
    """Give the user a visible, cancellable pause before update installation."""

    def __init__(self, parent: wx.Window, version: str, seconds: int = 5) -> None:
        super().__init__(parent, title="Endiginous update ready")
        self.remaining = max(1, seconds)
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        self.message = wx.StaticText(panel, label="")
        self.message.SetName("Update installation countdown")
        layout.Add(self.message, 0, wx.ALL, 12)
        cancel = wx.Button(panel, wx.ID_CANCEL, "Cancel update")
        layout.Add(cancel, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        panel.SetSizer(layout)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)
        self.message.SetLabel(f"Endiginous {version} will close and install the verified update in {self.remaining} seconds.")
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._tick, self.timer)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        cancel.SetFocus()
        self.timer.Start(1000)

    def _tick(self, _event: wx.TimerEvent) -> None:
        self.remaining -= 1
        if self.remaining <= 0:
            self.timer.Stop()
            self.EndModal(wx.ID_OK)
            return
        self.message.SetLabel(f"Endiginous will close and install the verified update in {self.remaining} seconds.")

    def _on_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.timer.Stop()
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


class MainFrame(wx.Frame):
    """Main native window and resilient WebView host."""

    def __init__(self, settings_store: SettingsStore, autostart: bool = False, launch_url: str | None = None) -> None:
        super().__init__(None, title=APP_NAME, size=(1120, 820))
        self.store = settings_store
        self.settings = settings_store.load()
        self.backoff = ReconnectBackoff(self.settings.reconnect_initial_seconds, self.settings.reconnect_max_seconds)
        self.reconnect_timer = wx.Timer(self)
        self.update_thread: threading.Thread | None = None
        self.browser_auth_flow: BrowserAuthFlow | None = None
        self.tray_icon: TrayIcon | None = None
        self.force_exit = False
        self.screen_reader = ScreenReaderSpeech()
        self.world_hotkeys_registered = False
        self.signed_in = False

        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)

        self.login_panel = wx.Panel(panel)
        login_layout = wx.BoxSizer(wx.VERTICAL)
        self.default_login = wx.Button(self.login_panel, label="&Sign in to Blind Software")
        login_layout.Add(self.default_login, 0, wx.EXPAND | wx.ALL, 8)
        domain_label = wx.StaticText(self.login_panel, label="Other Endiginous server domain:")
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
        self.SetStatusText("Starting Endiginous")
        self.Bind(wx.html2.EVT_WEBVIEW_LOADED, self._on_loaded, self.web)
        self.Bind(wx.html2.EVT_WEBVIEW_ERROR, self._on_error, self.web)
        self.Bind(wx.html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_script_message, self.web)
        self.Bind(wx.EVT_TIMER, self._on_reconnect_timer, self.reconnect_timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.web.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.default_login.Bind(wx.EVT_BUTTON, self._login_default)
        self.domain_login.Bind(wx.EVT_BUTTON, self._login_domain)
        self.domain.Bind(wx.EVT_TEXT_ENTER, self._login_domain)

        if launch_url:
            self._open_grid(launch_url)
        else:
            self._announce("Choose an Endiginous server and sign in.")
            self.default_login.SetFocus()
        if autostart and self.settings.start_minimized:
            self.Iconize(True)
        else:
            self.Show()
        if sys.platform == "win32":
            wx.CallAfter(self._set_world_hotkeys_active, True)
        wx.CallLater(5000, self._check_updates_background)

    def _build_menu(self) -> None:
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        self.browser_sign_in_id = wx.NewIdRef()
        self.browser_sign_in_item = file_menu.Append(
            self.browser_sign_in_id, "Sign in to &server\tCtrl+Shift+S"
        )
        file_menu.Append(wx.ID_REFRESH, "&Reconnect\tCtrl+R")
        self.focus_world_id = wx.NewIdRef()
        file_menu.Append(self.focus_world_id, "&Focus world\tF6")
        file_menu.AppendSeparator()
        settings_shortcut = "Cmd+," if sys.platform == "darwin" else "Ctrl+,"
        file_menu.Append(wx.ID_PREFERENCES, f"&Desktop settings...\t{settings_shortcut}")
        self.audio_settings_id = wx.NewIdRef()
        file_menu.Append(self.audio_settings_id, "&Audio setup...\tCtrl+Shift+A")
        self.cast_device_id = wx.NewIdRef()
        file_menu.Append(self.cast_device_id, "Cast to &device...\tCtrl+Shift+C")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_ABOUT, "&Credits and version\tCtrl+Shift+C")
        file_menu.Append(wx.ID_EXIT, "E&xit\tAlt+F4")
        menu_bar.Append(file_menu, "&File")
        self.SetMenuBar(menu_bar)
        self.Bind(wx.EVT_MENU, self._login_default, id=self.browser_sign_in_id)
        self.Bind(wx.EVT_MENU, lambda _event: self._reload(), id=wx.ID_REFRESH)
        self.Bind(wx.EVT_MENU, lambda _event: self._focus_world(), id=self.focus_world_id)
        self.Bind(wx.EVT_MENU, self._show_settings, id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, self._show_audio_settings, id=self.audio_settings_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.web.RunScript("window.dispatchEvent(new Event('chatgrid-cast-to-device'));"), id=self.cast_device_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.exit_application(), id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self._show_about, id=wx.ID_ABOUT)

        self.world_key_ids: dict[int, wx.WindowIDRef] = {
            wx.WXK_LEFT: wx.NewIdRef(),
            wx.WXK_RIGHT: wx.NewIdRef(),
            wx.WXK_UP: wx.NewIdRef(),
            wx.WXK_DOWN: wx.NewIdRef(),
        }
        accelerator_entries: list[wx.AcceleratorEntry] = []
        for key_code, command_id in self.world_key_ids.items():
            self.Bind(
                wx.EVT_MENU,
                lambda _event, forwarded=key_code: self._dispatch_world_arrow(forwarded),
                id=command_id,
            )
            accelerator_entries.append(wx.AcceleratorEntry(wx.ACCEL_NORMAL, key_code, command_id))
        if sys.platform != "win32":
            self.SetAcceleratorTable(wx.AcceleratorTable(accelerator_entries))
        else:
            self.Bind(wx.EVT_HOTKEY, self._on_world_hotkey)

    def _on_world_hotkey(self, event: wx.KeyEvent) -> None:
        """Map a registered Windows hotkey event back to its world direction."""
        event_id = event.GetId()
        for key_code, command_id in self.world_key_ids.items():
            if int(command_id) == event_id:
                self._dispatch_world_arrow(key_code)
                return

    def _set_world_hotkeys_active(self, active: bool) -> None:
        """Register arrows only while this foreground window owns the world."""
        if sys.platform != "win32":
            return
        should_register = active and self.IsActive() and self.web.IsShown()
        if should_register == self.world_hotkeys_registered:
            return
        if should_register:
            registered: list[int] = []
            windows_virtual_keys = {
                wx.WXK_LEFT: 0x25,
                wx.WXK_UP: 0x26,
                wx.WXK_RIGHT: 0x27,
                wx.WXK_DOWN: 0x28,
            }
            for key_code, command_id in self.world_key_ids.items():
                command = int(command_id)
                if ctypes.windll.user32.RegisterHotKey(
                    int(self.GetHandle()), command, 0, windows_virtual_keys[key_code]
                ):
                    registered.append(command)
                    continue
                for registered_id in registered:
                    ctypes.windll.user32.UnregisterHotKey(int(self.GetHandle()), registered_id)
                LOGGER.warning("Unable to register native world arrow hotkeys")
                return
            self.world_hotkeys_registered = True
            return
        for command_id in self.world_key_ids.values():
            ctypes.windll.user32.UnregisterHotKey(int(self.GetHandle()), int(command_id))
        self.world_hotkeys_registered = False

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        self._set_world_hotkeys_active(event.GetActive())
        event.Skip()

    def _announce(self, text: str) -> None:
        self.SetStatusText(text)

    @staticmethod
    def _server_url(value: str) -> str:
        """Return an HTTPS Endiginous URL for a user-entered domain."""
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
        parsed = urlsplit(url)
        incoming_query = parse_qsl(parsed.query, keep_blank_values=True)
        persisted_query = [
            (key, value)
            for key, value in incoming_query
            if key not in {"external_auth", "native_client"}
        ]
        self.settings.grid_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(persisted_query), "")
        )
        self.store.save(self.settings)
        self.login_panel.Hide()
        self.web.Show()
        self.web.GetParent().Layout()
        self._announce("Opening secure desktop sign-in.")
        navigation_query = [
            (key, value) for key, value in incoming_query if key != "native_client"
        ]
        navigation_query.append(("native_client", __version__))
        navigation_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(navigation_query), "")
        )
        self.web.LoadURL(navigation_url)
        self.web.SetFocus()

    def _login_default(self, _event: wx.CommandEvent) -> None:
        if self.signed_in:
            self.web.RunScript("document.getElementById('logoutButton')?.click();")
            return
        self._start_browser_auth("https://blind.software", "https://blind.software/chatgrid/")

    def _login_domain(self, _event: wx.CommandEvent) -> None:
        try:
            url = self._server_url(self.domain.GetValue())
        except (ValueError, OverflowError):
            self._announce("Enter a valid HTTPS server domain, such as example.com.")
            self.domain.SetFocus()
            return
        parsed = urlsplit(url)
        self._start_browser_auth(f"https://{parsed.netloc}", url)

    def _start_browser_auth(self, server_origin: str, grid_url: str) -> None:
        """Authenticate through the system browser and return to this running client."""
        if self.browser_auth_flow is not None:
            self._announce("Browser sign-in is already waiting for completion.")
            return
        try:
            flow = BrowserAuthFlow(server_origin, grid_url)
        except ValueError:
            self._announce("Enter a valid HTTPS Endiginous server before signing in.")
            return
        self.browser_auth_flow = flow
        self.default_login.Disable()
        self.domain_login.Disable()
        flow.start(
            lambda url, assertion: wx.CallAfter(self._finish_browser_auth, url, assertion),
            lambda message: wx.CallAfter(self._browser_auth_failed, message),
        )
        self._announce("Complete sign-in in the opened sign-in window. Endiginous will continue automatically.")
        if not webbrowser.open(flow.authorization_url, new=1):
            flow.close()
            self._browser_auth_failed("The system browser could not be opened. Try signing in again.")

    def _finish_browser_auth(self, grid_url: str, assertion: str) -> None:
        """Load the one-use assertion into the embedded world client."""
        self.browser_auth_flow = None
        self.default_login.Enable()
        self.domain_login.Enable()
        separator = "&" if "?" in grid_url else "?"
        self._open_grid(grid_url + separator + urlencode({"external_auth": assertion}))

    def _browser_auth_failed(self, message: str) -> None:
        self.browser_auth_flow = None
        self.default_login.Enable()
        self.domain_login.Enable()
        self._announce(message)
        self.default_login.SetFocus()

    def _on_loaded(self, _event: wx.html2.WebViewEvent) -> None:
        self.reconnect_timer.Stop()
        self.backoff.reset()
        self._announce("Endiginous loaded. Session and reconnect monitoring are active.")
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
            "style.textContent='#gridTitle,#connectionStatus,#authSessionView,#button-container,"
            "#deviceSummary,#joinGuide,#appFooter{display:none!important}';"
            "document.head.appendChild(style);}"
            "const canvas=document.getElementById('gameCanvas');"
            "if(canvas){canvas.setAttribute('role','application');"
            "canvas.setAttribute('aria-roledescription','interactive audio world');"
            "const focusWorld=()=>{if(!canvas.classList.contains('hidden')){"
            "canvas.focus({preventScroll:true});}};focusWorld();"
            "new MutationObserver(focusWorld).observe(canvas,{attributes:true,attributeFilter:['class']});}"
            "const logout=document.getElementById('logoutButton');"
            "if(logout){const notifyAuth=()=>window.chrome?.webview?.postMessage(JSON.stringify({"
            "type:'authState',signedIn:!logout.classList.contains('hidden')&&!logout.disabled}));"
            "notifyAuth();new MutationObserver(notifyAuth).observe(logout,{attributes:true,"
            "attributeFilter:['class','disabled']});}})();"
        )
        self.web.RunScript(spatial_audio_script(self.settings.spatial_audio))
        self._set_world_hotkeys_active(True)

    def _on_script_message(self, event: wx.html2.WebViewEvent) -> None:
        """Accept bounded native integration messages from the approved origin."""
        expected = urlsplit(self.settings.grid_url)
        current = urlsplit(self.web.GetCurrentURL())
        if current.scheme != "https" or current.netloc != expected.netloc:
            return
        try:
            message = json.loads(event.GetString())
        except (TypeError, ValueError):
            return
        if message.get("type") == "authState":
            self._set_signed_in(bool(message.get("signedIn")))
            return
        if message.get("type") != "speak" or not isinstance(message.get("text"), str):
            return
        self.screen_reader.speak(message["text"], bool(message.get("interrupt")))

    def _set_signed_in(self, signed_in: bool) -> None:
        """Keep the File menu authentication action aligned with web session state."""
        self.signed_in = signed_in
        label = "Sign &out\tCtrl+Shift+S" if signed_in else "Sign in to &server\tCtrl+Shift+S"
        self.browser_sign_in_item.SetItemLabel(label)

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
            self._announce("Sign in to an Endiginous server before opening audio setup.")
            self.default_login.SetFocus()
            return
        self.web.RunScript("document.getElementById('settingsButton')?.click();")
        self.web.SetFocus()

    def _focus_world(self) -> None:
        """Place browser and DOM focus on the interactive world surface."""
        if not self.web.IsShown():
            self._announce("Sign in before focusing the world.")
            self.default_login.SetFocus()
            return
        self.web.SetFocus()
        self.web.RunScript(
            "document.getElementById('gameCanvas')?.focus({preventScroll:true});"
        )
        self._announce("World focused. Arrow keys move your character.")

    def _dispatch_world_arrow(self, key_code: int) -> None:
        """Forward one native arrow-key step into the embedded world."""
        world_keys = {
            wx.WXK_LEFT: ("ArrowLeft", "ArrowLeft"),
            wx.WXK_RIGHT: ("ArrowRight", "ArrowRight"),
            wx.WXK_UP: ("ArrowUp", "ArrowUp"),
            wx.WXK_DOWN: ("ArrowDown", "ArrowDown"),
        }
        mapped = world_keys.get(key_code)
        if not mapped or not self.web.IsShown():
            return
        key, code = mapped
        LOGGER.info("Forwarding native world key %s", code)
        success, result = self.web.RunScript(
            f"window.chatGridNativeKey?.({json.dumps(code)});"
        )
        LOGGER.info("Native world key result success=%s result=%s", success, result)

    def _check_updates_background(self, interactive: bool = False) -> None:
        if self.update_thread and self.update_thread.is_alive():
            return

        def worker() -> None:
            try:
                service = UpdateService(self.settings.update_url, __version__, app_data_dir())
                manifest = service.check()
                if manifest is None:
                    if interactive:
                        wx.CallAfter(self._announce, "Endiginous is up to date.")
                    return
                installer = service.download(manifest)
                wx.CallAfter(self._prepare_update_install, service, installer, manifest)
            except Exception as error:
                LOGGER.warning("Update check failed: %s", error)
                if interactive:
                    wx.CallAfter(self._announce, "Update check failed. The current app will keep running.")

        self.update_thread = threading.Thread(target=worker, name="chat-grid-updater", daemon=True)
        self.update_thread.start()

    def _prepare_update_install(self, service: UpdateService, installer: Path, manifest: object) -> None:
        """Show the countdown on the UI thread before closing for installation."""
        version = str(getattr(manifest, "version", "the update"))
        self._announce(f"Endiginous {version} is verified and ready to install.")
        with UpdateInstallCountdown(self, version) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                self._announce("Update cancelled. Endiginous will keep running.")
                return
        service.install_after_exit(installer, manifest)
        self.exit_application()

    def _show_about(self, _event: wx.CommandEvent) -> None:
        wx.MessageBox(
            f"Endiginous {__version__}\nOfficial accessible desktop client by Raywonder / TappedIn.",
            "About Endiginous", wx.OK | wx.ICON_INFORMATION, self,
        )
        if self.web.IsShown():
            self.web.SetFocus()
        else:
            self.default_login.SetFocus()

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        unicode_key = event.GetUnicodeKey()
        if (event.ControlDown() or event.MetaDown()) and (key == ord(",") or unicode_key == ord(",")):
            self._show_settings(event)
            return
        if key == wx.WXK_ALT:
            self._open_file_menu()
            return
        if key in self.world_key_ids and not (
            event.ControlDown() or event.AltDown() or event.MetaDown()
        ):
            self._dispatch_world_arrow(event.GetKeyCode())
            return
        if key == wx.WXK_ESCAPE and self.IsIconized():
            self.Iconize(False)
            self.Raise()
            return
        event.Skip()

    def _open_file_menu(self) -> None:
        """Open File when WebView2 consumes the standalone Alt key."""
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.SendMessageW(int(self.GetHandle()), 0x0112, 0xF100 | ord("f"), 0)
                return
            except (AttributeError, OSError):
                LOGGER.debug("Native File-menu activation was unavailable", exc_info=True)
        menu_bar = self.GetMenuBar()
        if menu_bar is not None:
            menu_bar.SetFocus()

    def _on_close(self, event: wx.CloseEvent) -> None:
        if self.settings.keep_in_tray and not self.force_exit and event.CanVeto():
            event.Veto()
            self._set_world_hotkeys_active(False)
            self.Hide()
            if self.tray_icon is None:
                self.tray_icon = TrayIcon(self)
            self._announce("Endiginous is still connected and running in the background.")
            return
        self.reconnect_timer.Stop()
        self._set_world_hotkeys_active(False)
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
        wx.CallAfter(self._set_world_hotkeys_active, True)
        self._announce("Endiginous window restored. You remained signed in.")

    def exit_application(self) -> None:
        """Fully stop Endiginous, including any background session."""
        self._prepare_exit()

    def _prepare_exit(self) -> None:
        self._announce("Endiginous will exit after the countdown.")
        with UpdateInstallCountdown(self, "exit Endiginous") as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                self._announce("Exit cancelled. Endiginous will keep running.")
                return
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
