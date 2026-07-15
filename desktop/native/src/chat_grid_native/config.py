"""Persistent client settings and application paths."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys


APP_NAME = "Chat Grid"
APP_ID = "fm.tappedin.chatgrid.wxpython"
DEFAULT_URL = "https://blind.software/chatgrid/"
DEFAULT_UPDATE_URL = (
    "https://blind.software/chatgrid/updates/latest-macos.json"
    if sys.platform == "darwin"
    else "https://blind.software/chatgrid/updates/latest-windows.json"
)


def app_data_dir() -> Path:
    """Return the per-user application data directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Chat Grid"
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "TappedIn" / "ChatGrid"


@dataclass(slots=True)
class Settings:
    """User-controlled desktop behavior."""

    grid_url: str = DEFAULT_URL
    start_with_windows: bool = False
    start_minimized: bool = False
    keep_in_tray: bool = False
    auto_connect: bool = True
    auto_update: bool = True
    update_url: str = DEFAULT_UPDATE_URL
    reconnect_initial_seconds: float = 2.0
    reconnect_max_seconds: float = 60.0


class SettingsStore:
    """Load and save settings atomically."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or app_data_dir()
        self.path = self.root / "settings.json"

    def load(self) -> Settings:
        """Load settings, falling back safely when data is absent or invalid."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            known = Settings.__dataclass_fields__
            return Settings(**{key: value for key, value in raw.items() if key in known})
        except (OSError, ValueError, TypeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        """Persist settings without exposing credentials."""
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
