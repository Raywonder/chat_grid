# Indiginous native Qt 6 client

This directory contains the native Qt6 client track for Indiginous. It is
intentionally disjoint from the existing browser and wxPython client trees,
so the older desktop client remains a rollback path until this client has
passed its platform gates. It contains no WebView, browser widget, or HTML UI.

## What is here

- A CMake project targeting C++17 and Qt 6 Widgets.
- A platform-neutral `QMainWindow` with native File, View, and Help menus.
- Native status, settings, and about dialogs.
- A native placeholder world viewport abstraction that paints a simple grid and
  exposes world-state hooks without pretending to implement the world yet.
- A real Qt WebSocket transport using the Indiginous authentication and world
  packet contracts, including secure-origin handshaking, login, guest entry,
  welcome snapshots, movement, location changes, and chat status.
- A native keyboard world viewport with automatic focus on show/activation and
  no user-visible focus workaround in the navigation menu.
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

## Still being ported

### Native navigation milestone (source development, not a release)

The native input resolver separates world, text, dialog, menu and media-remote
contexts. Only unmodified arrows request movement; A adds an item and D requests
pickup/drop instead of moving. Shift+Left/Right turns by 15 degrees, without a
position update. World Tab routes item selection; Shift+Escape leaves world
controls. Semantic requests whose native views are not implemented explicitly
report that limitation; they do not pretend to complete an action.

Position packets retain stable player IDs. Requests do not move the displayed
player optimistically: authoritative self updates move self, peer updates remain
separate, malformed/other-location packets are ignored, and a disconnected world
cannot issue movement. Native text widgets and dialogs retain their keys/focus.
Heading is presentation state only; native spatial audio is not yet implemented.

`indiginous_qt6_navigation_test` is a QtTest executable with real widget key events,
focus checks and a synthetic loopback WebSocket server. Qt Widgets, Network,
WebSockets and Test are required. If unavailable, CMake explicitly warns that the
interaction tests are NOT BUILT. A passing source-contract check is not a compiled
test result. No production account or live server is used by these tests.

- Session-token persistence, browser external-auth handoff, and reconnect
  reconciliation.
- Full world item rendering and interaction, chat/direct-message panes, and
  server-authored UI metadata.
- WebRTC voice, radio/TV streams, item emitters, spatial audio, reconnect
  reconciliation, and local asset packaging.
- Native platform audio/device setup and accessibility polish beyond the
  structural Qt widgets.
- Windows/macOS packaging, signing, installers, update feeds, and deployment.
- iOS. A future iOS client must have its own SwiftUI/native view layer and
  should share only deliberately ported protocol/domain contracts, not this
  desktop widget UI.

The project is not a release claim and is not wired into any existing build,
installer, update feed, or deployment path. Qt6 Widgets, Network, and
WebSockets must be installed on the target build machine before compiling.
