# Native upgrade safety and architecture hold

This source-only safety change is not a release. Native version remains unchanged. The previously considered 0.4.24 wrapper candidate and embedded-web packaging were stopped at explicit user direction. No assets were bundled, installer built, or release published. Hosted web 0.4.23 R564/server S426 remains an independent accepted web product.

The required desktop architecture is fully native, with no WebView, embedded web assets or hidden browser execution for the application. Native navigation must preserve movement, rooms, people, items, chat, audio, settings, keyboard and screen-reader access. Existing wxPython code still hosts wx.html2 and does not meet this requirement. A native protocol, world model, controls and audio implementation with parity tests is required before a desktop build is represented as compliant.

Legacy state migration copies missing regular files only, preserves originals, conflicting files, installations and shortcuts, and refuses linked/reparse paths. Access errors are recorded instead of aborting startup. Identical outcomes reuse a content-addressed receipt. No recursive guessed install cleanup remains. Unknown old payload is retained pending a separately verified ownership manifest; this is conservative retention, not proof of a clean upgrade.

Existing update URL maps to a static public artifact allowlist, not account authorization or a user media token. Authentication identities, native callback aliases and AppId remain unchanged.

Tests use synthetic profiles. Isolated clean install/upgrade/uninstall, keyboard/NVDA tests and authorized publisher signing remain future release gates. macOS migration requires platform validation before a Mac release.
