# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("wx")
hiddenimports.append("wx.html2")

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
    name="Chat Grid",
    console=False,
    target_arch="x86_64",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="Chat Grid",
)
app = BUNDLE(
    coll,
    name="Chat Grid.app",
    bundle_identifier="fm.tappedin.chatgrid",
    version="0.3.8",
    info_plist={
        "CFBundleDisplayName": "Chat Grid",
        "CFBundleShortVersionString": "0.3.8",
        "CFBundleVersion": "0.3.8",
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "CFBundleURLTypes": [{
            "CFBundleURLName": "Chat Grid Connect",
            "CFBundleURLSchemes": ["chatgrid"],
        }],
    },
)
