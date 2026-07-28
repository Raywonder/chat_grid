from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_macos_package_signs_app_and_pkg_with_apple_identities() -> None:
    script = (ROOT / "macos" / "scripts" / "build-macos.sh").read_text(encoding="utf-8")
    assert "CODESIGN_IDENTITY=${CODESIGN_IDENTITY:-BE7E515BDD5EBAF1818338B6DA159BB020AAC454}" in script
    assert "INSTALLER_IDENTITY=${INSTALLER_IDENTITY:-D6D0AE874B4402280B95B77462501E8655A52914}" in script
    assert "/usr/bin/codesign --deep --force" in script
    assert "pkgbuild $pkg_args --sign \"$INSTALLER_IDENTITY\"" in script
    assert "pkgutil --check-signature" in script


def test_macos_spec_packages_complete_sound_tree() -> None:
    spec = (ROOT / "macos" / "ChatGrid-macOS.spec").read_text(encoding="utf-8")
    assert 'client" / "public" / "sounds"' in spec
    assert 'datas.append((str(sound_root), "sounds"))' in spec
