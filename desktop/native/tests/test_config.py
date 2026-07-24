from pathlib import Path

from chat_grid_native.config import Settings, SettingsStore
import chat_grid_native.migration as migration


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
    destination = local / "TappedIn" / "Endiginous"
    monkeypatch.setattr(migration, "app_data_dir", lambda: destination)
    monkeypatch.setattr(migration.Path, "home", staticmethod(lambda: tmp_path))
    receipt = migration.migrate_legacy_state()
    assert not legacy.exists()
    assert not shortcut.exists()
    assert (destination / "settings.json").exists()
    assert str(legacy) in receipt["migrated"]
