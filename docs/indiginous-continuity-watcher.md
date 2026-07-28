# Indiginous continuity watcher

The always-on companion service now maintains a private, bounded activity
ledger at `server/runtime/companion.activity.jsonl`. It records summaries of
connection health, world readiness, location/presence changes, direct or
clearly addressed messages, social actions, and item action results.

Ordinary public room messages remain transient. Direct-message text continues
to go to the canonical private Journal; the activity ledger stores only the
sender/location summary. Duplicate message and event IDs are ignored across
reconnects and service restarts. The ledger is capped at 500 entries and 2 MiB
and is best-effort so a storage problem cannot interrupt the world connection.

The service remains `chat-grid-companion.service`, which is already configured
to restart automatically. The state file reports the ledger path for health
checks, but no activity is announced in-world.
