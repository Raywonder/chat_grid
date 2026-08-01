#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
PYTHON_BIN=${PYTHON_BIN:-python3}
APP_NAME=${APP_NAME:-Indiginous}
VERSION=${VERSION:-0.4.18}
# Use the verified certificate fingerprints because this login keychain has
# duplicate display names. These are public certificate identifiers, never
# private Apple credentials or keychain secrets.
CODESIGN_IDENTITY=${CODESIGN_IDENTITY:-BE7E515BDD5EBAF1818338B6DA159BB020AAC454}
INSTALLER_IDENTITY=${INSTALLER_IDENTITY:-D6D0AE874B4402280B95B77462501E8655A52914}
SIGN_MACOS=${SIGN_MACOS:-1}
"$PYTHON_BIN" -m venv .venv-macos
. .venv-macos/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[build,test]'
python -m pytest
rm -rf build dist
python -m PyInstaller --noconfirm --clean macos/ChatGrid-macOS.spec
mkdir -p macos/release
rm -f macos/release/Indiginous-macOS.zip macos/release/Indiginous.dmg macos/release/Indiginous.pkg

if [ "$SIGN_MACOS" = "1" ]; then
  test -n "$CODESIGN_IDENTITY"
  test -n "$INSTALLER_IDENTITY"
  /usr/bin/codesign --deep --force --verbose --options runtime --timestamp \
    --sign "$CODESIGN_IDENTITY" "dist/$APP_NAME.app"
  /usr/bin/codesign --verify --deep --strict --verbose=2 "dist/$APP_NAME.app"
fi

ditto -c -k --sequesterRsrc --keepParent "dist/Indiginous.app" "macos/release/Indiginous-macOS.zip"
rm -rf macos/dmg-root
mkdir -p macos/dmg-root
ditto "dist/Indiginous.app" "macos/dmg-root/Indiginous.app"
ln -s /Applications macos/dmg-root/Applications
hdiutil create -volname "Indiginous" -srcfolder macos/dmg-root -ov -format UDZO "macos/release/Indiginous.dmg"

# The PKG is the machine-install artifact. It contains the signed app bundle,
# including the complete packaged sound tree, and installs beneath the
# BlindSoftware vendor root for all users.
pkg_args="--component dist/$APP_NAME.app --install-location /Applications/BlindSoftware --identifier fm.tappedin.indiginous.pkg --version $VERSION"
if [ "$SIGN_MACOS" = "1" ]; then
  pkgbuild $pkg_args --sign "$INSTALLER_IDENTITY" "macos/release/Indiginous.pkg"
  pkgutil --check-signature "macos/release/Indiginous.pkg"
else
  pkgbuild $pkg_args "macos/release/Indiginous.pkg"
fi
