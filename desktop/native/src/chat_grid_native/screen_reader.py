"""Native screen-reader speech routing for trusted Endiginous messages."""

from __future__ import annotations

import ctypes
from pathlib import Path
import subprocess
import sys


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
    """Best-effort NVDA Controller Client adapter with a safe no-op fallback."""

    def __init__(self) -> None:
        self.library = None
        if sys.platform != "win32":
            return
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
            return False
        if interrupt:
            self.library.nvdaController_cancelSpeech()
        return self.library.nvdaController_speakText(clean) == 0
