"""Accessible wxPython shell around the shared Endiginous client."""

from __future__ import annotations

import logging
import json
import ctypes
import os
from pathlib import Path
import sys
import threading

import wx
import wx.adv
import wx.html2

from . import __version__
from .config import APP_ID, APP_NAME, Settings, SettingsStore, app_data_dir
from .reconnect import ReconnectBackoff
from .single_instance import SingleInstanceActivation
from .startup import set_start_with_windows
from .updater import UpdateService


LOGGER = logging.getLogger(__name__)


class EndiginousTrayIcon(wx.adv.TaskBarIcon):
    """System-tray access to the one running Endiginous window."""

    def __init__(self, frame: "MainFrame") -> None:
        super().__init__()
        self.frame = frame
        bitmap = wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, (16, 16))
        icon = wx.Icon()
        icon.CopyFromBitmap(bitmap)
        self.SetIcon(icon, "Endiginous")
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, lambda _event: frame.show_from_tray())
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, lambda _event: frame.show_from_tray())

    def CreatePopupMenu(self) -> wx.Menu:
        """Build the tray menu each time Windows requests it."""
        menu = wx.Menu()
        open_id = wx.NewIdRef()
        reconnect_id = wx.NewIdRef()
        quit_id = wx.NewIdRef()
        menu.Append(open_id, "Open Endiginous")
        menu.Append(reconnect_id, "Reconnect Endiginous")
        menu.AppendSeparator()
        menu.Append(quit_id, "Quit Endiginous")
        self.Bind(wx.EVT_MENU, lambda _event: self.frame.show_from_tray(), id=open_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.frame.reload_from_tray(), id=reconnect_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.frame.request_exit(), id=quit_id)
        return menu


