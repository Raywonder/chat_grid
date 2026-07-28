# Indiginous tray menu actions

Date: 2026-07-26

The next desktop client release exposes the main recovery and configuration
actions from the system-tray popup, not only restore and quit.

Windows wxPython tray actions:

- Open Indiginous
- Reconnect Indiginous
- Focus world
- Settings
- Check for updates
- Open the Indiginous website
- About Indiginous
- Quit Indiginous

The native desktop shell additionally exposes both shared App settings and
Desktop settings. Tray labels use mnemonic ampersands for keyboard access.
Handlers are attached to each newly-created popup menu. This prevents opening
the tray menu repeatedly from accumulating duplicate event handlers.

Verification:

- Both source trees compile with `python3 -m compileall`.
- wxPython tray-menu contract test passed.
- Native tray-menu contract test passed.
- Full runtime tray and NVDA verification remain for the Windows desktop lane.
