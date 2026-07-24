# Indigenous 0.4.6 Windows build receipt

Date: 2026-07-24 (CDT)

## Verified

- Source movement repair: `997d288` — native Windows arrow movement now falls back to the foreground keyboard hook when global hotkey registration is unavailable.
- Native tests on the Windows 11 build VM: `40 passed`.
- PyInstaller completed on the Windows 11 build VM.
- Inno Setup completed successfully.
- Installer: `IndigenousSetup-0.4.6.exe`
- Size: `164,994,194` bytes
- SHA-256: `64ca78c81bd05c502ac7f87c3ae71bd37e1043522a6d718eaa24dfb1246d3c6d`
- VM install completed and the installed application launched/responded as process `Endiginous.exe`.

## Not yet released publicly

The installer has not replaced the public download or update manifest. macOS 0.4.6 still needs a matching build and user-facing launch/movement proof before a cross-platform release can be published. The installed executable/bundle still contains legacy technical identifiers; the visible product name is being migrated to **Indigenous** while compatibility routes and protocols are retained until the coordinated cutover is proven.
