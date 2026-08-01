"""tCast-compatible SHA-256 verified desktop updater."""

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
PLATFORM_KEY = "macos" if sys.platform == "darwin" else "windows"


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
        platform = data.get("platforms", {}).get(PLATFORM_KEY, {})
        default_name = "Indiginous-macOS.zip" if sys.platform == "darwin" else "Indiginous_Setup.exe"
        return cls(
            version=str(data.get("version", "")).strip(),
            download_url=str(data.get("downloadUrl") or data.get("download_url") or platform.get("downloadUrl") or platform.get("url") or "").strip(),
            sha256=str(data.get("sha256") or platform.get("sha256") or "").strip().lower(),
            file_name=str(data.get("fileName") or data.get("file_name") or platform.get("fileName") or default_name).strip(),
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
        expected = ".zip" if sys.platform == "darwin" else ".exe"
        if Path(self.file_name).suffix.lower() != expected:
            raise ValueError(f"Update package must be a {expected} file.")
        stable_name = "Indiginous-macOS.zip" if sys.platform == "darwin" else "Indiginous_Setup.exe"
        if self.file_name != stable_name:
            raise ValueError(f"Update must use the stable {stable_name} filename.")


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
        if sys.platform == "darwin":
            with tempfile.TemporaryDirectory(prefix="indiginious-update-verify-") as directory:
                extracted = Path(directory)
                subprocess.run(["/usr/bin/ditto", "-x", "-k", str(temporary), str(extracted)], check=True)
                app = extracted / "Indiginious.app"
                if not app.is_dir():
                    raise ValueError("Downloaded update does not contain Indiginious.app.")
                subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)], check=True)
                subprocess.run(["/usr/sbin/spctl", "--assess", "--type", "execute", "--verbose=2", str(app)], check=True)
        temporary.replace(target)
        return target

    def install_after_exit(self, installer: Path, manifest: UpdateManifest) -> None:
        """Launch a hidden tCast-style helper that waits, installs, and relaunches."""
        if sys.platform == "darwin":
            executable = Path(sys.executable).resolve()
            running_bundle = next((path for path in executable.parents if path.suffix == ".app"), None)
            destination = running_bundle.parent if running_bundle else Path.home() / "Applications"
            destination.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(
                [
                    "/bin/sh", "-c",
                    'while kill -0 "$1" 2>/dev/null; do sleep 1; done; '
                    'tmp=$(mktemp -d); backup="$3/.Indiginous.app.previous"; '
                    'trap "/bin/rm -rf \\\"$tmp\\\"" EXIT; '
                    '/usr/bin/ditto -x -k "$2" "$tmp" || exit 3; '
                    '[ -d "$tmp/Indiginous.app" ] || exit 4; '
                    '/bin/rm -rf "$3/.Indiginous.app.previous"; '
                    'if [ -e "$3/Indiginous.app" ]; then /bin/mv "$3/Indiginous.app" "$backup" || exit 5; fi; '
                    'if ! /usr/bin/ditto "$tmp/Indiginous.app" "$3/Indiginous.app"; then '
                    '  /bin/rm -rf "$3/Indiginous.app"; '
                    '  [ -e "$backup" ] && /bin/mv "$backup" "$3/Indiginous.app"; exit 6; '
                    'fi; /bin/rm -rf "$backup"; /usr/bin/open "$3/Indiginous.app"',
                    "chatgrid-update", str(os_getpid()), str(installer), str(destination),
                ],
                start_new_session=True,
                close_fds=True,
            )
            return
        helper = self.root / "updates" / "install-update.ps1"
        helper.write_text(
            "param([int]$Pid,[string]$Installer,[string]$Arguments,[string]$App,[string]$InstallDirectory)\n"
            "$Log = Join-Path (Split-Path -Parent $Installer) 'install-update.log'\n"
            "function Write-UpdateLog([string]$Message){ Add-Content -LiteralPath $Log -Value ((Get-Date -Format o) + ' ' + $Message) }\n"
            "$mutex = New-Object System.Threading.Mutex($false, 'IndiginousUpdateInstall')\n"
            "if(-not $mutex.WaitOne(0)){ exit 0 }\n"
            "try {\n"
            "  Write-UpdateLog \"handoff pid=$Pid installer=$Installer app=$App\"\n"
            "  if(Get-Process -Id $Pid -ErrorAction SilentlyContinue){ Wait-Process -Id $Pid -Timeout 120 -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800 }\n"
            "  if(Get-Process -Id $Pid -ErrorAction SilentlyContinue){ Write-UpdateLog 'application did not exit before timeout'; exit 2 }\n"
            "  if(-not (Test-Path -LiteralPath $Installer)){ Write-UpdateLog 'installer is missing'; exit 3 }\n"
            "  $working = Split-Path -Parent $Installer\n"
            "  $installerArguments = $Arguments + ' /DIR=\"' + $InstallDirectory + '\"'\n"
            "  Write-UpdateLog \"install directory=$InstallDirectory\"\n"
            "  $p=Start-Process -FilePath $Installer -ArgumentList $installerArguments -WorkingDirectory $working -WindowStyle Hidden -Wait -PassThru\n"
            "  Write-UpdateLog \"installer exit=$($p.ExitCode)\"\n"
            "  if($p.ExitCode -ne 0 -and $p.ExitCode -ne 3010){ exit $p.ExitCode }\n"
            "  if(-not (Test-Path -LiteralPath $App)){ Write-UpdateLog 'installed application is missing'; exit 4 }\n"
            "  Start-Sleep -Milliseconds 800\n"
            "  Start-Process -FilePath $App -WorkingDirectory (Split-Path -Parent $App)\n"
            "  Write-UpdateLog 'application relaunched'\n"
            "} catch { Write-UpdateLog (\"update failed: \" + $_.Exception.Message); exit 5 }\n"
            "finally { $mutex.ReleaseMutex(); $mutex.Dispose() }\n"
            ,
            encoding="utf-8-sig",
        )
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden", "-File", str(helper), "-Pid", str(os_getpid()),
                "-Installer", str(installer), "-Arguments", manifest.silent_args,
                "-App", str(Path(sys.executable).resolve()),
                "-InstallDirectory", str(Path(sys.executable).resolve().parent),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )


def os_getpid() -> int:
    """Small indirection for deterministic tests."""
    import os

    return os.getpid()
