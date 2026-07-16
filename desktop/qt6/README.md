# Chat Grid native Qt 6 foundation

This directory is an isolated, initial Qt 6 Widgets foundation for a native
Chat Grid client. It is intentionally disjoint from the existing browser,
wxPython, and Windows client trees. It contains no WebView, browser widget,
HTML UI, or deployment integration.

## What is here

- A CMake project targeting C++17 and Qt 6 Widgets.
- A platform-neutral `QMainWindow` with native File, View, and Help menus.
- Native status, settings, and about dialogs.
- A native placeholder world viewport abstraction that paints a simple grid and
  exposes world-state hooks without pretending to implement the world yet.
- A protocol-facing client seam with packet names and connection/auth/world
  state transitions taken from `docs/protocol-notes.md` and
  `docs/runtime-flow.md`.
- A Python source-contract test that runs without Qt and rejects accidental
  WebView/browser dependencies in this foundation.

## Configure and build

With Qt 6 Widgets installed:

```sh
cmake -S desktop/qt6 -B build/qt6
cmake --build build/qt6
ctest --test-dir build/qt6 --output-on-failure
```

On a machine without Qt 6, configuration still succeeds and runs the source
contract check; CMake reports that the native executable was skipped. This is
useful for CI/source validation, but it is not a Qt build.

## Deliberately not implemented yet

- WebSocket transport and the server's origin/base-path/session-cookie rules.
- Login/register/resume forms and session-token-to-cookie handoff.
- Welcome snapshot parsing, authoritative movement, location changes, and
  server-authored UI metadata.
- World rendering, item interaction, chat/direct-message outboxes, and admin
  actions.
- WebRTC voice, radio/TV streams, item emitters, spatial audio, reconnect
  reconciliation, and local asset packaging.
- Native platform audio/device setup and accessibility polish beyond the
  structural Qt widgets.
- Windows/macOS packaging, signing, installers, update feeds, and deployment.
- iOS. A future iOS client must have its own SwiftUI/native view layer and
  should share only deliberately ported protocol/domain contracts, not this
  desktop widget UI.

The project is a foundation only; it is not a release claim and is not wired
into any existing build, installer, or deployment path.
