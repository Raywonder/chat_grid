#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
python3 -m venv .venv-macos
. .venv-macos/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[build,test]'
python -m pytest
rm -rf build dist
python macos/setup_macos.py py2app
mkdir -p macos/release
ditto -c -k --sequesterRsrc --keepParent "dist/Chat Grid.app" "macos/release/ChatGrid-0.3.0-macOS.zip"
hdiutil create -volname "Chat Grid" -srcfolder "dist/Chat Grid.app" -ov -format UDZO "macos/release/ChatGrid-0.3.0.dmg"
