"""py2app bundle definition for the official Endiginous macOS client."""

from setuptools import setup

OPTIONS = {
    "argv_emulation": False,
    "packages": ["chat_grid_native", "requests", "packaging", "certifi"],
    "plist": {
        "CFBundleName": "Endiginous",
        "CFBundleDisplayName": "Endiginous",
        "CFBundleIdentifier": "fm.tappedin.chatgrid",
        "CFBundleShortVersionString": "0.4.3",
        "CFBundleVersion": "0.4.3",
        "LSMinimumSystemVersion": "12.0",
        "CFBundleURLTypes": [{
            "CFBundleURLName": "Endiginous Connect",
            "CFBundleURLSchemes": ["chatgrid"],
        }],
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=["macos/macos_entry.py"],
    name="Endiginous",
        version="0.4.3",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
