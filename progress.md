Original prompt: all updates instead of in main UI can be found within world under users navigational sections for reading.

## 2026-07-15

- Moved the existing changelog reader from the public footer into the connected-world grid dashboard.
- Wrapped it in an accessible `User navigation` landmark and renamed its control to `Read world updates`.
- The grid dashboard is hidden until the authenticated server welcome event, so logged-out users no longer see update content.
- Bumped the browser client revision from R444 to R445.
- Production `/chatgrid/` build and asset-path verification passed; public HTML, JavaScript, CSS, version, branding, help, and changelog return HTTP 200 with correct types.
- WebSocket upgrade returned HTTP 101.
- Visually inspected the fresh R445 logged-out Playwright screenshot: no updates section is present in the landing UI.
- TODO: verify the connected navigation landmark through an authenticated test path when a safe session fixture is available.
