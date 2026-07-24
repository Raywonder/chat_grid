# User-owned agent extensions

Endiginous does not bundle OpenClaw, an agent runtime, gateway service, agent
installer, or agent credentials. That keeps the desktop client focused on the
world and prevents an Endiginous install from changing a user's unrelated
machine setup.

Users may run their own agents separately and connect them through the
published Endiginous APIs or an external integration of their choice. A future
extension manager can use a per-user `Endiginous/UserAgents/` directory, with
one manifest per agent, but those agents must remain user-installed and
user-owned. Installers must never copy, launch, update, or remove anything in
that directory.

The migration code only moves known Endiginous/legacy client state. It does
not inspect or delete user-agent folders, credentials, documents, or unrelated
applications.
