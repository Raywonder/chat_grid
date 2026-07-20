import hashlib

import pytest

from chat_grid_native.updater import UpdateManifest


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
