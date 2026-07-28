"""Migrate known legacy client state into Indiginous-owned user paths."""

from __future__ import annotations

from pathlib import Path
import sys

from .config import app_data_dir


def migrate_legacy_state() -> dict[str, list[str]]:
    """Delegate to the shared migration implementation when available."""
    # Native and wxPython packages are built from the same source layout. Keep
    # this copy small so both platform bundles have identical behavior.
    import json
    import os
    import shutil

    names = ("Indiginous", "Endiginous", "Indigenous", "Chat Grid", "ChatGrid")
    home = Path.home()
    if sys.platform == "darwin":
        data_dirs = [home / "Library" / "Application Support" / name for name in names]
        install_dirs = [
            home / "Applications" / f"{name}.app" for name in names
        ] + [Path("/Applications") / f"{name}.app" for name in names]
        shortcuts = [home / "Desktop" / f"{name}.app" for name in names]
    else:
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
        data_dirs = [local / "TappedIn" / name for name in names]
        data_dirs += [local / name for name in names] + [roaming / name for name in names]
        install_dirs = [local / "Programs" / name for name in names]
        install_dirs += [root / name for root in program_files for name in names]
        install_dirs += [root / "BlindSoftware" / name for root in program_files for name in names]
        current_install = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
        if current_install is not None:
            install_dirs = [path for path in install_dirs if path.resolve() != current_install]
        shortcuts = [directory / f"{name}.lnk" for directory in (home / "Desktop", roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs") for name in names]
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
            migrated.append(str(source)); removed.append(str(source))
        except (OSError, shutil.Error):
            failed.append(str(source))
    for path in [*install_dirs, *shortcuts]:
        if not path.exists():
            continue
        try:
            shutil.rmtree(path) if path.is_dir() and not path.is_symlink() else path.unlink()
            removed.append(str(path))
        except OSError:
            failed.append(str(path))
    receipt = {"migrated": migrated, "removed": removed, "failed": failed}
    (destination / "migration-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt
