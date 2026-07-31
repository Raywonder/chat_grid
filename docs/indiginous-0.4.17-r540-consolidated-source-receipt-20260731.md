# Indiginous 0.4.17 / R540 consolidated source receipt

Date: 2026-07-31

This source update consolidates the accessible desktop/menu fixes, room-scoped
TV and radio remote behavior, per-device media sounds, gamepad input, active
companion controls, clock announcement handling, and duplicate-announcement
suppression.

## Verified

- Client: 29 Vitest tests passed.
- Client: ESLint passed.
- Client: Vite production build passed.
- Server: 282 pytest tests passed.
- Python syntax compilation passed for server and native desktop sources.
- Release source preflight passed for wxPython 0.4.17 / R540.
- The stale host-local repository claim was safely taken over after its owner
  PID was confirmed stopped.

## Not yet verified

- wxPython native tests and Windows installer build were not runnable on this
  Linux host because wxPython 4.2.5 requires a C compiler to build here.
- Windows/NVDA hands-on menu, authentication, controller, and installed-client
  verification remain required on the approved Windows build lane.
- No installer, public download, server deployment, or running-client update
  is claimed by this receipt.
