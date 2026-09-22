# Explicit account handoff transport (R564 / S426)

An Indiginous browser opened with a pending blind.software assertion adds
`auth_mode=external` to its WebSocket URL. This marker contains no credential
and grants no access. For that connection only, the server skips automatic
HttpOnly-cookie resume and waits for the normally verified `auth_external`
packet. Invalid or absent assertions never fall back to the saved cookie.

After authentication the client clears its pending assertion; subsequent
connections resume the ordinary cookie path. Existing clients and native
callbacks without the marker retain their previous behavior. The wire audience
`chatgrid` and signed-assertion verifier are unchanged.

This avoids successful cookie authentication being followed by a fatal
`Already authenticated` response to the intended explicit account handoff.
It also allows a valid explicit assertion for a different account to select
that intended account rather than silently retaining the cookie account.

Cookie persistence may finish after world welcome is processed. The auth
controller must not replace an active-world status with “Joining” in that case.

Regression coverage: `client/src/session/authHandoff.test.ts` and
`server/tests/test_explicit_handoff_ordering.py`. Tests use synthetic credentials
and temporary databases, never real account assertions or sessions.

Deploy matching web R564 and server S426 together. Server support must be
activated before marker-enabled clients are served. Preserve session databases,
secrets, historical URL aliases and installed-client identity. A backend
restart affects Indiginous only, never the host or development virtual machines.

