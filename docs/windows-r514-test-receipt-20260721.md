# Windows Endiginous R514 test receipt

- Date: 2026-07-21 CDT
- Lane: Windows 11 VM `OPENCLAW-WIN11`, account `openclaw-win11\\clawadmin`
- Source: `W:\\Repos\\ChatGrid`
- Target: wxPython Windows desktop client 0.4.3, web revision R514
- Build command: `desktop\\wxpython\\scripts\\build-windows.ps1`
- Windows client tests: 14 passed
- Installer: `EndiginousSetup-0.4.3-R514.exe`
- SHA-256: `9308b4c74796104b09a70a1087a892315767554cc55d43cbb9cec3fe6b8144ca`
- Artifact preflight: passed
- Silent install: passed, exit code 0
- Startup: the installed process started in the active NVDA session and logged the Edge WebView2 backend initialization.
- Not yet proven: Windows UI Automation exposed no top-level window or menu tree for the launched process, so File-menu focus/announcements, settings activation, world connection, and test-account sign-in were not claimed as passed.
- Cleanup: the test process was stopped and the temporary `Endiginous-R514-Test` scheduled task was removed.

The blocker is specifically interactive-window/UIA exposure in the VM test session, not a failed build or installer installation.
