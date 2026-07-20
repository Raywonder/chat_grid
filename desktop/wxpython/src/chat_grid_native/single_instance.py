"""Windows single-instance activation for the native Endiginous client."""

from __future__ import annotations

import ctypes
import sys


ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0
ACTIVATION_EVENT_NAME = r"Local\fm.tappedin.chatgrid.activate"


class SingleInstanceActivation:
    """Own one named Windows event or notify the already-running instance."""

    def __init__(self) -> None:
        self.handle: int | None = None
        self.is_owner = True
        if sys.platform != "win32":
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        handle = kernel32.CreateEventW(None, False, False, ACTIVATION_EVENT_NAME)
        if not handle:
            raise OSError(ctypes.get_last_error(), "Unable to create Endiginous activation event")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.SetEvent(handle)
            kernel32.CloseHandle(handle)
            self.is_owner = False
            return
        self.handle = handle

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
