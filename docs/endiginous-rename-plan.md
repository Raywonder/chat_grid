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

## Staged User-Facing Alias

The web client can be built with `VITE_BASE_PATH=/endiginous/` and served at
`/endiginous/` while `/chatgrid/` remains the compatibility path. The alias
must proxy WebSocket, session, and voice requests to the existing backend
routes, and both paths must be checked from the public side before account
links are switched.

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

## Next Coordinated Cutover

When Dominique approves a full compatibility-breaking migration, do it as one
release:

1. Add new `/endiginous/` routes while keeping `/chatgrid/` redirects or aliases.
2. Add a new `endiginous://` protocol while preserving `chatgrid://` for older
   installers.
3. Add `ENDIGINOUS_*` environment aliases, then migrate services and deploy docs.
4. Publish signed Windows/macOS updates that understand both old and new links.
5. Verify public assets, WebSocket handshakes, auth returns, update feeds,
   desktop install/update, companion presence, and rollback paths before removing
   old compatibility names.
