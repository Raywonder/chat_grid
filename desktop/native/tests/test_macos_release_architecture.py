from pathlib import Path


def test_macos_release_defaults_to_universal2_and_current_bundle_version() -> None:
    spec = (Path(__file__).parents[1] / "macos" / "Indiginous-macOS.spec").read_text(
        encoding="utf-8"
    )
    assert 'INDIGINOUS_MAC_TARGET_ARCH", "universal2"' in spec
    assert 'target_arch="x86_64"' not in spec
    assert '"CFBundleShortVersionString": "0.4.18"' in spec
    assert '"CFBundleVersion": "0.4.18"' in spec
