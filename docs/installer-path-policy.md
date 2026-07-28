# BlindSoftware installer path policy

BlindSoftware desktop applications use a vendor-owned default installation
root so applications are grouped predictably for all users:

- Windows default: `C:\Program Files\BlindSoftware\<AppName>` (or the
  architecture-appropriate Windows Program Files root).
- macOS default: `/Applications/BlindSoftware/<AppName>.app` when the app is
  installed system-wide.

Installers must keep an accessible directory/location choice enabled. A user
may select another permitted location, including a path under their own user
profile, when policy, permissions, portable use, or local administration
requires it. The selected location becomes the active install location for
that run; update and cleanup logic must use the running executable's location
and must never delete it as legacy state.

User data remains in per-user application-data storage and is not removed by
payload replacement. Legacy cleanup is limited to exact known application
directories and shortcuts.
