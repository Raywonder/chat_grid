import hashlib
import sys

import pytest

from chat_grid_native.updater import UpdateManifest


def test_tcast_nested_platform_manifest() -> None:
    checksum = hashlib.sha256(b"installer").hexdigest()
    platform = "macos" if sys.platform == "darwin" else "windows"
    file_name = "Endiginous-0.2.0-macOS.zip" if sys.platform == "darwin" else "EndiginousSetup-0.2.0.exe"
    manifest = UpdateManifest.from_dict({
        "version": "0.2.0",
        "platforms": {platform: {
            "url": f"https://example.test/{file_name}",
            "fileName": file_name,
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
    platform = "macos" if sys.platform == "darwin" else "windows"
    suffix = "macOS.zip" if sys.platform == "darwin" else "Setup.exe"
    manifest = UpdateManifest.from_dict({
        "version": "0.4.3",
        "platforms": {platform: {
            "url": f"https://example.test/Endiginous-0.4.2-{suffix}",
            "fileName": f"Endiginous-0.4.2-{suffix}",
            "sha256": checksum,
        }},
    })
    with pytest.raises(ValueError, match="version"):
        manifest.validate()
