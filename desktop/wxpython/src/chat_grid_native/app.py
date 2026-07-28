"""Accessible wxPython shell around the shared Indiginous client."""

from __future__ import annotations

import logging
import json
import os
from pathlib import Path
import sys
import threading
import webbrowser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import wx
import wx.adv
import wx.html2

from . import __version__
from .config import APP_ID, APP_NAME, Settings, SettingsStore, app_data_dir
from .browser_auth import BrowserAuthFlow
from .reconnect import ReconnectBackoff
from .single_instance import SingleInstanceActivation
from .startup import set_start_with_windows
from .updater import UpdateService
from .migration import migrate_legacy_state


LOGGER = logging.getLogger(__name__)


class IndiginousTrayIcon(wx.adv.TaskBarIcon):
    """System-tray access to the one running Indiginous window."""

    def __init__(self, frame: "MainFrame") -> None:
        super().__init__()
        self.frame = frame
        bitmap = wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, (16, 16))
        icon = wx.Icon()
        icon.CopyFromBitmap(bitmap)
        self.SetIcon(icon, "Indiginous")
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, lambda _event: frame.show_from_tray())
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, lambda _event: frame.show_from_tray())

    def CreatePopupMenu(self) -> wx.Menu:
        """Build the tray menu each time Windows requests it."""
        menu = wx.Menu()
        open_id = wx.NewIdRef()
        reconnect_id = wx.NewIdRef()
        settings_id = wx.NewIdRef()
        signin_id = wx.NewIdRef()
        updates_id = wx.NewIdRef()
        website_id = wx.NewIdRef()
        about_id = wx.NewIdRef()
        quit_id = wx.NewIdRef()
        menu.Append(open_id, "&Open Indiginous")
        menu.Append(reconnect_id, "&Reconnect Indiginous")
        menu.AppendSeparator()
        menu.Append(settings_id, "&Settings...")
        if not self.frame.is_signed_in:
            signin_id = wx.NewIdRef()
            menu.Append(signin_id, "Sign in to &Indiginous")
        menu.Append(updates_id, "Check for &updates")
        menu.AppendSeparator()
        menu.Append(website_id, "Open Indiginous &website")
        menu.Append(about_id, "&About Indiginous")
        menu.AppendSeparator()
        menu.Append(quit_id, "&Quit Indiginous")
        # Bind on the transient menu rather than the tray object.  Windows
        # asks for a fresh popup menu each time; binding on the tray would
        # accumulate handlers and repeat actions after several openings.
        menu.Bind(wx.EVT_MENU, lambda _event: self.frame.show_from_tray(), id=open_id)
        menu.Bind(wx.EVT_MENU, lambda _event: self.frame.reload_from_tray(), id=reconnect_id)
        menu.Bind(wx.EVT_MENU, lambda _event: self.frame._show_settings(_event), id=settings_id)
        if not self.frame.is_signed_in:
            menu.Bind(wx.EVT_MENU, lambda _event: self.frame._login_default(), id=signin_id)
        menu.Bind(wx.EVT_MENU, lambda _event: self.frame._check_updates_background(interactive=True), id=updates_id)
        menu.Bind(wx.EVT_MENU, lambda _event: self.frame._open_external_url("https://blind.software/indiginous/"), id=website_id)
        menu.Bind(wx.EVT_MENU, lambda _event: self.frame._show_about(_event), id=about_id)
        menu.Bind(wx.EVT_MENU, lambda _event: self.frame.request_exit(), id=quit_id)
        return menu


