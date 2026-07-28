# Indiginous macOS signed package and sound assets

The next macOS release uses the verified Apple Developer ID identities already
present on the owner Mac mini:

- `Developer ID Application` signs the app bundle with hardened runtime and a
  secure timestamp.
- `Developer ID Installer` signs `Indiginous.pkg`.

The build does not print or store Apple keychain secrets. Because the Mac
keychain contains duplicate display names, the default is pinned to the
verified public certificate fingerprints; identity values can be overridden by
environment variables when Apple rotates them.

The PKG installs the signed app under `/Applications/BlindSoftware` and carries
the complete `client/public/sounds` tree inside the app bundle. The shared
client also preloads the published ambience catalog in the background so a
partial browser cache can refill missing sounds without delaying startup or
playing a fallback while a real asset is still loading.

The package is not published by this source change alone. Before publication,
build on the owner Mac, verify `codesign`, `pkgutil`, `spctl`, package contents,
checksums, and a clean install/launch. Keep the existing public artifacts until
that receipt is complete.

## Current build receipt

The owner Mac completed the full 45-test packaging preflight (`43 passed, 2
skipped`) and produced an app containing 141 MB of packaged sounds. The
machine's SSH build session could not access a usable private-key signing
operation: every Developer ID certificate, including the verified fingerprint,
returned `errSecInternalComponent` while signing a nested Python extension.
Therefore the current local PKG is an unsigned internal proof only and has not
replaced the public macOS artifact. A normal signed Mac GUI/keychain session is
still required for the final app/PKG signing and Gatekeeper/notarization proof.
