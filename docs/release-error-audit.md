# Release Error Audit

Use this note before each Chat Grid release candidate to catch runtime errors that tests and build output do not see.

Run:

```bash
python3 scripts/chatgrid_log_audit.py
```

The script reads the current nginx access/error logs for `blind.software` plus `server/runtime/server.log`, groups Chat Grid failures by endpoint/status, and redacts high-value query strings such as media proxy stream URLs.

## Current Findings From 2026-07-14

- Stale hashed asset 404s appeared during rapid deploys, especially `/chatgrid/assets/index-*.js` and `/chatgrid/assets/index-*.css`. The deploy script now preserves hashed assets, but this should stay on the release checklist because aggressive cleanup can strand active browsers.
- `client_branding.json` returned 404 for some R366 clients. Branding falls back cleanly, but release checks should verify that production deploys include `client_branding.json` when `CHGRID_HOST_ORIGIN` is configured.
- `media_proxy.php` returned 500 twice during radio playback around R366. Next release work should add structured proxy logging for auth-check failures, upstream resolution failures, and HLS rewrite failures without exposing full stream keys.
- `media_proxy.php` returned several 401s. Some are expected when probes lack a browser session, but browser-origin 401s during radio playback should be treated as a regression candidate.
- `HEAD /chatgrid/ws` and some `HEAD /chatgrid/auth/session/check` probes produced noisy 502s because the endpoints are websocket/session-specific. Health checks should use the websocket GET handshake or a purpose-built HTTP health endpoint instead.
- The server runtime log shows frequent `position rate limit ignored` warnings during real movement. This may mean the client is sending movement repeats too quickly for the current budget or that the server warning level is too noisy for expected held-key movement.
- The server runtime log shows repeated `ignoring pre-ready packet` entries for `update_position` and `update_nickname` right after reconnect. Next release work should either queue those until `welcome_ready` or suppress/reclassify expected startup packets.

## Release Checklist

- Run focused server tests for the feature area, plus `server/tests/test_server_message_handling.py` when protocol behavior changes.
- Run `npm run build` from `client/`.
- Run `python3 scripts/chatgrid_log_audit.py` before and after deploy.
- Verify public `/chatgrid/`, `/chatgrid/version.js`, current JS/CSS assets, `help.json`, `client_branding.json` when configured, and `media_proxy.php` with an authenticated browser session when radio/media behavior changed.
- Treat new 500/502 responses, browser-origin 401s, missing current assets, and repeated app warnings as release blockers unless they are understood and documented.