class SettingsDialog(wx.Dialog):
    """Accessible desktop behavior settings."""

    def __init__(self, parent: wx.Window, settings: Settings, audio_devices: dict[str, list[tuple[str, str]]] | None = None) -> None:
        super().__init__(parent, title="Indiginous desktop settings")
        self.settings = settings
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)

        self.startup = wx.CheckBox(panel, label="Start Indiginous when I sign in to Windows")
        self.startup.SetValue(settings.start_with_windows)
        layout.Add(self.startup, 0, wx.ALL, 8)
        self.minimized = wx.CheckBox(panel, label="Start minimized when Windows starts")
        self.minimized.SetValue(settings.start_minimized)
        layout.Add(self.minimized, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.connect = wx.CheckBox(panel, label="Connect automatically after sign-in")
        self.connect.SetValue(settings.auto_connect)
        layout.Add(self.connect, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.updates = wx.CheckBox(panel, label="Check for and install verified Indiginous updates automatically")
        self.updates.SetValue(settings.auto_update)
        layout.Add(self.updates, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.keep_tray = wx.CheckBox(panel, label="Keep Indiginous running in the background when I close the window")
        self.keep_tray.SetValue(getattr(settings, "keep_in_tray", False))
        layout.Add(self.keep_tray, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.spatial_audio = wx.CheckBox(panel, label="Use binaural spatial audio for world sounds")
        self.spatial_audio.SetValue(getattr(settings, "spatial_audio", True))
        layout.Add(self.spatial_audio, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        audio_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Audio")
        self.audio_input = wx.Choice(panel, choices=["Default microphone"])
        self.audio_input.SetName("Microphone input device")
        self.audio_output = wx.Choice(panel, choices=["Default speakers"])
        self.audio_output.SetName("Speakers output device")
        audio_box.Add(wx.StaticText(panel, label="Microphone (input device)"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        audio_box.Add(self.audio_input, 0, wx.EXPAND | wx.ALL, 6)
        audio_box.Add(wx.StaticText(panel, label="Speakers (output device)"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        audio_box.Add(self.audio_output, 0, wx.EXPAND | wx.ALL, 6)
        self.output_mode = wx.Choice(panel, choices=["Stereo", "Mono"])
        self.output_mode.SetName("Audio output mode")
        self.output_mode.SetSelection(0 if settings.audio_output_mode != "mono" else 1)
        audio_box.Add(wx.StaticText(panel, label="Output mode"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        audio_box.Add(self.output_mode, 0, wx.EXPAND | wx.ALL, 6)
        self.master_volume = wx.Slider(panel, value=int(settings.master_volume), minValue=0, maxValue=100, style=wx.SL_HORIZONTAL)
        self.master_volume.SetName("Master volume")
        audio_box.Add(wx.StaticText(panel, label="Master volume"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        audio_box.Add(self.master_volume, 0, wx.EXPAND | wx.ALL, 6)
        self.microphone_gain = wx.Slider(panel, value=int(round(settings.microphone_gain * 100)), minValue=0, maxValue=500, style=wx.SL_HORIZONTAL)
        self.microphone_gain.SetName("Microphone gain")
        audio_box.Add(wx.StaticText(panel, label="Microphone gain"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        audio_box.Add(self.microphone_gain, 0, wx.EXPAND | wx.ALL, 6)
        self.voice_layer = wx.CheckBox(panel, label="Voice layer")
        self.item_layer = wx.CheckBox(panel, label="Item sounds")
        self.media_layer = wx.CheckBox(panel, label="Media audio")
        self.world_layer = wx.CheckBox(panel, label="World audio")
        for control, value in ((self.voice_layer, settings.voice_layer), (self.item_layer, settings.item_layer), (self.media_layer, settings.media_layer), (self.world_layer, settings.world_layer)):
            control.SetValue(value)
            audio_box.Add(control, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        self.announcement_mode = wx.Choice(panel, choices=["Speak announcements and play alert sounds", "Alert sounds only", "Required announcements only"])
        self.announcement_mode.SetSelection({"full": 0, "sounds_only": 1, "required_only": 2}.get(settings.announcement_mode, 0))
        audio_box.Add(wx.StaticText(panel, label="TTS announcements"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        audio_box.Add(self.announcement_mode, 0, wx.EXPAND | wx.ALL, 6)
        self.radio_announcement_mode = wx.Choice(panel, choices=["Speak station changes and readouts", "Sounds only", "Off"])
        self.radio_announcement_mode.SetSelection({"full": 0, "sounds_only": 1, "off": 2}.get(settings.radio_announcement_mode, 0))
        audio_box.Add(wx.StaticText(panel, label="Radio station readouts"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        audio_box.Add(self.radio_announcement_mode, 0, wx.EXPAND | wx.ALL, 6)
        self.item_beacons = wx.CheckBox(panel, label="Item beacons near me")
        self.item_beacons.SetValue(settings.item_beacons)
        audio_box.Add(self.item_beacons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        self.movement_directions = wx.CheckBox(panel, label="Speak movement directions and nearby-user movement")
        self.movement_directions.SetValue(settings.movement_directions)
        audio_box.Add(self.movement_directions, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        layout.Add(audio_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(layout)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)
        self.SetAffirmativeId(wx.ID_OK)
        self.SetEscapeId(wx.ID_CANCEL)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)
        self.set_audio_devices(audio_devices or {})
        self.startup.SetFocus()

    def set_audio_devices(self, devices: dict[str, list[tuple[str, str]]]) -> None:
        """Refresh native input/output choices from the embedded browser."""
        for control, key, default_label, saved_id in (
            (self.audio_input, "inputs", "Default microphone", self.settings.audio_input_device_id),
            (self.audio_output, "outputs", "Default speakers", self.settings.audio_output_device_id),
        ):
            control.Freeze()
            control.Clear()
            control.Append(default_label, "")
            for device_id, label in devices.get(key, []):
                control.Append(label or default_label, device_id)
            index = next((i for i in range(control.GetCount()) if control.GetClientData(i) == saved_id), 0)
            control.SetSelection(index)
            control.Thaw()

    def _on_ok(self, _event: wx.CommandEvent) -> None:
        self.apply()
        self.SetReturnCode(wx.ID_OK)
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
        self.settings.audio_output_mode = "mono" if self.output_mode.GetSelection() == 1 else "stereo"
        input_index = self.audio_input.GetSelection()
        output_index = self.audio_output.GetSelection()
        self.settings.audio_input_device_id = str(self.audio_input.GetClientData(input_index) or "") if input_index != wx.NOT_FOUND else ""
        self.settings.audio_input_device_name = self.audio_input.GetString(input_index) if input_index != wx.NOT_FOUND else ""
        self.settings.audio_output_device_id = str(self.audio_output.GetClientData(output_index) or "") if output_index != wx.NOT_FOUND else ""
        self.settings.audio_output_device_name = self.audio_output.GetString(output_index) if output_index != wx.NOT_FOUND else ""
        self.settings.master_volume = self.master_volume.GetValue()
        self.settings.microphone_gain = self.microphone_gain.GetValue() / 100.0
        self.settings.voice_layer = self.voice_layer.GetValue()
        self.settings.item_layer = self.item_layer.GetValue()
        self.settings.media_layer = self.media_layer.GetValue()
        self.settings.world_layer = self.world_layer.GetValue()
        self.settings.announcement_mode = ("full", "sounds_only", "required_only")[self.announcement_mode.GetSelection()]
        self.settings.radio_announcement_mode = ("full", "sounds_only", "off")[self.radio_announcement_mode.GetSelection()]
        self.settings.item_beacons = self.item_beacons.GetValue()
        self.settings.movement_directions = self.movement_directions.GetValue()


class UpdateInstallCountdown(wx.Dialog):
    """Give the user a visible, cancellable pause before update installation."""

    def __init__(self, parent: wx.Window, version: str, seconds: int = 5) -> None:
        super().__init__(parent, title="Indiginous update ready")
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
        self.message.SetLabel(f"Indiginous {version} will close and install the verified update in {self.remaining} seconds.")
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
            f"Indiginous will close and install the verified update in {self.remaining} seconds."
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
        self.browser_auth_flow: BrowserAuthFlow | None = None
        self.auto_browser_auth_call: wx.CallLater | None = None
        self.pending_external_auth = False
        self.is_signed_in = False
        self.settings_dialog: SettingsDialog | None = None
        self.audio_devices: dict[str, list[tuple[str, str]]] = {"inputs": [], "outputs": []}
        self.world_focus_restore: wx.CallLater | None = None
        self.force_quit = False
        self.panel: wx.Panel | None = None
        self.layout: wx.BoxSizer | None = None

        self.panel = wx.Panel(self)
        self.layout = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(self.panel, label="Starting Indiginous.")
        self.status.SetName("Indiginous status")
        self.layout.Add(self.status, 0, wx.EXPAND | wx.ALL, 6)
        self.web = self._create_webview()
        self.layout.Add(self.web, 1, wx.EXPAND)
        self.panel.SetSizer(self.layout)

        self._build_menu()
        self.CreateStatusBar()
        self.SetStatusText("Starting Indiginous")
        self.Bind(wx.EVT_TIMER, self._on_reconnect_timer, self.reconnect_timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_ICONIZE, self._on_iconize)
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        self._load_grid(self.settings.grid_url)
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
        signin_id = wx.NewIdRef()
        tray_id = wx.NewIdRef()
        file_menu.Append(reconnect_id, "&Reconnect to world", "Reconnect without opening another client")
        file_menu.Append(restart_world_id, "&Restart frozen world view\tCtrl+Shift+R", "Replace only the embedded world view")
        file_menu.Append(focus_world_id, "&Focus world\tCtrl+L", "Move keyboard focus into the world")
        file_menu.AppendSeparator()
        self.signin_menu_item = file_menu.Append(signin_id, "Sign in to &Indiginous\tCtrl+Shift+S", "Open the Indiginous sign-in page")
        settings_shortcut = "Cmd+Alt+," if sys.platform == "darwin" else "Ctrl+Alt+,"
        file_menu.Append(wx.ID_PREFERENCES, f"&Settings...\t{settings_shortcut}")
        cast_id = wx.NewIdRef()
        file_menu.Append(cast_id, "Cast to &device...\tCtrl+Shift+C")
        file_menu.Append(tray_id, "&Minimize to system tray\tCtrl+M")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "E&xit Indiginous\tAlt+F4")
        menu_bar.Append(file_menu, "&File")
        help_menu = wx.Menu()
        update_id = wx.NewIdRef()
        website_id = wx.NewIdRef()
        blindsoftware_id = wx.NewIdRef()
        help_menu.Append(update_id, "Check for &updates")
        help_menu.AppendSeparator()
        help_menu.Append(website_id, "Open Indiginous &website")
        help_menu.Append(blindsoftware_id, "Open &blind.software")
        help_menu.Append(wx.ID_ABOUT, "&About Indiginous")
        menu_bar.Append(help_menu, "&Help")
        self.SetMenuBar(menu_bar)
        self.SetName("Indiginous main window")
        self.Bind(wx.EVT_MENU_OPEN, self._on_menu_open)
        self.Bind(wx.EVT_MENU_HIGHLIGHT, self._on_menu_highlight)
        self.Bind(wx.EVT_MENU, lambda _event: self._reload(), id=reconnect_id)
        self.Bind(wx.EVT_MENU, lambda _event: self._restart_webview(), id=restart_world_id)
        self.Bind(wx.EVT_MENU, lambda _event: self._focus_world(), id=focus_world_id)
        self.Bind(wx.EVT_MENU, lambda _event: self._login_default(), id=signin_id)
        self.Bind(wx.EVT_MENU, self._show_settings, id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, lambda _event: self.web.RunScript("window.dispatchEvent(new Event('chatgrid-cast-to-device'));"), id=cast_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.Hide(), id=tray_id)
        self.Bind(wx.EVT_MENU, lambda _event: self.request_exit(), id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, lambda _event: self._check_updates_background(interactive=True), id=update_id)
        self.Bind(wx.EVT_MENU, lambda _event: self._open_external_url("https://blind.software/indiginous/"), id=website_id)
        self.Bind(wx.EVT_MENU, lambda _event: self._open_external_url("https://blind.software/"), id=blindsoftware_id)
        self.Bind(wx.EVT_MENU, self._show_about, id=wx.ID_ABOUT)

    @staticmethod
    def _open_external_url(url: str) -> None:
        """Open an approved public link without putting it in the startup UI."""
        webbrowser.open(url, new=2)

    def _on_menu_open(self, event: wx.MenuEvent) -> None:
        """Keep native menu opening visible to keyboard and screen-reader users."""
        menu = event.GetMenu()
        if menu is not None and self.GetMenuBar() is not None:
            index = next(
                (i for i in range(self.GetMenuBar().GetMenuCount())
                 if self.GetMenuBar().GetMenu(i) is menu),
                -1,
            )
            if index == 0:
                self._announce("File menu opened. Use the arrow keys to choose an action.")
        event.Skip()

    def _on_menu_highlight(self, event: wx.MenuEvent) -> None:
        """Speak the highlighted native action so NVDA can follow the menu."""
        item = event.GetMenuItem()
        if item is not None:
            label = item.GetItemLabelText().replace('&', '').strip()
            if label:
                self._announce(label)
        event.Skip()

    def _load_grid(self, url: str, assertion: str | None = None) -> None:
        """Load the shared client in native mode, optionally consuming one auth assertion."""
        parsed = urlsplit(url)
        query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                 if key not in {"desktop", "native_client", "external_auth"}]
        query.append(("native_client", __version__))
        if assertion:
            query.append(("external_auth", assertion))
        target = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
        self.web.LoadURL(target)

    def _login_default(self) -> None:
        """Open the approved BlindSoftware browser sign-in flow."""
        self._start_browser_auth(interactive=True)

    def _start_browser_auth(self, *, interactive: bool = False) -> None:
        if self.browser_auth_flow is not None:
            if interactive:
                self._announce("Indiginous sign-in is already open in your browser.")
            return
        try:
            flow = BrowserAuthFlow("https://blind.software", self.settings.grid_url)
            self.browser_auth_flow = flow
            if not webbrowser.open(flow.authorization_url, new=2):
                raise RuntimeError("The system browser could not be opened.")
            self._announce("Finish signing in in your browser. Indiginous will return here automatically.")
            flow.start(self._finish_browser_auth, self._browser_auth_failed)
        except Exception as error:
            LOGGER.warning("Could not start browser sign-in: %s", error)
            self.browser_auth_flow = None
            if interactive:
                self._announce("Indiginous could not open sign-in. Use Help or try again.")

    def _finish_browser_auth(self, grid_url: str, assertion: str) -> None:
        def apply() -> None:
            self.browser_auth_flow = None
            self.pending_external_auth = True
            self._load_grid(grid_url, assertion)
            self._announce("Signed in to Indiginous. Connecting to the world.")
        wx.CallAfter(apply)

    def _browser_auth_failed(self, message: str) -> None:
        def report() -> None:
            self.browser_auth_flow = None
            self._announce(message)
        wx.CallAfter(report)

    def _schedule_automatic_browser_auth(self) -> None:
        if self.auto_browser_auth_call is not None or self.browser_auth_flow is not None:
            return
        if not self.settings.auto_connect:
            return
        self.auto_browser_auth_call = wx.CallLater(900, self._begin_automatic_browser_auth)

    def _begin_automatic_browser_auth(self) -> None:
        self.auto_browser_auth_call = None
        self._start_browser_auth(interactive=False)

    def _on_script_message(self, event: wx.html2.WebViewEvent) -> None:
        """Receive sign-in state without exposing assertions to the native shell."""
        try:
            message = json.loads(event.GetString())
        except (TypeError, ValueError):
            return
        if message.get("type") == "authState":
            self.is_signed_in = bool(message.get("signedIn"))
            if hasattr(self, "signin_menu_item"):
                self.signin_menu_item.Show(not self.is_signed_in)
            if self.GetMenuBar() is not None:
                self.GetMenuBar().Refresh()
            if not self.is_signed_in:
                self._schedule_automatic_browser_auth()
        elif message.get("type") == "audioDevices":
            self.audio_devices = {
                "inputs": [(str(item.get("id", "")), str(item.get("label", ""))) for item in message.get("inputs", []) if item.get("id") is not None],
                "outputs": [(str(item.get("id", "")), str(item.get("label", ""))) for item in message.get("outputs", []) if item.get("id") is not None],
            }
            if self.settings_dialog is not None:
                self.settings_dialog.set_audio_devices(self.audio_devices)

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
        web.SetName("Indiginous world")
        try:
            web.AddScriptMessageHandler("indiginousNative")
            web.Bind(wx.html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_script_message)
        except (AttributeError, RuntimeError):
            LOGGER.debug("WebView script-message bridge is unavailable", exc_info=True)
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
        self._load_grid(self.settings.grid_url)
        self.web.SetFocus()

    def _announce(self, text: str) -> None:
        self.status.SetLabel(text)
        self.SetStatusText(text)

    def _on_loaded(self, _event: wx.html2.WebViewEvent) -> None:
        self.reconnect_timer.Stop()
        self.backoff.reset()
        self._announce("Indiginous loaded. Session and reconnect monitoring are active.")
        # Desktop users get the native File/Help menus; keep the web surface
        # focused on the world and never show product links or legacy branding
        # in the startup window.
        self.web.RunScript(
            "(() => {"
            "const style = document.createElement('style');"
            "style.id='indiginous-native-shell-style';"
            "style.textContent='#gridTitle,#connectionStatus,#loginView,#authSessionView,#button-container,#deviceSummary,#joinGuide,#appFooter,#openSettingsButton,#settingsModal{display:none!important}';"
            "document.head.appendChild(style);"
            "const send = () => { const logout = document.getElementById('logoutButton'); const signedIn = !!logout && !logout.hidden && !logout.classList.contains('hidden'); window.chrome?.webview?.postMessage(JSON.stringify({type:'authState', signedIn})); };"
            "const devices = async () => { try { let stream=null; try { stream=await navigator.mediaDevices?.getUserMedia({audio:true}); } catch (_) {} const list=await navigator.mediaDevices?.enumerateDevices?.() || []; window.chrome?.webview?.postMessage(JSON.stringify({type:'audioDevices',inputs:list.filter(d=>d.kind==='audioinput').map(d=>({id:d.deviceId,label:d.label})),outputs:list.filter(d=>d.kind==='audiooutput').map(d=>({id:d.deviceId,label:d.label}))})); stream?.getTracks().forEach(t=>t.stop()); } catch (_) {} };"
            "window.indiginousNativeRefreshAudioDevices = devices; devices();"
            "send(); new MutationObserver(send).observe(document.body,{subtree:true,childList:true,attributes:true});"
            "})();"
        )
        if self.pending_external_auth or self.settings.auto_connect:
            self.pending_external_auth = False
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
        self._queue_world_focus(800)

    def _focus_world(self) -> None:
        """Activate web world controls and move native focus into the renderer."""
        self.web.RunScript("document.getElementById('focusGridButton')?.click();")
        self.web.SetFocus()

    def _queue_world_focus(self, delay_ms: int = 100) -> None:
        """Restore renderer focus after Windows has finished activating the frame."""
        if self.world_focus_restore is not None:
            self.world_focus_restore.Stop()
        self.world_focus_restore = wx.CallLater(delay_ms, self._focus_world)

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
        self._load_grid(self.settings.grid_url)

    def _reload(self) -> None:
        self.backoff.reset()
        try:
            self.web.Reload(wx.html2.WEBVIEW_RELOAD_NO_CACHE)
        except Exception:
            LOGGER.exception("WebView reload failed; replacing the renderer")
            self._restart_webview()

    def show_from_tray(self) -> None:
        """Restore, raise, and focus the existing accessible window."""
        self._activate_window()
        self._queue_world_focus(150)
        self.RequestUserAttention(wx.USER_ATTENTION_INFO)

    def _activate_window(self) -> None:
        """Restore and foreground the existing window without creating a client."""
        if self.IsIconized():
            self.Iconize(False)
        self.Show(True)
        self.Raise()
        if sys.platform == "win32":
            try:
                hwnd = int(self.GetHandle())
                user32 = __import__("ctypes").windll.user32
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
            except (AttributeError, OSError, TypeError, ValueError):
                LOGGER.debug("Windows foreground activation was unavailable", exc_info=True)
        self.SetFocus()
        self._queue_world_focus(120)

    def reload_from_tray(self) -> None:
        """Recover the existing WebView without launching another application."""
        self.show_from_tray()
        self._reload()

    def request_exit(self) -> None:
        """Explicitly quit instead of applying close-to-tray behavior."""
        self.force_quit = True
        self.Close()

    def _prepare_exit(self) -> None:
        """Keep the legacy exit hook equivalent to an explicit full quit."""
        self.request_exit()

    def _quit_without_update(self) -> None:
        """Close immediately when no verified newer installer exists."""
        LOGGER.info("No verified update available during quit")
        self.force_quit = True
        self.Close()

    def _on_iconize(self, event: wx.IconizeEvent) -> None:
        if event.IsIconized():
            wx.CallAfter(self.Hide)
        event.Skip()

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        """Re-arm world keyboard focus after Alt+Tab, restore, or tray reopen."""
        if event.GetActive() and self.settings_dialog is None:
            self._queue_world_focus(120)
        event.Skip()

    def _show_settings(self, _event: wx.CommandEvent) -> None:
        self._activate_window()
        dialog = SettingsDialog(self, self.settings, self.audio_devices)
        self.settings_dialog = dialog
        self.web.RunScript("window.indiginousNativeRefreshAudioDevices?.();")
        try:
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
                    "inputDeviceId": self.settings.audio_input_device_id,
                    "outputDeviceId": self.settings.audio_output_device_id,
                    "layers": {"voice": self.settings.voice_layer, "item": self.settings.item_layer, "media": self.settings.media_layer, "world": self.settings.world_layer},
                    "announcementMode": self.settings.announcement_mode,
                    "radioAnnouncementMode": self.settings.radio_announcement_mode,
                    "itemBeacons": self.settings.item_beacons,
                    "movementDirections": self.settings.movement_directions,
                }) + ");"
            )
            self._announce("Desktop settings saved.")
        finally:
            self.settings_dialog = None
            dialog.Destroy()

    def _check_updates_background(self, interactive: bool = False) -> None:
        if self.update_thread and self.update_thread.is_alive():
            return

        def worker() -> None:
            try:
                service = UpdateService(self.settings.update_url, __version__, app_data_dir())
                manifest = service.check()
                if manifest is None:
                    if interactive:
                        wx.CallAfter(self._announce, "Indiginous is up to date.")
                    return
                if not interactive and service.is_dismissed(manifest):
                    return
                if not self.settings.auto_update and not interactive:
                    wx.CallAfter(self._announce, f"Indiginous {manifest.version} is available.")
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
        self._announce(f"Indiginous {version} is verified and ready to install.")
        with UpdateInstallCountdown(self, version) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                service.dismiss(manifest)
                self._announce("Update cancelled. Indiginous will keep running.")
                return
        service.install_after_exit(installer, manifest)
        self.force_quit = True
        self.Close()

    def _show_about(self, _event: wx.CommandEvent) -> None:
        wx.MessageBox(
            f"Indiginous {__version__}\nOfficial accessible Windows client by Raywonder / TappedIn.",
            "About Indiginous", wx.OK | wx.ICON_INFORMATION, self,
        )

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        unicode_key = event.GetUnicodeKey()
        if ((event.ControlDown() and event.AltDown()) or (event.MetaDown() and event.AltDown())) and (
            key == ord(",") or unicode_key == ord(",")
        ):
            self._show_settings(event)
            return
        if (event.ControlDown() or event.MetaDown()) and not event.AltDown() and (
            key == ord("R") or key == ord("r") or unicode_key == ord("R") or unicode_key == ord("r")
        ):
            self._dispatch_world_shortcut("KeyR", ctrl=True)
            return
        if key == wx.WXK_ESCAPE and self.IsIconized():
            self.Iconize(False)
            self.Raise()
            return
        event.Skip()

    def _on_close(self, event: wx.CloseEvent) -> None:
        if event.CanVeto() and not self.force_quit:
            event.Veto()
            self.Hide()
            return
        self.reconnect_timer.Stop()
        event.Skip()


class IndiginousApp(wx.App):
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
        self.tray = IndiginousTrayIcon(self.frame)
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
    migrate_legacy_state()
    logging.basicConfig(
        filename=root / "chat-grid.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    activation = SingleInstanceActivation()
    if not activation.is_owner:
        return 0
    try:
        LOGGER.info("Starting Indiginous %s on Python %s", __version__, sys.version)
        app = IndiginousApp(activation)
        app.MainLoop()
        return 0
    except Exception:
        LOGGER.exception("Fatal desktop startup failure")
        try:
            wx.MessageBox(
                "Indiginous could not start. A diagnostic log was saved to "
                f"{root / 'chat-grid.log'}.",
                "Indiginous startup error",
                wx.OK | wx.ICON_ERROR,
            )
        except Exception:
            pass
        return 1
