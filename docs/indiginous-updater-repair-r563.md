# Indiginous updater repair candidate 0.4.23 / R563

Not built or released. Source metadata is for the next candidate only; published
feeds remain at their verified existing versions.

Both Windows helper implementations now use TargetProcessId instead of Pid.
PowerShell treats variable names case-insensitively, and PID is read-only, so
binding a Pid parameter can fail before installer handoff. Generated helper text
and subprocess arguments must use the same nonreserved name.

Verification: isolated Python tests generated both Windows helpers with process
launch mocked, checking the parameter, wait logic and command argument. Native
Windows PowerShell successfully bound TargetProcessId. No installer was launched.

Update linkage audit: Windows 0.4.22 R561 checksum matches its stable installer;
macOS 0.4.22 R560 ZIP and DMG checksums match their server files. The macOS feed
selects a DMG while the current auto-updater requires a ZIP and signature checks;
the feed describes the package as unsigned. Do not bypass signing checks.
latest-windows-native.json still advertises 0.4.9 R531 and requires a coordinated
compatibility-feed correction after current client consumers are verified.

Remaining: native rebuilds, install/upgrade/relaunch tests, macOS signing and
architecture verification, public HTTPS verification, artifact upload followed
by atomic feed publication. Do not relabel an old installer as this version.
