# Endiginous identity ntfy notifications

- Owner: Endiginous / TappedIn platform service, managed by Devine Creations/TappedIn.
- Provider: self-hosted ntfy at `https://ntfy.tappedin.fm`.
- Publisher: dedicated `chatgrid-alerts` service identity with write-only access to `chatgrid-user-*`.
- Subscribers: read-only access through a random per-identity topic link. The link is bearer-style private metadata and should not be shared.
- Opt-in: disabled by default for existing and future Endiginous identities. Users control it in App settings.
- Clients: settings are server-backed through `ntfy_preferences_get` and `ntfy_preferences_update`, allowing web, Windows, macOS, and iOS clients to share the same identity preference.
- Account source: ntfy is an identity/account preference, not a per-device
  secret. After a user signs in with any enabled BlindSoftware account login
  method, including Mastodon/fediverse authentication, every client should load
  the same account-backed ntfy preference and private subscription status.
- Login independence: ntfy must not depend on the user choosing local
  BlindSoftware username/password login. If the portal authenticates the user
  through Mastodon or another configured provider and maps that login to the
  canonical BlindSoftware account, ntfy preferences and targeted notifications
  use that canonical account.
- Failure behavior: delivery errors, missing publisher credentials, rotated
  topics, disabled topics, or an unavailable ntfy server must not block login,
  world entry, item actions, or account handoff. The targeted event should still
  be stored as an in-grid/account notification, and admin/user surfaces should
  show a non-secret status that explains ntfy is unavailable or needs setup.
- Destination model: future notification destinations should follow the same
  pattern: user-enabled account preference, server-side delivery, no client
  publisher credentials, a clear enabled/configured/error state, and fallback to
  in-grid notifications.
- Secrets: `/home/tappedin/.openclaw/state/chatgrid-ntfy.env`, mode 600, owned by `tappedin`. Never embed publisher credentials in a client.
- Webhooks/callbacks: none. Endiginous publishes outbound JSON to ntfy when its notification service creates a targeted identity event.
- Recovery/removal: rotate the publisher credential with the deployment script; users can rotate their topic in App settings. Remove the systemd drop-in and ACL/user only when retiring the feature globally.
- Cost: existing self-hosted service; no separate paid provider account.
