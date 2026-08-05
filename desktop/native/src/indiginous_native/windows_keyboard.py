"""Disabled compatibility shim for the old Windows keyboard hook module.

Indiginous must never install a process-wide or low-level keyboard hook.  The
native client uses wx/WebView events while its own window is focused instead.
"""

from __future__ import annotations

from typing import Callable


class WindowsWorldKeyHook:
    """Fail-closed compatibility object; it never captures OS input."""

    def __init__(self, on_arrow: Callable[[int], None]) -> None:
        del on_arrow
        raise RuntimeError("Global Indiginous keyboard hooks are disabled for safety")

    def close(self) -> None:
        """Retained for callers that clean up the former hook object."""
