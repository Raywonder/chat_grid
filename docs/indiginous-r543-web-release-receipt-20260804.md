# Indiginous R543 web release receipt — 2026-08-04

## Verified

- Source commit: `23521b1` (R543 metadata) plus the preceding guide commits.
- Public web URL: `https://blind.software/indiginous/`
- Public version endpoint reports release `0.4.18`, client revision `R543`.
- Public index response: HTTP 200, 10,522 bytes at verification time.
- Live `chat-grid.service`: active after restart.
- Rollback copy: `/home/blindsoft/release-backups/indiginous-before-r543-20260804`
- Client tests: 29 passed.
- Client lint: passed.
- Client production build: passed.
- Server media-guide tests: 2 passed.

## Release boundary

The R543 web client is published. The Windows and macOS updater manifests
remain on the previously verified R541 desktop artifacts because the matching
R543 platform installers were not built and platform-specific accessibility
verification was not available. No stale installer was relabeled as R543.
