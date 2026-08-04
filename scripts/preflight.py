#!/usr/bin/env python3
"""Preflight checks for Indiginous desktop release source and artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SystemExit(f"missing required file: {path}") from error


def _extract(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text)
    if not match:
        raise SystemExit(f"could not find {label}")
    return match.group(1)


def check_source(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    native_metadata = _read_json(repo / "desktop" / "native" / "release-metadata.json")
    wx_metadata = _read_json(repo / "desktop" / "wxpython" / "release-metadata.json")
    version_js = (repo / "client" / "public" / "version.js").read_text(encoding="utf-8")
    wx_package_version = _extract(
        r'version = "([^"]+)"',
        (repo / "desktop" / "wxpython" / "pyproject.toml").read_text(encoding="utf-8"),
        "wxPython package version",
    )
    native_package_version = _extract(
        r'version = "([^"]+)"',
        (repo / "desktop" / "native" / "pyproject.toml").read_text(encoding="utf-8"),
        "native package version",
    )
    macos_spec = (repo / "desktop" / "native" / "macos" / "ChatGrid-macOS.spec").read_text(encoding="utf-8")
    macos_bundle_version = _extract(r'version="([^"]+)"', macos_spec, "macOS bundle version")
    macos_short_version = _extract(r'"CFBundleShortVersionString": "([^"]+)"', macos_spec, "macOS short version")
    macos_display_name = _extract(r'"CFBundleDisplayName": "([^"]+)"', macos_spec, "macOS display name")
    wx_installer = (repo / "desktop" / "wxpython" / "installer" / "ChatGrid.iss").read_text(encoding="utf-8")
    wx_installer_name = _extract(r'#define MyAppName "([^"]+)"', wx_installer, "Windows installer app name")
    wx_installer_version = _extract(r'#define MyAppVersion "([^"]+)"', wx_installer, "Windows installer version")
    wx_runtime_version = _extract(
        r'__version__ = "([^"]+)"',
        (repo / "desktop" / "wxpython" / "src" / "chat_grid_native" / "__init__.py").read_text(encoding="utf-8"),
        "wxPython runtime version",
    )
    native_runtime_version = _extract(
        r'__version__ = "([^"]+)"',
        (repo / "desktop" / "native" / "src" / "chat_grid_native" / "__init__.py").read_text(encoding="utf-8"),
        "native runtime version",
    )
    client_revision = _extract(r'CHGRID_CLIENT_REVISION = "([^"]+)"', version_js, "client revision")

    expected = {"framework": args.framework, "version": args.version, "revision": args.revision}
    metadata_pairs = {"native": native_metadata, "wxpython": wx_metadata}
    mismatches = [
        f"{label} metadata {key}: expected {value}, found {str(metadata.get(field, ''))}"
        for label, metadata in metadata_pairs.items()
        for key, value, field in (
            ("framework", expected["framework"], "framework"),
            ("version", expected["version"], "releaseVersion"),
            ("revision", expected["revision"], "clientRevision"),
        )
        if str(metadata.get(field, "")) != value
    ]
    if wx_package_version != args.version:
        mismatches.append(f"wxPython pyproject version: expected {args.version}, found {wx_package_version}")
    if native_package_version != args.version:
        mismatches.append(f"native pyproject version: expected {args.version}, found {native_package_version}")
    if wx_runtime_version != args.version:
        mismatches.append(f"wxPython runtime version: expected {args.version}, found {wx_runtime_version}")
    if native_runtime_version != args.version:
        mismatches.append(f"native runtime version: expected {args.version}, found {native_runtime_version}")
    if wx_installer_version != args.version:
        mismatches.append(f"Windows installer version: expected {args.version}, found {wx_installer_version}")
    if wx_installer_name != args.app_name:
        mismatches.append(f"Windows installer app name: expected {args.app_name}, found {wx_installer_name}")
    if macos_display_name != args.app_name:
        mismatches.append(f"macOS display name: expected {args.app_name}, found {macos_display_name}")
    if macos_bundle_version != args.version:
        mismatches.append(f"macOS bundle version: expected {args.version}, found {macos_bundle_version}")
    if macos_short_version != args.version:
        mismatches.append(f"macOS short version: expected {args.version}, found {macos_short_version}")
    if client_revision != args.revision:
        mismatches.append(f"web client revision: expected {args.revision}, found {client_revision}")

    windows_hashes: set[str] = set()
    for manifest_path in (
        repo / "desktop" / "wxpython" / "updates" / "latest-windows.json",
        repo / "desktop" / "native" / "updates" / "latest-windows.json",
    ):
        manifest = _read_json(manifest_path)
        platform = manifest.get("platforms", {}).get("windows", {})
        if not str(platform.get("sha256", "")).strip():
            mismatches.append(f"Windows update manifest has no SHA-256: {manifest_path}")
        else:
            windows_hashes.add(str(platform.get("sha256", "")).strip().lower())
        if str(manifest.get("version", "")).strip() != args.version:
            mismatches.append(f"Windows update manifest version mismatch: {manifest_path}")
        if str(manifest.get("revision", "")).strip() != args.revision:
            mismatches.append(f"Windows update manifest revision mismatch: {manifest_path}")
        update_url = str(platform.get("url", "")).strip()
        if "indiginous" in urlparse(update_url).path.lower():
            mismatches.append(f"Windows update URL must be app-name neutral: {manifest_path}")
        if str(platform.get("fileName", "")).strip() != "Indiginous_Setup.exe":
            mismatches.append(f"Windows update filename must be Indiginous_Setup.exe: {manifest_path}")
    if len(windows_hashes) != 1:
        mismatches.append("Windows update manifests must contain the same artifact SHA-256")

    mac_manifest_path = repo / "desktop" / "native" / "updates" / "latest-macos.json"
    mac_manifest = _read_json(mac_manifest_path)
    mac_platform = mac_manifest.get("platforms", {}).get("macos", {})
    if str(mac_manifest.get("version", "")).strip() != args.version:
        mismatches.append(f"macOS update manifest version mismatch: {mac_manifest_path}")
    if str(mac_manifest.get("revision", "")).strip() != args.revision:
        mismatches.append(f"macOS update manifest revision mismatch: {mac_manifest_path}")
    if str(mac_platform.get("fileName", "")).strip() != "Indiginious-macOS.zip":
        mismatches.append("macOS updater feed must use the stable Indiginious-macOS.zip package")
    if not str(mac_platform.get("sha256", "")).strip():
        mismatches.append(f"macOS update manifest has no SHA-256: {mac_manifest_path}")

    if mismatches:
        raise SystemExit("source preflight failed:\n- " + "\n- ".join(mismatches))
    print(f"source preflight ok: {args.framework} {args.version} {args.revision} at {repo}")
    return 0


def check_artifact(args: argparse.Namespace) -> int:
    artifact = Path(args.artifact).resolve()
    if not artifact.is_file():
        raise SystemExit(f"artifact missing: {artifact}")
    if artifact.stat().st_size <= 0:
        raise SystemExit(f"artifact is empty: {artifact}")
    if args.built_after:
        threshold = datetime.fromisoformat(args.built_after)
        built_at = datetime.fromtimestamp(artifact.stat().st_mtime, tz=threshold.tzinfo)
        if built_at < threshold:
            raise SystemExit(f"artifact is older than {args.built_after}: {built_at.isoformat()}")
    expected_name = "Indiginous_Setup.exe" if artifact.suffix.lower() == ".exe" else "Indiginous-macOS.zip"
    if artifact.name != expected_name:
        raise SystemExit(f"artifact name must be the stable {expected_name}: {artifact.name}")
    print(f"artifact preflight ok: {artifact} ({artifact.stat().st_size} bytes)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    source = subparsers.add_parser("source")
    source.add_argument("--repo", required=True)
    source.add_argument("--framework", required=True)
    source.add_argument("--version", required=True)
    source.add_argument("--revision", required=True)
    source.add_argument("--app-name", default="Indiginous")
    source.set_defaults(func=check_source)

    artifact = subparsers.add_parser("artifact")
    artifact.add_argument("--artifact", required=True)
    artifact.add_argument("--framework", required=True)
    artifact.add_argument("--version", required=True)
    artifact.add_argument("--revision", required=True)
    artifact.add_argument("--built-after")
    artifact.set_defaults(func=check_artifact)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
