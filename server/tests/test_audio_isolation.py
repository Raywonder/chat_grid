from pathlib import Path

import pytest

from app.audio_isolation import AudioIsolationError, isolate_file
from app.host_tools import find_tool


def test_missing_input_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(AudioIsolationError, match="does not exist"):
        isolate_file(tmp_path / "missing.wav", tmp_path / "out")


def test_shared_tool_root_is_reused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = tmp_path / "bin" / "demucs"
    tool.parent.mkdir()
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(0o755)
    monkeypatch.setenv("CHGRID_SHARED_TOOL_ROOT", str(tmp_path))
    monkeypatch.setenv("PATH", "")
    found = find_tool("demucs")
    assert found is not None
    assert found.executable == str(tool)
    assert found.location == "shared"
