# Endiginous Rename Plan

Endiginous is the current user-facing name for the project formerly called Chat
Grid.

## Already Migrated

- Web app title, main heading, help title, sign-in copy, and current desktop
  update feeds use Endiginous.
- Package metadata now uses `endiginous-client`, `endiginous-server`,
  `endiginous-desktop`, `endiginous-windows`, and
  `endiginous-windows-native`.
- Agent instructions in the main, Mac, Windows, and project workspaces tell
  Codex and other CLI workers to use Endiginous for new visible naming.
- `scripts/endiginous_presence.py` is the preferred companion CLI entrypoint.

## Completed Primary Route Migration

The web client is now built and published at `/endiginous/`. The signaling
service, session routes, voice assets, desktop defaults, update feeds, and
account auth links use `/endiginous/` as the primary path. `/chatgrid/` remains
an active compatibility path and proxies to the same Endiginous backend so
older installed clients and bookmarks continue to work.

## Compatibility Names To Keep For Now

Keep these until a dedicated cutover updates production, installed clients,
auth callbacks, update feeds, systemd units, and rollback checks together:

- `/chatgrid/` public path and URLs.
- `chatgrid://` deep links.
- `CHGRID_*` environment variables and web version constants.
- `chat-grid.service` and `chat-grid-companion.service`.
- `chat_grid_native` Python package paths.
- `chat-grid-focus`, `chat-grid-native-key`, and similar browser/native bridge
  event names.
- Existing bundle identifiers, database filenames, backup names, logs, and old
  release artifacts.

## Remaining Legacy Compatibility

The remaining `chatgrid` identifiers are deliberately retained where removing
them would strand an installed client or change a persistent contract: legacy
deep links, old environment variables, Python import paths, service names,
database/topic names, browser bridge events, bundle identifiers, and historical
release artifacts. New installers register `endiginous://` and continue to
accept `chatgrid://`.

The old path should only be retired after the active Windows/macOS population
has updated and a separate removal release verifies auth returns, update feeds,
companion presence, and rollback behavior.
