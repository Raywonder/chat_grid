#!/usr/bin/env python3
"""Preflight checks for Endiginous desktop release source and artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


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
    if args.version.lower() not in artifact.name.lower():
        raise SystemExit(f"artifact name does not include {args.version}: {artifact.name}")
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
    source.add_argument("--app-name", default="Endiginous")
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
