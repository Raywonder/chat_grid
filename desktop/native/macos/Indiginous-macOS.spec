# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("wx")
hiddenimports.append("wx.html2")

# Ship the complete local sound library with signed macOS packages. The web
# client still uses its published HTTPS assets, but the bundle remains useful
# for offline repair/asset recovery and never depends on a partial cache.
sound_root = Path(SPECPATH).resolve().parents[2] / "client" / "public" / "sounds"
if sound_root.is_dir():
    datas.append((str(sound_root), "sounds"))

a = Analysis(
    ["macos_entry.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Indiginous",
    console=False,
    # Fail closed toward a modern package. An Intel-only release now triggers
    # Apple's deprecation warning and must be requested explicitly for local
    # compatibility testing; the public Mac build is universal2 by default.
    target_arch=os.environ.get("INDIGINOUS_MAC_TARGET_ARCH", "universal2"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="Indiginous",
)
app = BUNDLE(
    coll,
    name="Indiginous.app",
    bundle_identifier="fm.tappedin.chatgrid",
    version="0.4.18",
    info_plist={
        "CFBundleDisplayName": "Indiginous",
        "CFBundleShortVersionString": "0.4.18",
        "CFBundleVersion": "0.4.18",
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "CFBundleURLTypes": [{
            "CFBundleURLName": "Indiginous Connect",
            "CFBundleURLSchemes": ["indiginous", "chatgrid"],
        }],
    },
)
