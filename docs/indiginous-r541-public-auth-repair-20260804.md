# Indiginous R541 public auth repair

- Date: 2026-08-04
- Source commit: `e2b76b4871c4fecfecf72859d4871c712816ed17`
- Staged client: `deploy/publish/indiginous-r541-auth-repair-20260804-1015`
- Published target: `/home/blindsoft/public_html/indiginous`
- Rollback copy: `/mnt/backups/chat-grid/indiginous-before-r541-auth-20260804-1015`
- Public revision: `0.4.18` / `R541`

## Cause

The public `/indiginous/` client was still R540 while the Windows installer
and current source were R541. The stale web client prevented the desktop
browser-auth handoff from reaching the current world admission flow.

## Verification

- `https://blind.software/indiginous/version.js` reports `0.4.18` / `R541`.
- The published R541 JavaScript asset returns HTTP 200.
- `wss://blind.software/indiginous/ws` with origin `https://blind.software`
  connects and returns `auth_required` with expected revision `R541`.
- Focused server auth/session tests: 19 passed.
- Windows updater tests: 6 passed.
- Unverified: hands-on Windows desktop sign-in and world entry after this
  deployment, because the Windows client is not connected to this session.
