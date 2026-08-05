# Indiginous naming audit

The active source, desktop package paths, installer/spec filenames, Qt
scaffold identifiers, browser/native bridge names, and companion CLI entry
points now use `Indiginous`/`indiginous`.

The following names remain intentionally linked compatibility contracts:

- `/chatgrid/` and `chatgrid://` for older clients and bookmarks.
- `CHGRID_*` environment and web-version variables.
- Existing systemd unit, database, topic, bundle-identifier, and storage keys.
- `chatgrid_presence.py` and `chatgrid_log_audit.py` wrapper entry points.
- Legacy migration cleanup names and historical release receipts.

This is an audit boundary, not a second product name. New code and new
installers must use Indiginous; compatibility names must only appear at an
explicit boundary with a test or migration reason.
