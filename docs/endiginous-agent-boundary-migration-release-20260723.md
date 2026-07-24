# Endiginous agent boundary and migration release

Date: 2026-07-23
Version: 0.4.4
Web revision: R517

## Product boundary

Endiginous installers and desktop clients no longer bundle OpenClaw onboarding, gateway registration, agent scripts, agent credentials, or OpenClaw runtime files. The supported extension direction is documented in `docs/user-agent-extensions.md`; user-owned agents can be added later through a separate, user-controlled extension location and are not copied into the product installer.

The visible product spelling is Endiginous. `chatgrid` names remain only where they are required for legacy URLs, protocols, service identifiers, database/log compatibility, and migration. The only remaining `Indigenous` source references are deliberate legacy-name cleanup entries.

## Migration and cleanup

Both desktop implementations migrate known legacy per-user state from old Chat Grid/ChatGrid/Indigenous locations into the current Endiginous application-data directory before startup. They remove only the exact legacy install directories and shortcuts listed by the migration module, write a `migration-receipt.json`, and preserve files when a copy fails. Startup cleanup also removes exact legacy autorun values. Windows installers use the current `%LOCALAPPDATA%\\Programs\\Endiginous` directory and do not reuse a stale previous install directory.

## Build and verification

- Mac mini: full native test suite, 37 passed.
- Windows 11 VM: full native test suite, 37 passed.
- Windows installer: built with Inno Setup 6.7.3 from the local-disk source tree; installed successfully to `%LOCALAPPDATA%\\Programs\\Endiginous`; the exact stale build-cache install and old legacy shortcut checks were cleaned/verified.
- Mac ZIP: app extracted and passed `codesign --verify --deep --strict`.
- Public downloads and manifests: all returned HTTP 200; the live Windows download SHA-256 matched the published manifest.

Artifacts:

- Windows installer: `1c2084baab07b8cdf006a4b2eadb4331c340dfcd8d85dea695a5585bde5344bb`
- Mac DMG: `cd15510fd277dcfb4438d6d279a70d3ee82aa1dbb0a27075824619137fdc49b1`
- Mac ZIP: `7516965bee7cc10416f991226772b217c22388bb7325e2b9009d10fcea7d5e28`

Public URLs:

- https://blind.software/endiginous/downloads/EndiginousSetup-0.4.4.exe
- https://blind.software/endiginous/downloads/Endiginous-0.4.4.dmg
- https://blind.software/endiginous/downloads/Endiginous-0.4.4-macOS.zip

The active BlindSoftware download page labels were updated from the stale Mac 0.4.1 labels to 0.4.4. The Mac DMG remains unsigned; the app inside the ZIP passed local deep code-sign verification.

