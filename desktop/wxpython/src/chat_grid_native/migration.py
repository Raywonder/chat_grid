"""Migrate known legacy client state into Endiginous-owned user paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

from .config import app_data_dir

LEGACY_APP_NAMES = ("Chat Grid", "ChatGrid", "Indigenous")


def _paths() -> tuple[list[Path], list[Path], list[Path]]:
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
        return ([base / name for name in LEGACY_APP_NAMES],
                [home / "Applications" / f"{name}.app" for name in LEGACY_APP_NAMES]
                + [Path("/Applications") / f"{name}.app" for name in LEGACY_APP_NAMES],
                [home / "Desktop" / f"{name}.app" for name in LEGACY_APP_NAMES])
    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    roaming = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    program_files = [
        Path(value)
        for value in (
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramW6432"),
            os.environ.get("ProgramFiles(x86)"),
        )
        if value
    ]
    data = [local / "TappedIn" / name for name in LEGACY_APP_NAMES]
    data += [local / name for name in LEGACY_APP_NAMES]
    data += [roaming / name for name in LEGACY_APP_NAMES]
    installs = [local / "Programs" / name for name in LEGACY_APP_NAMES]
    installs += [root / name for root in program_files for name in LEGACY_APP_NAMES]
    names = [f"{name}.lnk" for name in LEGACY_APP_NAMES]
    shortcut_dirs = [home / "Desktop", roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs"]
    shortcuts = [directory / name for directory in shortcut_dirs for name in names]
    return data, installs, shortcuts


def migrate_legacy_state() -> dict[str, list[str]]:
    """Copy known legacy state, then remove only exact old app paths."""
    data_dirs, install_dirs, shortcuts = _paths()
    destination = app_data_dir()
    destination.mkdir(parents=True, exist_ok=True)
    migrated: list[str] = []
    removed: list[str] = []
    failed: list[str] = []
    for source in data_dirs:
        if not source.is_dir() or source == destination:
            continue
        try:
            for child in source.iterdir():
                target = destination / child.name
                if child.is_dir() and not child.is_symlink():
                    shutil.copytree(child, target, dirs_exist_ok=True)
                elif not target.exists():
                    shutil.copy2(child, target)
            shutil.rmtree(source)
            migrated.append(str(source))
            removed.append(str(source))
        except (OSError, shutil.Error):
            failed.append(str(source))
    for path in [*install_dirs, *shortcuts]:
        if not path.exists():
            continue
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(str(path))
        except OSError:
            failed.append(str(path))
    receipt = {"migrated": migrated, "removed": removed, "failed": failed}
    (destination / "migration-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt
