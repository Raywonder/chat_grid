"""tCast-compatible SHA-256 verified Windows updater."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import urlparse

from packaging.version import InvalidVersion, Version
import requests


LOGGER = logging.getLogger(__name__)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
DEFAULT_SILENT_ARGS = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS"


@dataclass(frozen=True, slots=True)
class UpdateManifest:
    """Resolved Windows update metadata."""

    version: str
    download_url: str
    sha256: str
    file_name: str
    release_notes: str = ""
    silent_args: str = DEFAULT_SILENT_ARGS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpdateManifest":
        """Resolve both flat and tCast platform-nested manifest forms."""
        platform = data.get("platforms", {}).get("windows", {})
        return cls(
            version=str(data.get("version", "")).strip(),
            download_url=str(data.get("downloadUrl") or data.get("download_url") or platform.get("downloadUrl") or platform.get("url") or "").strip(),
            sha256=str(data.get("sha256") or platform.get("sha256") or "").strip().lower(),
            file_name=str(data.get("fileName") or data.get("file_name") or platform.get("fileName") or "EndiginousSetup.exe").strip(),
            release_notes=str(data.get("releaseNotes") or data.get("release_notes") or "").strip(),
            silent_args=str(data.get("silentArgs") or platform.get("silentArgs") or DEFAULT_SILENT_ARGS).strip(),
        )

    def validate(self) -> None:
        """Reject incomplete or unsafe update metadata."""
        Version(self.version)
        if not self.download_url.startswith("https://"):
            raise ValueError("Update download URL must use HTTPS.")
        if not SHA256_RE.fullmatch(self.sha256):
            raise ValueError("Update manifest SHA-256 is missing or invalid.")
        if Path(self.file_name).suffix.lower() != ".exe":
            raise ValueError("Windows update must be an executable installer.")
        published_name = Path(urlparse(self.download_url).path).name
        if published_name != self.file_name:
            raise ValueError("Update URL filename does not match the manifest filename.")
        if self.version not in self.file_name:
            raise ValueError("Update filename does not identify the manifest version.")


class UpdateService:
    """Check, download, verify, and hand off an installer after app exit."""

    def __init__(self, manifest_url: str, current_version: str, root: Path) -> None:
        self.manifest_url = manifest_url
        self.current_version = current_version
        self.root = root

    def check(self) -> UpdateManifest | None:
        """Return a newer valid update, or None."""
        response = requests.get(self.manifest_url, timeout=(5, 20))
        response.raise_for_status()
        manifest = UpdateManifest.from_dict(response.json())
        manifest.validate()
        try:
            return manifest if Version(manifest.version) > Version(self.current_version) else None
        except InvalidVersion as error:
            raise ValueError("Update manifest version is invalid.") from error

    def _dismissal_path(self) -> Path:
        return self.root / "updates" / "dismissed.json"

    def is_dismissed(self, manifest: UpdateManifest) -> bool:
        """Return whether this exact update was recently canceled by the user."""
        try:
            data = json.loads(self._dismissal_path().read_text(encoding="utf-8"))
            return data.get("version") == manifest.version and data.get("sha256") == manifest.sha256 and float(data.get("until", 0)) > time.time()
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return False

    def dismiss(self, manifest: UpdateManifest, *, seconds: int = 24 * 60 * 60) -> None:
        """Remember a canceled update without blocking a manual check."""
        path = self._dismissal_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"version": manifest.version, "sha256": manifest.sha256, "until": time.time() + seconds}) + "\n", encoding="utf-8")
        temporary.replace(path)

    def download(self, manifest: UpdateManifest) -> Path:
        """Download atomically and require the published checksum."""
        manifest.validate()
        updates = self.root / "updates"
        updates.mkdir(parents=True, exist_ok=True)
        target = updates / manifest.file_name
        temporary = target.with_suffix(".download")
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest().lower() == manifest.sha256:
            return target
        digest = hashlib.sha256()
        with requests.get(manifest.download_url, stream=True, timeout=(5, 120)) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        output.write(chunk)
                        digest.update(chunk)
        if digest.hexdigest().lower() != manifest.sha256:
            temporary.unlink(missing_ok=True)
            raise ValueError("Downloaded installer did not match the published SHA-256 checksum.")
        temporary.replace(target)
        return target

    def install_after_exit(self, installer: Path, manifest: UpdateManifest) -> None:
        """Launch a hidden tCast-style helper that waits, installs, and relaunches."""
        helper = self.root / "updates" / "install-update.ps1"
        helper.write_text(
            "param([int]$Pid,[string]$Installer,[string]$Arguments,[string]$App)\n"
            "$mutex = New-Object System.Threading.Mutex($false, 'EndiginousUpdateInstall')\n"
            "if(-not $mutex.WaitOne(0)){ exit 0 }\n"
            "Wait-Process -Id $Pid -ErrorAction SilentlyContinue\n"
            "try {\n"
            "  $p=Start-Process -FilePath $Installer -ArgumentList $Arguments -Wait -PassThru\n"
            "  if($p.ExitCode -eq 0){Start-Process -FilePath $App}\n"
            "} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }\n",
            encoding="utf-8-sig",
        )
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden", "-File", str(helper), "-Pid", str(os_getpid()),
                "-Installer", str(installer), "-Arguments", manifest.silent_args,
                "-App", str(Path(sys.executable).resolve()),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )


def os_getpid() -> int:
    """Small indirection for deterministic tests."""
    import os

    return os.getpid()
