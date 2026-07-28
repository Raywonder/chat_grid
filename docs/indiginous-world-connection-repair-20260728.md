# Indiginous world connection repair

Date: 2026-07-28

## Cause

The live Indiginous web client was stale at 0.4.7/R520 while the signaling
server required client revision R536. The Windows laptop's installed 0.4.13
client also had a stale per-user `settings.json` pointing to the retired
`https://blind.software/endiginous/` URL and the old Chat Grid update feed.

## Repair

- Published the validated R536 web client to `/home/blindsoft/public_html/indiginous/`.
- Preserved the previous web tree at
  `/home/blindsoft/public_html/indiginous.backup-before-r536-client-20260728-0528`.
- Updated the laptop settings to `https://blind.software/indiginous/?native_client=1`.
- Updated the laptop feed to the tokenized Indiginous R536 manifest URL.
- Restarted the laptop's installed `Indiginous.exe`.

## Proof

- `https://blind.software/indiginous/version.js` returns 0.4.13/R536.
- The public HTML references `/indiginous/assets/index-Cwsnr_Vg.js` and
  `/indiginous/assets/index-D4XdF8kv.css`; both return HTTP 200.
- The public WebSocket returns `101 Switching Protocols` and an
  `auth_required` response with expected client revision R536.
- Laptop process is running from `C:\Program Files\BlindSoftware\Indiginous\Indiginous.exe`.
- Laptop settings were read back after restart and contain the corrected URLs.

## Remaining limitation

The final authenticated personal-world session still requires Dominique to
complete the browser sign-in in the running laptop app; no owner credentials
were used or exposed during this repair.
