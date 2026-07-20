# Third-Party Notices and Distribution Boundaries

Endiginous source code is distributed under the MIT License in `LICENSE`.
That license does not automatically grant rights to every name, logo, sound,
recording, stream, feed, photograph, or other media referenced by or bundled
with a deployment.

## Original project

Endiginous is the Raywonder/TappedIn branded continuation of Chat Grid, which
was originally created by Jage9. The upstream project history remains available
at <https://github.com/jage9/chat_grid>. Forks and modified builds must retain
the MIT copyright and permission notice. The MIT License does not grant
trademark rights or imply endorsement by Jage9.

## Software dependencies

The web, server, Electron, and native desktop clients use third-party
dependencies under their own licenses. Package lock files record the exact
versions used for a release. Redistributors must preserve any notices required
by those packages. In particular, inspect:

- `client/package-lock.json`
- `server/uv.lock`
- `desktop/windows/package-lock.json`
- `desktop/wxpython/pyproject.toml`

## Audio and other media

Media must have a recorded source and redistribution basis before it is put in
a public installer, downloadable archive, or reusable asset pack. Project-made
or commissioned media may be distributed only within the rights granted by
its creator or service terms. Third-party broadcasts, podcasts, music,
meditations, and station branding are not relicensed under MIT merely because
Endiginous can play or reference them.

The current audit and release rules are documented in
`docs/asset-licensing.md`. Files marked `review required` there must not be
represented as MIT-licensed assets or redistributed beyond an already approved
deployment until their rights are confirmed.

## Names and branding

"Endiginous," "Chat Grid," "Jage9," station names, show names, organization
names, and other brands may be protected independently of copyright. Renaming a
fork is allowed by the MIT code license, but a new name must not imply
endorsement, cultural representation, or affiliation that has not been granted.
