# Indiginous Windows 0.4.8 keyboard-safety receipt

Date: 2026-07-26 (CDT)

## Result

The Windows native client was rebuilt as Indiginous 0.4.8 / R530. The client no longer installs or calls a process-wide keyboard hook, intercepts standalone Alt, or sends a Windows system command to force-open the File menu. Keyboard handling stays inside the wx/WebView window. If the in-app world dispatch raises an exception, the client logs it and closes itself instead of leaving a global input/accessibility hook behind.

The legacy wxPython source tree received the same standalone-Alt removal. The Windows build script now stops on dependency, test, PyInstaller, or Inno Setup failure instead of continuing toward a misleading installer.

## Proof

- Focused native safety/menu/dialog tests: 14 passed.
- Legacy wxPython accessibility-shortcut tests: 4 passed.
- Windows VM native suite: 40 passed in 0.44 seconds.
- Source preflight: passed for wxPython 0.4.8 / R530.
- Python compileall: passed for both desktop source trees.
- `git diff --check`: passed.
- Installer silent-install test on `OPENCLAW-WIN11`: exit code 0; 853 files installed.
- Installed `Indiginous.exe` launched for three seconds and was then closed by its exact process ID.

## Artifact

- Installer: `desktop/native/release/IndiginousSetup-0.4.8.exe`
- Size: 165,358,536 bytes
- SHA-256: `74fe3dc63f7e9201a4a60e101a2e156d6b79680a4fce38966672b12f5c71fb7c`
- Artifact preflight: passed.
- Both native and legacy wxPython Windows update manifests now contain this checksum.

The public download URL in the manifests was not deployed or replaced in this task. Publishing remains a separate release action.

## Scope note

This receipt proves source-level hook removal, automated menu/shortcut protections, a real Windows build, silent installation, and launch/cleanup. A live NVDA keyboard-session test with Dominique pressing Alt across the whole Windows desktop was not available in this server-side run; that final physical accessibility check remains the next user-machine verification step.

The repository already contained broad unrelated uncommitted work. No reset, cleanup, or commit was performed, so those changes remain preserved for their owners.
