# Indiginous exit/update prompt fix

Date: 2026-07-27

## Fix

- Explicit Exit in the native wxPython shell now closes the application
  immediately instead of reusing the update-install countdown.
- The legacy `_prepare_exit` hook now delegates to the same explicit quit path.
- The wxPython Windows shell no longer performs an update check as part of
  explicit Exit; ordinary close-to-tray behavior remains controlled by the
  user's tray setting.
- Regression checks cover the absence of the false update dialog and the
  force-close path in both desktop shells.

## Verification

- Python compilation passed for both modified desktop shells.
- `git diff --check` passed.
- Manual source-level regression assertions passed for both native paths.
- The pinned wxPython test environments could not be built on this Linux host:
  wxPython 4.2.5 requires a C compiler and GTK build dependencies that are
  not installed here.

## Release status

The public Windows manifest remains 0.4.11/R534. The working wxPython tree is
0.4.12/R535, but release preflight currently reports version/revision drift in
the native and macOS metadata plus the update manifests. No public installer
replacement is claimed by this receipt.

Recovery copies of the two modified app modules are under the timestamped
`backups/indiginous-exit-update-fix-*` directory.
