"""py2app bundle definition for the official Indiginous macOS client."""

from setuptools import setup

OPTIONS = {
    "argv_emulation": False,
    "packages": ["indiginous_native", "requests", "packaging", "certifi"],
    "plist": {
        "CFBundleName": "Indiginous",
        "CFBundleDisplayName": "Indiginous",
        "CFBundleIdentifier": "fm.tappedin.chatgrid",
        "CFBundleShortVersionString": "0.4.22",
        "CFBundleVersion": "0.4.22",
        "LSMinimumSystemVersion": "12.0",
        "CFBundleURLTypes": [{
            "CFBundleURLName": "Indiginous Connect",
            "CFBundleURLSchemes": ["indiginous", "chatgrid"],
        }],
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=["macos/macos_entry.py"],
    name="Indiginous",
        version="0.4.22",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
