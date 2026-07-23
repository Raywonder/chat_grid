import hashlib
import inspect

import pytest

from chat_grid_native.updater import UpdateManifest, UpdateService
import chat_grid_native.updater as updater_module


def test_windows_handoff_forces_current_install_directory() -> None:
    source = inspect.getsource(updater_module.UpdateService.install_after_exit)
    assert "InstallDirectory" in source
    assert "/DIR=" in source
    assert "install-update.log" in source


def test_tcast_nested_windows_manifest() -> None:
    checksum = hashlib.sha256(b"installer").hexdigest()
    manifest = UpdateManifest.from_dict({
        "version": "0.2.0",
        "platforms": {"windows": {
            "url": "https://example.test/EndiginousSetup-0.2.0.exe",
            "fileName": "EndiginousSetup-0.2.0.exe",
            "sha256": checksum,
        }},
    })
    manifest.validate()
    assert manifest.version == "0.2.0"
    assert manifest.sha256 == checksum


def test_manifest_rejects_missing_checksum() -> None:
    manifest = UpdateManifest.from_dict({"version": "0.2.0", "downloadUrl": "https://example.test/setup.exe"})
    with pytest.raises(ValueError, match="SHA-256"):
        manifest.validate()


def test_manifest_rejects_version_filename_mismatch() -> None:
    checksum = hashlib.sha256(b"installer").hexdigest()
    manifest = UpdateManifest.from_dict({
        "version": "0.4.3",
        "platforms": {"windows": {
            "url": "https://example.test/EndiginousSetup-0.4.2.exe",
            "fileName": "EndiginousSetup-0.4.2.exe",
            "sha256": checksum,
        }},
    })
    with pytest.raises(ValueError, match="version"):
        manifest.validate()


def test_verified_cached_installer_is_reused(tmp_path) -> None:
    payload = b"installer"
    checksum = hashlib.sha256(payload).hexdigest()
    manifest = UpdateManifest.from_dict({
        "version": "0.2.0",
        "downloadUrl": "https://example.test/EndiginousSetup-0.2.0.exe",
        "fileName": "EndiginousSetup-0.2.0.exe",
        "sha256": checksum,
    })
    target = tmp_path / "updates" / manifest.file_name
    target.parent.mkdir()
    target.write_bytes(payload)
    assert UpdateService("https://example.test/latest.json", "0.1.0", tmp_path).download(manifest) == target


def test_cancel_dismissal_is_scoped_to_exact_manifest(tmp_path) -> None:
    service = UpdateService("https://example.test/latest.json", "0.1.0", tmp_path)
    checksum = hashlib.sha256(b"installer").hexdigest()
    manifest = UpdateManifest.from_dict({
        "version": "0.2.0",
        "downloadUrl": "https://example.test/EndiginousSetup-0.2.0.exe",
        "fileName": "EndiginousSetup-0.2.0.exe",
        "sha256": checksum,
    })
    service.dismiss(manifest)
    assert service.is_dismissed(manifest)
    assert not service.is_dismissed(UpdateManifest.from_dict({
        "version": "0.2.1",
        "downloadUrl": "https://example.test/EndiginousSetup-0.2.1.exe",
        "fileName": "EndiginousSetup-0.2.1.exe",
        "sha256": checksum,
    }))
