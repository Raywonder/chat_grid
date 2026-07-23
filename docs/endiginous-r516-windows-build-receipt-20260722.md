# Endiginous R516 Windows build receipt

Date: 2026-07-22 CDT
Host: `OPENCLAW-WIN11` (`192.168.188.147`), account `openclaw-win11\\clawadmin`
Source stage: `C:\\BuildCache\\Endiginous-R516-20260722-1505`
Build cache: `C:\\BuildCache\\Endiginous-R516-build-20260722-1505`
Version: 0.4.4
Revision: R516

## Verified

- The documented `W:` share check still fails at the protected credential
  transformation, but the VM's local `C:` lane has Python 3.12, Inno Setup 6,
  WebView2, and about 50 GB free.
- Windows client tests: 15 passed.
- PyInstaller completed on Windows 11.
- Inno Setup completed successfully after adding the required `shellexec` flag
  to the existing OpenClaw post-install `[Run]` entry in
  `desktop/wxpython/installer/ChatGrid.iss`.
- Installer:
  `C:\\BuildCache\\Endiginous-R516-20260722-1505\\desktop\\wxpython\\release\\EndiginousSetup-0.4.4.exe`
- Installer size: 27,376,460 bytes.
- Installer SHA-256:
  `732a7aee35018a0cfdb1b091e2bbf8425206bcbcc7196eb61a3e6e505b2ec32a`
- Fresh silent install exited 0 into
  `C:\\BuildCache\\EndiginousInstall-0.4.4-R516-20260722-1505`.
- The installed `Endiginous.exe` stayed alive for five seconds; the test
  process was then stopped and no Endiginous process remained.
- Local preserved copy:
  `tmp/endiginous-r516-windows-20260722/EndiginousSetup-0.4.4-R516.exe`

## Still not a release approval

- Real NVDA/UI Automation menu, settings, authenticated-world movement, and
  audio proof remain pending; the previous VM session exposed no usable
  top-level UIA tree.
- macOS VoiceOver and authenticated-world movement/audio proof remain pending.
- The Windows installer is unsigned internal evidence only. Public downloads,
  update manifests, and account links remain unchanged.
