# Indiginous R534 authentication and desktop UI release

Date: 2026-07-26

## Changes

- Removed legacy Jage/old-project wording from the client startup page and version label.
- Windows wxPython shell now loads `/indiginous/` with `native_client=0.4.11`.
- Added the BlindSoftware browser sign-in handoff using a short-lived loopback callback and `external_auth` assertion.
- Automatic sign-in starts only when the embedded client reports that the visible logout control is absent/hidden.
- Kept public links in the native Help and system-tray menus instead of the startup surface.
- Bumped the coordinated web/desktop release to 0.4.11 / R534.

## Verification

- Public `https://blind.software/indiginous/version.js` reports 0.4.11 / R534.
- Public startup HTML contains `Indiginous web client` and no Jage marker.
- Public auth route responded to an unauthenticated callback probe with HTTP 400; no account credentials were used.
- Browser-auth loopback callback test passed with a synthetic assertion.
- Windows VM `OPENCLAW-WIN11` / `clawadmin`: 24 tests passed, 1 platform skip.
- PyInstaller and Inno Setup completed successfully.
- Fresh installer install returned exit code 0; installed executable existed at `C:\Program Files\BlindSoftware\Indiginous\Indiginous.exe`.
- Installed executable launch stayed alive with one Indiginous process; the process was stopped after the check.
- Public installer download matches the VM artifact SHA-256:
  `75106febd9da1b1d3eff0cfe85227abd0cdfacc8de133b135c35b23b0069d1a0`

Artifact: `desktop/wxpython/release/Indiginous_Setup.exe`

## Remaining limitation

An actual signed-in account/browser callback was not exercised because no account credentials were used in the build proof. The first real sign-in should open the browser from the installed client, return through the loopback callback, and reconnect the embedded world with the one-use assertion.

The existing dirty worktree was preserved; no broad reset or cleanup was performed.
