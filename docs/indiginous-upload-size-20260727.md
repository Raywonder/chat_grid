# Indiginous upload-size update — 2026-07-27

## Result

Indiginous admin ambience uploads now accept files up to 5 GiB. Files below
that ceiling remain valid; the requested 1 GiB capacity floor is supported
without rejecting smaller sound assets.

The browser validates the 5 GiB ceiling, streams the file in 180 KiB chunks,
and hashes each chunk incrementally so a multi-gigabyte upload is not copied
into one browser-sized `ArrayBuffer`. The server protocol accepts the same
5 GiB ceiling and enough chunk indexes for a full upload.

## Verification

- `uv run --project server pytest -q server/tests/test_models.py` — 11 passed.
- `npm run lint` — passed.
- `npm run build` — passed; Vite produced the production bundle.
- `chat-grid.service` — active after restart.
- Public `https://blind.software/indiginous/` — HTTP 200.
- Public bundle — confirmed the 5 GiB limit, incremental hashing path, and no
  stale 50 MB rejection text.

## Recovery

- Pre-change public client backup:
  `/home/tappedin/.openclaw/workspace/backups/indiginous-upload-limit-before-20260727-070900/`
- Staged publish tree:
  `/home/tappedin/.openclaw/workspace/projects/chat_grid/deploy/publish/indiginous/`
