Original prompt: this is treeted like a game in a way so use all game dev tools to make client as robust as possible even though its more like a social networking platform. Including binoral audio etc.

## 2026-07-15

- Goal: add an accessible, game-style runtime foundation without turning authentication or social features into game UI.
- Implementing a versioned spatial-audio bridge with HRTF binaural panning, bounded coordinates, reconnect-safe lifecycle, and mono fallback.
- Native settings expose spatial audio as an explicit preference.
- TODO: integrate the server world with the bridge for footsteps, doors, people, environmental loops, and voice positions.
- TODO: add deterministic world-state hooks (`render_game_to_text` and `advanceTime`) in the hosted Web UI when its source tree is available in this workspace.
- TODO: exercise hosted-world interactions with the game Playwright client after the server supplies those hooks.

### Hosted-world smoke test

- Ran the required game Playwright client against `https://blind.software/chatgrid/`.
- Visually inspected `output/web-game/shot-0.png`: the sign-in, connect, audio setup, guide, movement, chat, people, items, help, and updates controls rendered.
- Console contained one HTTP 401 before authentication; no page-rendering crash was observed.
- The page does not currently expose `render_game_to_text` or `advanceTime`, so deterministic authenticated world simulation remains a server-side TODO.
