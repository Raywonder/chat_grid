# Indiginous desktop 0.4.10 / R533 receipt

Date: 2026-07-26

## Scope

Reviewed the current in-world public and direct-message context in `raywonder_house_bedroom`, including Dominique's requests to keep public room chat visible to Clawdia, record direct messages in the canonical Journal, restore/focus the existing Windows window from the tray, prevent duplicate launches, and make the File menu discoverable to screen readers.

## Implemented

- Reconnect history now consumes the current room's bounded public-chat history and keeps it in room-local companion memory.
- Reconnect direct-message history is written to the canonical Journal with deterministic de-duplication; old messages are not re-answered.
- Windows/macOS single-instance activation is enforced in both desktop shells.
- Tray restore restores, raises, foregrounds, and focuses the existing window instead of launching another copy.
- Windows foreground activation uses the native window handle when available.
- The File menu now announces when opened and exposes the current keyboard navigation path.
- Settings uses `Ctrl+Alt+,` on Windows/Linux and `Cmd+Alt+,` on macOS.
- Release metadata and client revision are aligned to 0.4.10 / R533.

## Verification

- wxPython desktop tests: 24 passed.
- Companion/server focused tests: 9 passed.
- Python compilation: passed.
- Focused native desktop tests: 15 passed in the available wx test environment.
- Source preflight: passed for wxPython 0.4.10 / R533.
- Windows 11 VM access: passed; SSH, RDP, W: build drive, and required build shares were reachable.
- Windows build: passed on `OPENCLAW-WIN11` with 23 tests passed and 1 platform-appropriate skip.
- Windows artifact preflight: passed.
- Artifact: `Indiginous_Setup.exe`
- Artifact path: `/mnt/backup/windows-build/Repos/ChatGrid/desktop/wxpython/release/Indiginous_Setup.exe`
- Artifact size: 27,374,168 bytes
- SHA-256: `188bfa2b96b09bd3b693c9c83d411ffc0588239eac75dc70f5c7a04b91aff6dc`

## Still unverified

- Interactive UAC installation and real NVDA/keyboard/File-menu operation on Dominique's physical Windows desktop.
- The VM's unattended installer launch did not provide valid Program Files installation proof through the remote non-interactive session, so no false installation claim is made.
- Full native test collection on Linux remains unavailable because that environment has no `wx` module for the native login test.
- macOS build, signing, installation, and VoiceOver proof remain pending.
- The stable Windows artifact has not been published to the public download route in this receipt.

