# Desktop Single-Instance and Tray Standard

All TappedIn, Raywonder, and Divine Creations desktop applications should follow this lifecycle unless a documented product requirement explicitly needs multiple instances.

## Required behavior

- Acquire an application-specific operating-system single-instance lock before creating the main window.
- If another instance already owns the lock, signal that instance to restore, raise, and focus its existing main window, then exit immediately.
- Never create a second WebView, audio session, login session, background watcher, or tray icon for an ordinary relaunch.
- Minimize and ordinary window-close actions should hide the app to its system-tray icon when background operation is useful.
- The tray must offer accessible actions to open/restore, reconnect or reload the existing app, and explicitly quit.
- A relaunch should restore a minimized or hidden healthy window. If the existing UI process or embedded web view is unresponsive, recover or reload that existing instance instead of creating another instance.
- Explicit Quit, uninstall, update installation, operating-system shutdown, and fatal recovery may end the process cleanly and release its lock.
- Window restoration must unminimize, show, raise, request user attention, and place keyboard or screen-reader focus in the primary application surface.

## Platform mappings

- Electron: `app.requestSingleInstanceLock()`, `second-instance`, one `Tray`, and a shared restore/focus function.
- wxPython on Windows: one named activation event or mutex plus a timer/message receiver, `wx.adv.TaskBarIcon`, and a shared restore/focus method.
- .NET/WPF/WinUI: one named mutex plus named pipe/event/activation redirection, with one `NotifyIcon` or App SDK tray implementation.
- macOS: the application delegate/open event should activate the existing app and window; do not create a second app process for ordinary reopening.

## Verification

For each release, test all of these from the installed user-facing build:

1. Launch once and confirm one process, one main window, and one tray icon.
2. Launch the same shortcut again and confirm the existing window comes forward without another process remaining.
3. Minimize or close to tray, relaunch, and confirm the existing window becomes visible and focused.
4. Confirm explicit Quit removes the tray icon and process, then a later launch starts normally.
5. Confirm reconnect/reload recovers the existing UI without duplicating audio, authentication, or background services.

Endiginous's Electron and accessible wxPython Windows shells are the initial reference implementations.
