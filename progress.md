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

## Next Version Accessibility Navigation Note

- Treat the main game/window canvas as a world-navigation surface, not a web-document surface. When technically possible, auto-disable or suppress screen reader browse/navigation modes while the player is in the main world so arrow keys and other controls stay in the game.
- Keep ordinary text, links, and app/web navigation out of the main canvas. The main surface should expose concise world/location titles and live world narration only.
- Put app links, external links, settings, account actions, downloads, help, and similar web/app options in menus, command palettes, or other explicit navigation surfaces.
- If an in-world item opens web-like content, its navigation should still follow the in-world navigation model first. Browser-style navigation should be presented through world controls/menus rather than leaking page/link browsing into the main play surface.
