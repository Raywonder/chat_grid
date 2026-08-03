# Indiginous R541 authentication resume receipt

Date: 2026-08-03

## Change

R541 makes native sign-in state deterministic and lets a returning desktop
client resume from its saved blind.software session without opening the system
browser again.

- The shared client checks the HttpOnly session cookie before starting an
  automatic connection. A saved username alone is no longer treated as proof
  that an auth packet is available.
- The wxPython shell no longer sends a competing second Connect click during
  ordinary startup. It only submits the one-use assertion returned by the
  initial browser authorization flow.
- The shared client sends explicit native auth-state messages for sign-in,
  sign-out, authentication failure, and successful world admission.
- Native shells update their File-menu action and announce the message through
  their existing accessible status/screen-reader path.

## Verification

- Client tests: 29 passed.
- Client lint: passed.
- Client production build: passed.
- wxPython focused source tests: 18 passed.
- Native focused source-only tests: 13 passed.
- Client revision: R541.

## Remaining platform proof

The Linux server is not a valid native desktop release lane. The native
environment could not build wxPython because no C compiler is installed, so
Windows and macOS packaged-client proof remains assigned to the existing
Windows VM and Mac mini lanes. No desktop installer or public update artifact
was replaced by this checkpoint.
