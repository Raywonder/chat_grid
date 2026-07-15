"""py2app bundle definition for the official Chat Grid macOS client."""

from setuptools import setup

OPTIONS = {
    "argv_emulation": False,
    "packages": ["chat_grid_native", "requests", "packaging", "certifi"],
    "plist": {
        "CFBundleName": "Chat Grid",
        "CFBundleDisplayName": "Chat Grid",
        "CFBundleIdentifier": "fm.tappedin.chatgrid",
        "CFBundleShortVersionString": "0.3.2",
        "CFBundleVersion": "0.3.2",
        "LSMinimumSystemVersion": "12.0",
        "CFBundleURLTypes": [{
            "CFBundleURLName": "Chat Grid Connect",
            "CFBundleURLSchemes": ["chatgrid"],
        }],
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=["macos/macos_entry.py"],
    name="Chat Grid",
    version="0.3.2",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
