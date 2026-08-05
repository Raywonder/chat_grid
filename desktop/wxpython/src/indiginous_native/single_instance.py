"""Windows single-instance activation for the native Indiginous client."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys
import tempfile

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows uses the named event path.
    fcntl = None


ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0
ACTIVATION_EVENT_NAME = r"Local\fm.tappedin.chatgrid.activate"


class SingleInstanceActivation:
    """Own one named Windows event or notify the already-running instance."""

    def __init__(self) -> None:
        self.handle: int | None = None
        self._lock_handle = None
        self.is_owner = True
        if sys.platform != "win32":
            self._acquire_posix_lock()
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        handle = kernel32.CreateEventW(None, False, False, ACTIVATION_EVENT_NAME)
        if not handle:
            raise OSError(ctypes.get_last_error(), "Unable to create Indiginous activation event")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.SetEvent(handle)
            kernel32.CloseHandle(handle)
            self.is_owner = False
            return
        self.handle = handle

    def _acquire_posix_lock(self) -> None:
        """Use an OS-released lock on macOS/Linux so crashes cannot strand it."""
        if fcntl is None:
            return
        path = Path(tempfile.gettempdir()) / "Indiginous-single-instance.lock"
        try:
            lock_handle = path.open("a+")
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            try:
                lock_handle.close()
            except UnboundLocalError:
                pass
            self.is_owner = False
            return
        self._lock_handle = lock_handle

    def activation_requested(self) -> bool:
        """Return true once when another launch asks this instance to appear."""
        if self.handle is None or sys.platform != "win32":
            return False
        return ctypes.windll.kernel32.WaitForSingleObject(self.handle, 0) == WAIT_OBJECT_0

    def close(self) -> None:
        """Release the named event owned by this process."""
        if self.handle is not None and sys.platform == "win32":
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
        if self._lock_handle is not None and fcntl is not None:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            self._lock_handle.close()
            self._lock_handle = None
