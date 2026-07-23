# Endiginous OpenClaw installer receipt

Date: 2026-07-21

## Implemented

- Both Windows Inno Setup definitions bundle `scripts/installers/openclaw-join-windows.ps1`.
- The post-install wizard has a checked-by-default `OpenClaw device setup` task.
- That task installs/configures the OpenClaw CLI and node service, then starts interactive Headscale/Tailscale enrollment with `-InstallTailscale`.
- The installer invokes the setup helper with the Windows `runas` verb so machine-level Tailscale installation can request UAC elevation.
- Existing healthy Tailscale enrollment is preserved; rerunning the installer no longer resets the device identity.
- No shared Tailscale auth key or OpenClaw token is embedded in the installer.

## Files

- `desktop/wxpython/installer/ChatGrid.iss`
- `desktop/native/windows/installer/ChatGrid.iss`
- `desktop/wxpython/README.md`
- `scripts/installers/openclaw-join-windows.ps1`

## Verification

- PowerShell parser check passed.
- Helper checksum check passed: `c3c90deb8349d2fe0aa66a4e916b82bb19c1b7bf021aef8bf959cf33aabc0b6e`.
- Both installer source paths resolve to the helper.
- Windows VM TCP access to SSH and RDP passed.

## Still pending

The Windows build-share credential on the reachable `OPENCLAW-WIN11` VM fails its encrypted `Import-Clixml` load. A real Windows build, installer installation, OpenClaw/Tailscale enrollment, and user-facing verification remain pending until that build-share route is repaired.
