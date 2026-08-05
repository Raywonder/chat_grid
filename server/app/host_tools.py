"""Resolve host-level optional tools shared by multiple Indiginous servers."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat


@dataclass(frozen=True)
class HostTool:
    """An executable discovered from the server, host, or shared tool root."""

    name: str
    executable: str
    location: str


def shared_tool_roots() -> tuple[Path, ...]:
    """Return configured and conventional host-wide tool roots in priority order."""

    values: list[Path] = []
    configured = os.getenv("CHGRID_SHARED_TOOL_ROOT", "").strip()
    if configured:
        values.append(Path(configured).expanduser())
    values.extend(
        [
            Path("/var/lib/indiginous/tools"),
            Path("/opt/indiginous/tools"),
            Path.home() / ".local/share/indiginous/tools",
        ]
    )
    result: list[Path] = []
    for root in values:
        root = root.resolve()
        if root not in result:
            result.append(root)
    return tuple(result)


def find_tool(name: str, *, override: str = "") -> HostTool | None:
    """Find an executable, preferring an explicit override then shared roots."""

    requested = override.strip() or name
    executable = requested.split(maxsplit=1)[0] if requested else name
    explicit = Path(executable).expanduser()
    if explicit.is_absolute() and _is_executable(explicit):
        return HostTool(name, str(explicit), "configured")

    for root in shared_tool_roots():
        candidates = (root / "bin" / executable, root / ".venv" / "bin" / executable, root / executable)
        for candidate in candidates:
            if _is_executable(candidate):
                return HostTool(name, str(candidate), "shared")

    path_match = shutil.which(executable)
    if path_match:
        return HostTool(name, path_match, "path")
    return None


def _is_executable(path: Path) -> bool:
    """Check executable permission bits without requiring an executable mount."""

    try:
        return path.is_file() and bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    except OSError:
        return False


def tool_path(name: str, *, override: str = "") -> str | None:
    """Return a discovered executable path, or ``None`` when unavailable."""

    found = find_tool(name, override=override)
    return found.executable if found else None
