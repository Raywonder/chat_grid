"""Windows per-user startup registration."""

from __future__ import annotations

from pathlib import Path
import sys


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "Chat Grid"


def executable_path() -> Path:
    """Return the command target for the installed or development app."""
    return Path(sys.executable).resolve()


def set_start_with_windows(enabled: bool, executable: Path | None = None) -> None:
    """Enable or disable startup for the current Windows user."""
    if sys.platform != "win32":
        return
    import winreg

    target = executable or executable_path()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, f'"{target}" --autostart')
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass
