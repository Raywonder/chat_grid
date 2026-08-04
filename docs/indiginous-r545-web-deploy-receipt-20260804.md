# Indiginous R545 web deployment receipt — 2026-08-04

- Source commit: `c3b45b4` (`fix: quiet routine movement narration`).
- Web revision: `0.4.18` / `R545`.
- Public URL: `https://blind.software/indiginous/`.
- Public `version.js`: HTTP 200; reports `0.4.18` / `R545`.
- Public entrypoint and referenced JavaScript/CSS assets: HTTP 200.
- Web build: Vite production build passed before deployment.
- Existing public installer artifacts were preserved and verified:
  - Windows `Indiginous_Setup.exe`: HTTP 200, 27,396,930 bytes,
    SHA-256 `3c27b2080b76caceddb9d10392a40d2735e356cc90a693e12ed20af2b487057c`,
    published as `0.4.18` / `R541`.
  - macOS `Indiginous-macOS.zip`: HTTP 200, 37,198,184 bytes,
    SHA-256 `81a52a914fb9c4f2e2514a0bf50b8d10621dc12efcba0710fb9c13d2d9a44839`,
    published as `0.4.5` / `R517`.
- Download-page labels were corrected in `/home/blindsoft/public_html/index.php`
  and PHP syntax validation passed. A backup is stored at
  `/home/tappedin/backups/blindsoftware-index-before-indiginous-r545-labels-20260804-1251.php`.
- Web rollback tree: `/home/tappedin/backups/indiginous-live-before-r545-20260804-1251`.
- Desktop release gate: no matching R545 Windows or macOS artifacts exist, so
  the updater manifests remain on their verified desktop revisions rather than
  falsely relabeling older installers.
