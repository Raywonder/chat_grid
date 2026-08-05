from pathlib import Path
import pytest

from indiginous_native.config import Settings, SettingsStore
import indiginous_native.migration as migration


def test_installer_policy_file_uses_blindsoftware_vendor_root() -> None:
    installer = Path(__file__).parents[1] / "windows" / "installer" / "Indiginous.iss"
    source = installer.read_text(encoding="utf-8")
    assert "DefaultDirName={autopf}\\BlindSoftware\\{#MyAppName}" in source


def test_settings_round_trip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    expected = Settings(auto_connect=False, start_with_windows=True)
    store.save(expected)
    assert store.load() == expected


def test_invalid_settings_fall_back(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text("not json", encoding="utf-8")
    assert store_defaults(SettingsStore(tmp_path))


def store_defaults(store: SettingsStore) -> bool:
    return store.load() == Settings()


def test_legacy_state_is_migrated_and_old_shortcut_removed(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "local"
    roaming = tmp_path / "roaming"
    legacy = (tmp_path / "Library" / "Application Support" / "Chat Grid") if migration.sys.platform == "darwin" else (local / "TappedIn" / "Chat Grid")
    legacy.mkdir(parents=True)
    (legacy / "settings.json").write_text('{"auto_connect": false}\n', encoding="utf-8")
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    shortcut = desktop / ("Chat Grid.app" if migration.sys.platform == "darwin" else "Chat Grid.lnk")
    shortcut.write_text("legacy", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))
    destination = local / "TappedIn" / "Indiginous"
    monkeypatch.setattr(migration, "app_data_dir", lambda: destination)
    monkeypatch.setattr(migration.Path, "home", staticmethod(lambda: tmp_path))
    receipt = migration.migrate_legacy_state()
    assert not legacy.exists()
    assert not shortcut.exists()
    assert (destination / "settings.json").exists()
    assert str(legacy) in receipt["migrated"]


@pytest.mark.skipif(migration.sys.platform == "darwin", reason="Windows install roots are not used on macOS")
def test_legacy_install_roots_are_removed_when_accessible(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "local"
    roaming = tmp_path / "roaming"
    program_files = tmp_path / "Program Files"
    old_install = program_files / "Chat Grid"
    old_install.mkdir(parents=True)
    (old_install / "old.exe").write_bytes(b"old")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.setenv("ProgramW6432", "")
    monkeypatch.setenv("ProgramFiles(x86)", "")
    destination = local / "TappedIn" / "Indiginous"
    monkeypatch.setattr(migration, "app_data_dir", lambda: destination)
    receipt = migration.migrate_legacy_state()
    assert not old_install.exists()
    assert str(old_install) in receipt["removed"]


@pytest.mark.skipif(migration.sys.platform == "darwin", reason="Windows install roots are not used on macOS")
def test_blindsoftware_install_root_is_removed_when_accessible(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "local"
    roaming = tmp_path / "roaming"
    program_files = tmp_path / "Program Files"
    old_install = program_files / "BlindSoftware" / "Indiginous"
    old_install.mkdir(parents=True)
    (old_install / "old.exe").write_bytes(b"old")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.setenv("ProgramW6432", "")
    monkeypatch.setenv("ProgramFiles(x86)", "")
    destination = local / "TappedIn" / "Indiginous"
    monkeypatch.setattr(migration, "app_data_dir", lambda: destination)
    receipt = migration.migrate_legacy_state()
    assert not old_install.exists()
    assert str(old_install) in receipt["removed"]
