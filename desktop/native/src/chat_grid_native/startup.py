"""Per-user startup registration for Windows and macOS."""

from __future__ import annotations

from pathlib import Path
import plistlib
import sys


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "Endiginous"
LEGACY_RUN_VALUES = ("Endiginous",)


def executable_path() -> Path:
    """Return the command target for the installed or development app."""
    return Path(sys.executable).resolve()


def set_start_with_system(enabled: bool, executable: Path | None = None) -> None:
    """Enable or disable startup for the current desktop user."""
    if sys.platform == "darwin":
        target = executable or executable_path()
        launch_agents = Path.home() / "Library" / "LaunchAgents"
        plist_path = launch_agents / "fm.tappedin.chatgrid.plist"
        if not enabled:
            plist_path.unlink(missing_ok=True)
            return
        launch_agents.mkdir(parents=True, exist_ok=True)
        data = {
            "Label": "fm.tappedin.chatgrid",
            "ProgramArguments": [str(target), "--autostart"],
            "RunAtLoad": True,
            "ProcessType": "Interactive",
        }
        temporary = plist_path.with_suffix(".tmp")
        temporary.write_bytes(plistlib.dumps(data))
        temporary.replace(plist_path)
        return
    if sys.platform != "win32":
        return
    import winreg

    target = executable or executable_path()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            for legacy_value in LEGACY_RUN_VALUES:
                try:
                    winreg.DeleteValue(key, legacy_value)
                except FileNotFoundError:
                    pass
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, f'"{target}" --autostart')
        else:
            for value_name in (RUN_VALUE, *LEGACY_RUN_VALUES):
                try:
                    winreg.DeleteValue(key, value_name)
                except FileNotFoundError:
                    pass


set_start_with_windows = set_start_with_system
