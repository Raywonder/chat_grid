# BlindSoftware installer path policy receipt

Date: 2026-07-26

## Implemented

- Active Windows Inno definitions default to
  `C:\Program Files\BlindSoftware\Indiginous` through the Windows
  architecture-aware `{autopf}` constant.
- The installer directory page remains available, so users can select a
  different permitted path, including a path under their own profile.
- Legacy cleanup recognizes the vendor-rooted paths and preserves the
  currently running frozen executable directory instead of deleting it as
  legacy state.
- The macOS setup scaffold defaults to
  `/Applications/BlindSoftware/Indiginous.app` and exposes an editable install
  location field.
- The reusable policy is documented in `docs/installer-path-policy.md`.

## Verification

- wxPython focused tests: 13 passed.
- Native focused tests: 12 passed.
- Python compile checks: passed.
- Source preflight: passed for wxPython 0.4.9 / R531.
- Windows VM build: 21 tests passed; Inno Setup compiled
  `W:\Repos\ChatGrid\desktop\wxpython\release\Indiginous_Setup.exe`.
- Windows installer SHA-256:
  `5EA2C7BE9210F0BE86FC7A7B561CE72E190113B4374A9229DBDE4F16985E1692`.

## Not verified here

- The Windows VM build session is noninteractive; machine-wide Inno install
  proof through SSH was blocked by the VM's interactive UAC boundary. The
  compiled source/default path is verified, but a runtime install under
  `C:\Program Files\BlindSoftware\Indiginous` still needs an interactive
  Windows desktop run.
- macOS SwiftUI tests and DMG/app packaging were not run on this Linux host.
