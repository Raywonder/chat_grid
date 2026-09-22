"""Migrate known legacy client state into Indiginous-owned user paths."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile

from .config import app_data_dir

LEGACY_APP_NAMES = ("Indiginous", "Indiginious", "Endiginous", "Indigenous", "Chat Grid", "ChatGrid")


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
    installs += [root / "BlindSoftware" / name for root in program_files for name in LEGACY_APP_NAMES]
    # Never remove the directory containing the currently running frozen app.
    # This matters now that the default is Program Files/BlindSoftware/Indiginous.
    current_install = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
    if current_install is not None:
        installs = [path for path in installs if path.resolve() != current_install]
    names = [f"{name}.lnk" for name in LEGACY_APP_NAMES]
    shortcut_dirs = [home / "Desktop", roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs"]
    shortcuts = [directory / name for directory in shortcut_dirs for name in names]
    return data, installs, shortcuts


def _linked(path: Path) -> bool:
    """Do not traverse symlinks or Windows junctions during migration."""
    import stat
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _copy_missing(source: Path, target: Path, conflicts: list[str]) -> int:
    """Copy missing regular files and return their count without deleting originals."""
    if _linked(source) or _linked(target):
        conflicts.append(str(source))
        return 0
    if source.is_dir():
        if target.exists() and not target.is_dir():
            conflicts.append(str(source))
            return 0
        target.mkdir(exist_ok=True)
        copied_count = 0
        for child in source.iterdir():
            copied_count += _copy_missing(child, target / child.name, conflicts)
        return copied_count
    elif source.is_file():
        temporary: Path | None = None
        try:
            if target.exists():
                conflicts.append(str(source))
                return 0
            # Copy completely before exclusive publication. A failed copy must
            # not leave a truncated settings file for the application to load.
            with source.open("rb") as original, tempfile.NamedTemporaryFile(
                dir=target.parent, prefix=".migration-", delete=False
            ) as copied:
                temporary = Path(copied.name)
                shutil.copyfileobj(original, copied)
            os.link(temporary, target)
            return 1
        except FileExistsError:
            conflicts.append(str(source))
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return 0


def migrate_legacy_state() -> dict[str, list[str]]:
    """Copy missing legacy state only; retain originals and all installations."""
    receipt: dict[str, list[str]] = {
        "migrated": [], "removed": [], "failed": [], "conflicts": []
    }
    try:
        data_dirs, _, _ = _paths()
        destination = app_data_dir()
        # Reject linked destination ancestors, including redirected profile roots.
        if any(_linked(path) for path in (destination, *destination.parents)):
            receipt["failed"].append(str(destination))
            return receipt
        destination.mkdir(parents=True, exist_ok=True)
    except OSError:
        receipt["failed"].append("Migration destination or legacy paths unavailable")
        return receipt
    for source in data_dirs:
        try:
            if source == destination or not source.exists():
                continue
            if any(_linked(path) for path in (source, *source.parents)):
                receipt["conflicts"].append(str(source))
                continue
            if source.is_dir():
                copied = _copy_missing(source, destination, receipt["conflicts"])
                if copied:
                    receipt["migrated"].append(str(source))
        except (OSError, shutil.Error):
            receipt["failed"].append(str(source))
    # An exclusive receipt preserves previous migration evidence and never
    # follows an existing receipt symlink. Originals remain the recovery copy.
    if not any(receipt.values()):
        return receipt
    # Identical repeated outcomes reuse immutable evidence instead of growing
    # one new receipt on every application launch.
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    receipt_path = destination / f"migration-receipt-{digest}.json"
    try:
        with receipt_path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError:
        pass
    except OSError:
        receipt["failed"].append(str(receipt_path))
    return receipt
