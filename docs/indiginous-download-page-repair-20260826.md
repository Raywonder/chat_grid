# Indiginous download page repair — 2026-08-26

## Status

The public download presentation is repaired and verified. No Windows R561
installer was published because the owner Windows execution lane still denies
commands and the source release manifests do not yet pass the R561 artifact
gate.

## Public changes

- Replaced the raw `/indiginous/downloads/` directory index with a curated
  accessible page.
- Added explicit platform, version/revision, architecture, file name, size,
  and SHA-256 details for the verified Windows 0.4.18 / R549 package and the
  current macOS 0.4.22 / R560 packages.
- Added an Indiginous section to `/?route=downloads`.
- Updated signed-in account labels so Windows is identified as the verified
  stable release rather than an unverified “latest” build.
- Added captions, column scopes, row headers, contextual token URL labels,
  and contextual remove-button names to download tables.
- Strengthened the public focus indicator and corrected user-facing
  `Endiginous` error text to `Indiginous`.

## Verification

- `https://blind.software/indiginous/downloads/` returned HTTP 200 and served
  the curated page, not an autoindex.
- `https://blind.software/?route=downloads` returned HTTP 200 and exposed the
  Indiginous section and semantic table markup.
- Public Windows manifest returned HTTP 200 and remains explicitly 0.4.18 / R549.
- Public web version remains 0.4.22 / R561.
- PHP syntax check passed for the staged site source.
- Backups: `/home/tappedin/.openclaw/workspace/backups/blindsoftware-index-before-indiginous-downloads-20260826-221143.php`
  and the matching stylesheet backup.

## Remaining release gate

The native Windows build, installer launch, and NVDA/UIA verification remain
unverified. `scripts/preflight.py source` correctly fails while the Windows and
macOS update manifests remain at R560 instead of the requested R561 artifact
boundary. Do not publish or relabel the Windows feed until the native Windows
artifact is built, tested, checksummed, and verified from the Windows user path.
