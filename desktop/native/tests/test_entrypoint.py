from pathlib import Path


def test_windows_build_uses_top_level_entrypoint():
    root = Path(__file__).parents[1]
    build_script = (root / "windows" / "scripts" / "build-windows.ps1").read_text(encoding="utf-8")
    entrypoint = (root / "desktop_entry.py").read_text(encoding="utf-8")
    assert 'Join-Path $Root "desktop_entry.py"' in build_script
    assert "from chat_grid_native.app import main" in entrypoint
    assert "from .app" not in entrypoint
