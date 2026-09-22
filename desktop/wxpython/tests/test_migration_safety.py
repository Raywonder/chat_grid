from pathlib import Path
import pytest
import indiginous_native.migration as migration


def setup_paths(tmp_path, monkeypatch):
    source, destination, install = (tmp_path / n for n in ("old", "new", "install"))
    source.mkdir()
    destination.mkdir()
    install.mkdir()
    (install / "unknown.txt").write_text("keep")
    monkeypatch.setattr(migration, "_paths", lambda: ([source], [install], []))
    monkeypatch.setattr(migration, "app_data_dir", lambda: destination)
    return source, destination, install


def test_conflicts_and_nested_files_are_preserved(tmp_path, monkeypatch):
    source, destination, install = setup_paths(tmp_path, monkeypatch)
    for directory in (source, destination):
        (directory / "nested").mkdir()
    (source / "settings.json").write_text("old settings")
    (destination / "settings.json").write_text("current settings")
    (source / "nested" / "same").write_text("old nested")
    (destination / "nested" / "same").write_text("new nested")
    (source / "nested" / "missing").write_text("copy me")
    receipt = migration.migrate_legacy_state()
    assert (source / "settings.json").read_text() == "old settings"
    assert (destination / "settings.json").read_text() == "current settings"
    assert (destination / "nested" / "same").read_text() == "new nested"
    assert (destination / "nested" / "missing").read_text() == "copy me"
    assert (install / "unknown.txt").read_text() == "keep"
    assert len(receipt["conflicts"]) == 2
    assert not receipt["removed"]
    migration.migrate_legacy_state()
    assert (destination / "nested" / "same").read_text() == "new nested"


def test_file_directory_conflict_preserved(tmp_path, monkeypatch):
    source, destination, _ = setup_paths(tmp_path, monkeypatch)
    (source / "conflict").mkdir()
    (source / "conflict" / "only").write_text("keep")
    (destination / "conflict").write_text("existing")
    receipt = migration.migrate_legacy_state()
    assert receipt["conflicts"]
    assert (source / "conflict" / "only").read_text() == "keep"
    assert (destination / "conflict").read_text() == "existing"


def test_io_failure_preserves_original(tmp_path, monkeypatch):
    source, destination, _ = setup_paths(tmp_path, monkeypatch)
    (source / "only").write_text("irreplaceable")
    def fail(*args):
        raise OSError("synthetic failure")
    monkeypatch.setattr(migration.shutil, "copyfileobj", fail)
    receipt = migration.migrate_legacy_state()
    assert receipt["failed"] == [str(source)]
    assert (source / "only").read_text() == "irreplaceable"
    assert not (destination / "only").exists()
    assert not list(destination.glob(".migration-*"))
    assert not receipt["removed"]


def test_link_not_traversed(tmp_path, monkeypatch):
    source, destination, _ = setup_paths(tmp_path, monkeypatch)
    external = tmp_path / "outside"
    external.write_text("private")
    try:
        (source / "link").symlink_to(external)
    except OSError:
        pytest.skip("OS does not grant symlink creation")
    receipt = migration.migrate_legacy_state()
    assert str(source / "link") in receipt["conflicts"]
    assert not (destination / "link").exists()
    assert external.read_text() == "private"


def test_installer_preserves_unknown_and_previous_paths():
    source = (Path(__file__).parents[1] / "installer" / "Indiginous.iss").read_text()
    assert "[InstallDelete]" not in source
    assert "UsePreviousAppDir=yes" in source
    assert 'AppId={{8E748C80-7600-4AA2-97CC-834088D47792}' in source


def test_denied_source_metadata_does_not_abort_startup(tmp_path, monkeypatch):
    source, destination, _ = setup_paths(tmp_path, monkeypatch)
    original = migration._linked
    def denied(path):
        if path == source:
            raise PermissionError("synthetic inaccessible source")
        return original(path)
    monkeypatch.setattr(migration, "_linked", denied)
    receipt = migration.migrate_legacy_state()
    assert receipt["failed"] == [str(source)]
    assert source.exists() and destination.exists()


def test_denied_destination_metadata_does_not_abort_startup(tmp_path, monkeypatch):
    source, destination, _ = setup_paths(tmp_path, monkeypatch)
    def denied(path):
        raise PermissionError("synthetic inaccessible destination ancestor")
    monkeypatch.setattr(migration, "_linked", denied)
    assert migration.migrate_legacy_state()["failed"]
    assert source.exists() and destination.exists()


def test_repeated_outcome_does_not_grow_receipts(tmp_path, monkeypatch):
    source, destination, _ = setup_paths(tmp_path, monkeypatch)
    (source / "settings.json").write_text("old")
    (destination / "settings.json").write_text("current")
    for _ in range(5):
        migration.migrate_legacy_state()
    assert len(list(destination.glob("migration-receipt-*.json"))) == 1
