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
ditto -c -k --sequesterRsrc --keepParent "dist/Endiginous.app" "macos/release/Endiginous-0.4.1-macOS.zip"
rm -rf macos/dmg-root
mkdir -p macos/dmg-root
ditto "dist/Endiginous.app" "macos/dmg-root/Endiginous.app"
ln -s /Applications macos/dmg-root/Applications
hdiutil create -volname "Endiginous" -srcfolder macos/dmg-root -ov -format UDZO "macos/release/Endiginous-0.4.1.dmg"
