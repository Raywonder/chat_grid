# Indiginous repository consolidation

Status: required target architecture; migration and installer rebuilds are not complete.

## One maintained source repository

Consolidate the maintained product into one canonical Gitea repository named
`indiginous`. The current verified source remote is
`raywonder/endiginous`; its existing GitHub mirror is `Raywonder/chat_grid`.
The namespace of the final repository must be verified against the owning
account or organization before moving it. Do not create an unrelated repository
or delete an existing mirror to make the naming appear complete.

Use one integration branch, with platform-specific folders for Windows, macOS,
iOS, web, and server. Shared protocols, permissions, account APIs, and common
tests remain shared. Platform branches may be used for focused work and release
maintenance; branches are not nested folders and must not become divergent
copies of the shared product. Existing client/ and server/ source paths remain
until scripts, CI, packaging and documentation migrate together.

## Branding and compatibility

- All new visible titles, installers, application metadata and help use Indiginous.
- Retain the original Chat Grid attribution, history and license notices.
- Distinguish visible branding from compatibility identifiers. Migrate stored
  preferences without losing audio, accessibility, login or device settings.
- Update sign-in callback registration, application URL handlers, bridge events,
  server routes, configuration readers and update consumers as a tested group.
- Legacy install names in detection and migration tests are intentional until
  upgrade support is retired. Never replace those strings with the new name.
- Repository redirects may help old source links, but must not be assumed to
  preserve release assets, authenticated API calls or updater feeds.

## Pending source inventory, 2026-09-08

Checkout main is at 2a3eefb; Gitea main was e29b228 at inspection.
Two committed changes need review before synchronization: 50b4c9d (official Tesla
TV sources) and 2a3eefb (R562 release receipt). The working tree has no tracked
modifications at the start of this audit, but contains untracked backups, build
outputs, publishing directories, a previous Windows artifact, two server-specific
Jellyfin reports, and two companion-client backup files. Do not bulk-add them.
Review operational reports for privacy separately from product documentation.
Preserve all recovery files until retention and replacement verification allow
cleanup. An old artifact is not a new build.

## Installer and release gates

1. Claim and fingerprint the current approved source with agent_sync_guard.
2. Review and integrate intentional source changes only, preserving other work.
3. Test web/server and each changed native platform independently.
4. Bump shared release/platform revision metadata for user-visible changes.
5. Rebuild on the appropriate platform with required signing credentials and
   accessible install, upgrade, launch, authentication, audio and updater tests.
6. Retain `Indiginous_Setup.exe` as the Windows installer filename.
7. Publish artifacts before manifests; verify version, size, hash and URLs.
8. Migrate repository and client consumers before retiring old source locations.

Indiginous management of blind.software projects, tickets, notification groups,
role-help and scoped support permissions remains a separate implementation task.
The client must use server-authorized capabilities; a role label or hidden UI
control is never an authorization decision. Desktop and iOS releases require
separate evidence and cannot be substituted for each other.
