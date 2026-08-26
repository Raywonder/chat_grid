# Indiginous R561 VoiceOver and download hotfix

Date: 2026-08-26

## User-reported failures

- The public macOS ZIP action did not download.
- The web client did not reliably read world feedback through VoiceOver.

## Repairs

- Restored the BlindSoftware public-artifact PHP route used by the stable,
  neutral download URLs. The macOS ZIP, macOS DMG, and both updater-manifest
  routes now resolve again with the intended attachment names.
- Removed the dynamic `aria-label` that masked the central live region's text
  mutations from VoiceOver.
- Restored concise local movement and turn feedback when movement-direction
  announcements are enabled, with held-arrow coalescing.
- Implemented the documented Shift+Escape path to leave the application canvas
  and focus the visible Indiginous return control.
- Made the persistent canvas description non-live so it does not compete with
  the central transient status announcer.
- Advanced the public web client revision from R560 to R561 while retaining
  release version 0.4.22.

## Source and verification

- Source commit: `fd23616`.
- Client tests: 35 passed.
- Client lint: passed.
- Production build: passed.
- Public URL: `https://blind.software/indiginous/`.
- Public version: 0.4.22 / R561.
- Public HTML, current JavaScript, CSS, version, branding, help, and changelog:
  HTTP 200 with expected content types.
- Public WebSocket: HTTP 101 Switching Protocols.
- `chat-grid.service` and `chat-grid-companion.service`: active.
- Runtime item JSON: valid, 216 items.
- Public macOS ZIP route: HTTP 200, `application/zip`, attachment filename
  `Indiginous-macOS.zip`.
- Public macOS DMG and macOS/Windows update-manifest routes: HTTP 200.

## Recovery points

- Web client: `/mnt/backups/chat-grid/indiginous-before-r561-20260826-1026/`.
- BlindSoftware index:
  `/home/blindsoft/public_html/index.php.bak-indiginous-public-download-repair-20260826-1006`.

## Remaining hands-on proof

Matt still needs to refresh the authenticated page in Safari with VoiceOver and
confirm movement, turning, world/chat status, help, and Shift+Escape behavior.
Automated checks cannot prove the audible VoiceOver result on his exact session.
