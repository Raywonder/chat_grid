"""Native screen-reader speech routing for trusted Indiginous messages."""

from __future__ import annotations

import ctypes
from pathlib import Path
import subprocess
import sys
import threading

MAX_SPEECH_LENGTH = 2000


def _resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parents[2]))


def workstation_locked() -> bool:
    """Return True when Windows does not expose the interactive input desktop."""
    if sys.platform != "win32":
        return False
    user32 = ctypes.windll.user32
    desktop = user32.OpenInputDesktop(0, False, 0x0100)
    if not desktop:
        return True
    user32.CloseDesktop(desktop)
    return False


class ScreenReaderSpeech:
    """Best-effort NVDA/macOS speech adapter with a safe no-op fallback."""

    def __init__(self) -> None:
        self.library = None
        self._retry_timer: threading.Timer | None = None
        self._retry_lock = threading.Lock()
        self._retry_attempts = 0
        if sys.platform != "win32":
            return
        self._load_library()

    def _load_library(self) -> None:
        """Load or re-probe the controller after NVDA restarts."""
        self.library = None
        candidate = _resource_root() / "nvda" / "nvdaControllerClient.dll"
        try:
            library = ctypes.WinDLL(str(candidate))
            library.nvdaController_testIfRunning.restype = ctypes.c_ulong
            library.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
            library.nvdaController_speakText.restype = ctypes.c_ulong
            library.nvdaController_cancelSpeech.restype = ctypes.c_ulong
            self.library = library
        except (OSError, AttributeError):
            self.library = None

    def reconnect(self) -> None:
        """Re-probe the NVDA bridge without requiring an app restart."""
        if sys.platform == "win32":
            self._load_library()

    def available(self) -> bool:
        return bool(self.library and self.library.nvdaController_testIfRunning() == 0)

    def speak(self, text: str, interrupt: bool = False) -> bool:
        """Speak bounded text through NVDA, macOS speech, or a safe fallback."""
        clean = " ".join(str(text).split())[:MAX_SPEECH_LENGTH]
        if not clean or workstation_locked():
            return False
        if sys.platform == "darwin":
            try:
                if interrupt:
                    subprocess.run(["killall", "say"], check=False, capture_output=True)
                subprocess.Popen(["say", clean], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError:
                return False
        if not self.available():
            self._schedule_retry(clean, interrupt)
            return False
        if interrupt:
            self.library.nvdaController_cancelSpeech()
        try:
            spoken = self.library.nvdaController_speakText(clean) == 0
        except (OSError, AttributeError):
            spoken = False
        if not spoken:
            self._schedule_retry(clean, interrupt)
        else:
            with self._retry_lock:
                self._retry_attempts = 0
        return spoken

    def _schedule_retry(self, text: str, interrupt: bool) -> None:
        """Retry short-lived NVDA startup/controller failures quietly."""
        if sys.platform != "win32":
            return
        with self._retry_lock:
            if self._retry_timer is not None:
                return
            if self._retry_attempts >= 3:
                self._retry_attempts = 0
                return
            self._retry_attempts += 1

            def retry() -> None:
                with self._retry_lock:
                    self._retry_timer = None
                self.reconnect()
                self.speak(text, interrupt)

            self._retry_timer = threading.Timer(0.35, retry)
            self._retry_timer.daemon = True
            self._retry_timer.start()
