# Chat Grid macOS 0.3.1 unsigned build status

Date: 2026-07-15

- Native startup now presents only the default-server login button and labeled custom-domain login controls.
- Credits and version information are under File > Information > Credits and version.
- Custom domains are normalized to HTTPS `/chatgrid/` endpoints and credential-bearing or insecure URLs are rejected.
- Automated tests: 13 passed.
- Bundle identifier: `fm.tappedin.chatgrid`; deep-link scheme: `chatgrid:`; architecture: x86_64.
- Launch smoke test and ad-hoc deep signature verification passed.
- Developer ID signing and Apple notarization remain intentionally deferred.

Artifacts on the Mac build host:

- `/Users/admin/tmp/chatgrid-native-build/macos/release/ChatGrid-0.3.1-macOS.zip`
  - SHA-256: `7cb8d727680bc6d057aa1cec8bfab8c1656748b6ed8213a2bd015897b2b844d2`
- `/Users/admin/tmp/chatgrid-native-build/macos/release/ChatGrid-0.3.1.dmg`
  - SHA-256: `387e3db90e90e0e20f1f55456ee5f57aec6e5f687240605257f1300a1da397f4`

Do not place these unsigned artifacts in the production automatic-update channel before signing and notarization.
