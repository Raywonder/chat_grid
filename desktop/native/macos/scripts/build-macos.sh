#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
PYTHON_BIN=${PYTHON_BIN:-python3}
"$PYTHON_BIN" -m venv .venv-macos
. .venv-macos/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[build,test]'
python -m pytest
rm -rf build dist
python -m PyInstaller --noconfirm --clean macos/ChatGrid-macOS.spec
mkdir -p macos/release
ditto -c -k --sequesterRsrc --keepParent "dist/Chat Grid.app" "macos/release/ChatGrid-0.3.6-macOS.zip"
hdiutil create -volname "Chat Grid" -srcfolder "dist/Chat Grid.app" -ov -format UDZO "macos/release/ChatGrid-0.3.6.dmg"