class SettingsDialog(wx.Dialog):
    """Accessible desktop behavior settings."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(parent, title="Endiginous desktop settings")
        self.settings = settings
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)

        self.startup = wx.CheckBox(panel, label="Start Endiginous when I sign in to Windows")
        self.startup.SetValue(settings.start_with_windows)
        layout.Add(self.startup, 0, wx.ALL, 8)
        self.minimized = wx.CheckBox(panel, label="Start minimized when Windows starts")
        self.minimized.SetValue(settings.start_minimized)
        layout.Add(self.minimized, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.connect = wx.CheckBox(panel, label="Connect automatically after sign-in")
        self.connect.SetValue(settings.auto_connect)
        layout.Add(self.connect, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.updates = wx.CheckBox(panel, label="Check for and install verified updates automatically")
        self.updates.SetValue(settings.auto_update)
        layout.Add(self.updates, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.keep_tray = wx.CheckBox(panel, label="Keep Endiginous running in the background when I close the window")
        self.keep_tray.SetValue(getattr(settings, "keep_in_tray", False))
        layout.Add(self.keep_tray, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.spatial_audio = wx.CheckBox(panel, label="Use binaural spatial audio for world sounds")
        self.spatial_audio.SetValue(getattr(settings, "spatial_audio", True))
        layout.Add(self.spatial_audio, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.audio_summary = wx.StaticText(panel, label="Audio device selection and detailed audio controls are available in File > Settings.")
        self.audio_summary.SetName("Audio settings guidance")
        layout.Add(self.audio_summary, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(layout)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)
        self.startup.SetFocus()

    def _on_ok(self, _event: wx.CommandEvent) -> None:
        self.apply()
        self.EndModal(wx.ID_OK)

    def _on_cancel(self, _event: wx.CommandEvent) -> None:
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
        self.settings.auto_update = self.updates.GetValue()
        self.settings.keep_in_tray = self.keep_tray.GetValue()
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
        self.message.SetLabel(
            f"Endiginous will close and install the verified update in {self.remaining} seconds."
        )

    def _on_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.timer.Stop()
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


class MainFrame(wx.Frame):
    """Main native window and resilient WebView host."""

    def __init__(self, settings_store: SettingsStore, autostart: bool = False) -> None:
        super().__init__(None, title=APP_NAME, size=(1120, 820))
        self.store = settings_store
        self.settings = settings_store.load()
        self.backoff = ReconnectBackoff(self.settings.reconnect_initial_seconds, self.settings.reconnect_max_seconds)
        self.reconnect_timer = wx.Timer(self)
        self.update_thread: threading.Thread | None = None
        self.force_quit = False
        self.panel: wx.Panel | None = None
        self.layout: wx.BoxSizer | None = None

        self.panel = wx.Panel(self)
        self.layout = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(self.panel, label="Starting Endiginous.")
        self.status.SetName("Endiginous status")
        self.layout.Add(self.status, 0, wx.EXPAND | wx.ALL, 6)
        self.web = self._create_webview()
        self.layout.Add(self.web, 1, wx.EXPAND)
        self.panel.SetSizer(self.layout)

        self._build_menu()
        self.CreateStatusBar()
        self.SetStatusText("Starting Endiginous")
        self.Bind(wx.EVT_TIMER, self._on_reconnect_timer, self.reconnect_timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_ICONIZE, self._on_iconize)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        self.web.LoadURL(self.settings.grid_url)
        if autostart and self.settings.start_minimized:
            self.Iconize(True)
        else:
            self.Show()
        if self.settings.auto_update:
            wx.CallLater(5000, self._check_updates_background)

    def _build_menu(self) -> None:
        """Create a conventional, fully keyboard-accessible native menu bar."""
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        reconnect_id = wx.NewIdRef()
        restart_world_id = wx.NewIdRef()
        focus_world_id = wx.NewIdRef()
        tray_id = wx.NewIdRef()
        file_menu.Append(reconnect_id, "&Reconnect to world", "Reconnect without opening another client")
        file_menu.Append(restart_world_id, "&Restart frozen world view\tCtrl+Shift+R", "Replace only the embedded world view")
        file_menu.Append(focus_world_id, "&Focus world\tCtrl+L", "Move keyboard focus into the world")
        file_menu.AppendSeparator()
        settings_shortcut = "Cmd+," if sys.platform == "darwin" else "Ctrl+,"
        file_menu.Append(wx.ID_PREFERENCES, f"&Settings...\t{settings_shortcut}")
        cast_id = wx.NewIdRef()
        file_menu.Append(cast_id, "Cast to &device...\tCtrl+Shift+C")
        file_menu.Append(tray_id, "&Minimize to system tray\tCtrl+M")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "E&xit Endiginous\tAlt+F4")
        menu_bar.Append(file_menu, "&File")
        help_menu = wx.Menu()
        update_id = wx.NewIdRef()
        help_menu.Append(update_id, "Check for &updates")
        help_menu.Append(wx.ID_ABOUT, "&About Endiginous")
        menu_bar.Append(help_menu, "&Help")
        self.SetMenuBar(menu_bar)
        self.Bind(wx.EVT_MENU, lambda _event: self._reload(), id=reconnect_id)
        self.Bind(wx.EVT_MENU, lambda _event: self._restart_webview(), id=restart_world_id)
        self.Bind(wx.EVT_MENU, lambda _event: self._focus_world(), id=focus_world_id)
        self.Bind(wx.EVT_MENU, self._show_settings, id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, lambda _event: self.web.RunScript("window.dispatchEvent(new Event('chatgrid-cast-to-device'));"), id=cast_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.Hide(), id=tray_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.request_exit(), id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, lambda _event: self._check_updates_background(interactive=True), id=update_id)
        self.Bind(wx.EVT_MENU, self._show_about, id=wx.ID_ABOUT)

    def _create_webview(self) -> wx.html2.WebView:
        """Create and bind one replaceable Edge WebView world surface."""
        assert self.panel is not None
        try:
            web = wx.html2.WebView.New(self.panel, backend=wx.html2.WebViewBackendEdge)
            if not web:
                raise RuntimeError("Edge WebView2 backend returned no window")
            LOGGER.info("Using Edge WebView2 backend")
        except Exception:
            # Some otherwise supported Windows systems have an absent, damaged,
            # or incompatible WebView2 runtime.  Do not let that close the whole
            # native shell before the user can reach its accessible File menu.
            LOGGER.exception("Edge WebView2 initialization failed; using default backend")
            web = wx.html2.WebView.New(self.panel)
            if not web:
                raise RuntimeError("No usable wx.html2 WebView backend is installed")
            LOGGER.info("Using default wx.html2 WebView backend")
        web.SetName("Endiginous world")
        web.Bind(wx.html2.EVT_WEBVIEW_LOADED, self._on_loaded)
        web.Bind(wx.html2.EVT_WEBVIEW_ERROR, self._on_error)
        return web

    def _restart_webview(self) -> None:
        """Replace a stalled renderer while leaving the native app usable."""
        assert self.layout is not None
        old_web = self.web
        self._announce("Restarting the world view. The native File menu remains available.")
        self.layout.Detach(old_web)
        old_web.Destroy()
        self.web = self._create_webview()
        self.layout.Add(self.web, 1, wx.EXPAND)
        self.layout.Layout()
        self.web.LoadURL(self.settings.grid_url)
        self.web.SetFocus()

    def _announce(self, text: str) -> None:
        self.status.SetLabel(text)
        self.SetStatusText(text)

    def _on_loaded(self, _event: wx.html2.WebViewEvent) -> None:
        self.reconnect_timer.Stop()
        self.backoff.reset()
        self._announce("Endiginous loaded. Session and reconnect monitoring are active.")
        if self.settings.auto_connect:
            self.web.RunScript("setTimeout(() => document.getElementById('connectButton')?.click(), 500);")
        # Native WebView focus alone does not activate the web world's
        # application-level keyboard contract.  Activate the same accessible
        # control that browser users select so movement, chat, and item keys
        # are ready when the desktop world receives focus.
        self.web.RunScript(
            "(() => {"
            "let attempts = 0;"
            "const activate = () => {"
            "const button = document.getElementById('focusGridButton');"
            "if (button && !button.classList.contains('hidden')) { button.click(); return; }"
            "if (++attempts < 80) setTimeout(activate, 250);"
            "};"
            "activate();"
            "})();"
        )
        wx.CallLater(1000, self.web.SetFocus)

    def _focus_world(self) -> None:
        """Activate web world controls and move native focus into the renderer."""
        self.web.RunScript("document.getElementById('focusGridButton')?.click();")
        self.web.SetFocus()

    def _dispatch_world_shortcut(self, code: str, *, ctrl: bool = False, shift: bool = False) -> None:
        """Forward a native-only shortcut into the embedded world command profile."""
        options = json.dumps({"ctrlKey": ctrl, "shiftKey": shift})
        self.web.RunScript(f"window.chatGridNativeKey?.({json.dumps(code)}, {options});")

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
        try:
            self.web.Reload(wx.html2.WEBVIEW_RELOAD_NO_CACHE)
        except Exception:
            LOGGER.exception("WebView reload failed; replacing the renderer")
            self._restart_webview()

    def show_from_tray(self) -> None:
        """Restore, raise, and focus the existing accessible window."""
        if self.IsIconized():
            self.Iconize(False)
        self.Show(True)
        self.Raise()
        self.RequestUserAttention(wx.USER_ATTENTION_INFO)
        self.web.SetFocus()

    def reload_from_tray(self) -> None:
        """Recover the existing WebView without launching another application."""
        self.show_from_tray()
        self._reload()

    def request_exit(self) -> None:
        """Explicitly quit instead of applying close-to-tray behavior."""
        self._prepare_exit()

    def _prepare_exit(self) -> None:
        self._announce("Endiginous will exit after the countdown.")
        with UpdateInstallCountdown(self, "exit Endiginous") as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                self._announce("Exit cancelled. Endiginous will keep running.")
                return
        self.force_quit = True
        self.Close()

    def _on_iconize(self, event: wx.IconizeEvent) -> None:
        if event.IsIconized():
            wx.CallAfter(self.Hide)
        event.Skip()

    def _show_settings(self, _event: wx.CommandEvent) -> None:
        with SettingsDialog(self, self.settings) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            dialog.apply()
            self.store.save(self.settings)
            set_start_with_windows(self.settings.start_with_windows)
            self.web.RunScript(
                "window.chatGridNativeApplyAudioSettings?.(" + json.dumps({
                    "outputMode": self.settings.audio_output_mode,
                    "masterVolume": self.settings.master_volume,
                    "microphoneGain": self.settings.microphone_gain,
                    "layers": {"voice": self.settings.voice_layer, "item": self.settings.item_layer, "media": self.settings.media_layer, "world": self.settings.world_layer},
                    "announcementMode": self.settings.announcement_mode,
                    "radioAnnouncementMode": self.settings.radio_announcement_mode,
                    "itemBeacons": self.settings.item_beacons,
                    "movementDirections": self.settings.movement_directions,
                }) + ");"
            )
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
                        wx.CallAfter(self._announce, "Endiginous is up to date.")
                    return
                if not interactive and service.is_dismissed(manifest):
                    return
                if not self.settings.auto_update and not interactive:
                    wx.CallAfter(self._announce, f"Endiginous {manifest.version} is available.")
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
                service.dismiss(manifest)
                self._announce("Update cancelled. Endiginous will keep running.")
                return
        service.install_after_exit(installer, manifest)
        self.force_quit = True
        self.Close()

    def _show_about(self, _event: wx.CommandEvent) -> None:
        wx.MessageBox(
            f"Endiginous {__version__}\nOfficial accessible Windows client by Raywonder / TappedIn.",
            "About Endiginous", wx.OK | wx.ICON_INFORMATION, self,
        )

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        unicode_key = event.GetUnicodeKey()
        if (event.ControlDown() or event.MetaDown()) and (key == ord(",") or unicode_key == ord(",")):
            self._show_settings(event)
            return
        if (event.ControlDown() or event.MetaDown()) and not event.AltDown() and (
            key == ord("R") or key == ord("r") or unicode_key == ord("R") or unicode_key == ord("r")
        ):
            self._dispatch_world_shortcut("KeyR", ctrl=True)
            return
        if key == wx.WXK_ALT:
            self._open_file_menu()
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
        if event.CanVeto() and not self.force_quit:
            event.Veto()
            self.Hide()
            return
        self.reconnect_timer.Stop()
        event.Skip()


class EndiginousApp(wx.App):
    """Application entry point."""

    def __init__(self, activation: SingleInstanceActivation) -> None:
        self.activation = activation
        super().__init__(False)

    def OnInit(self) -> bool:
        os.environ.setdefault("WEBVIEW2_USER_DATA_FOLDER", str(app_data_dir() / "WebView2"))
        # GPU/driver failures can freeze an older Windows machine. Software
        # rendering costs a little performance but keeps the desktop responsive.
        os.environ.setdefault(
            "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
            "--disable-gpu --disable-gpu-compositing --disable-background-networking",
        )
        autostart = "--autostart" in sys.argv
        self.frame = MainFrame(SettingsStore(), autostart=autostart)
        self.tray = EndiginousTrayIcon(self.frame)
        self.activation_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_activation_timer, self.activation_timer)
        self.activation_timer.Start(250)
        self.SetTopWindow(self.frame)
        return True

    def _on_activation_timer(self, _event: wx.TimerEvent) -> None:
        if self.activation.activation_requested():
            self.frame.show_from_tray()

    def OnExit(self) -> int:
        self.activation_timer.Stop()
        self.tray.RemoveIcon()
        self.tray.Destroy()
        self.activation.close()
        return super().OnExit()


def main() -> int:
    """Start the GUI."""
    root = app_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=root / "chat-grid.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    activation = SingleInstanceActivation()
    if not activation.is_owner:
        return 0
    try:
        LOGGER.info("Starting Endiginous %s on Python %s", __version__, sys.version)
        app = EndiginousApp(activation)
        app.MainLoop()
        return 0
    except Exception:
        LOGGER.exception("Fatal desktop startup failure")
        try:
            wx.MessageBox(
                "Endiginous could not start. A diagnostic log was saved to "
                f"{root / 'chat-grid.log'}.",
                "Endiginous startup error",
                wx.OK | wx.ICON_ERROR,
            )
        except Exception:
            pass
        return 1
