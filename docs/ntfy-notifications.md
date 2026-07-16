# Chat Grid identity ntfy notifications

- Owner: Chat Grid / TappedIn platform service, managed by Devine Creations/TappedIn.
- Provider: self-hosted ntfy at `https://ntfy.tappedin.fm`.
- Publisher: dedicated `chatgrid-alerts` service identity with write-only access to `chatgrid-user-*`.
- Subscribers: read-only access through a random per-identity topic link. The link is bearer-style private metadata and should not be shared.
- Opt-in: disabled by default for existing and future Chat Grid identities. Users control it in App settings.
- Clients: settings are server-backed through `ntfy_preferences_get` and `ntfy_preferences_update`, allowing web, Windows, macOS, and iOS clients to share the same identity preference.
- Secrets: `/home/tappedin/.openclaw/state/chatgrid-ntfy.env`, mode 600, owned by `tappedin`. Never embed publisher credentials in a client.
- Webhooks/callbacks: none. Chat Grid publishes outbound JSON to ntfy when its notification service creates a targeted identity event.
- Recovery/removal: rotate the publisher credential with the deployment script; users can rotate their topic in App settings. Remove the systemd drop-in and ACL/user only when retiring the feature globally.
- Cost: existing self-hosted service; no separate paid provider account.
