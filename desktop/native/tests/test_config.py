from pathlib import Path

from chat_grid_native.config import Settings, SettingsStore


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
