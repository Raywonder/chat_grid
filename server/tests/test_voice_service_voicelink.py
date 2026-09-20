from pathlib import Path
import subprocess
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import voice_service


def test_voicelink_backend_uses_agent_adapter_and_writes_wav(
    monkeypatch, tmp_path: Path
) -> None:
    helper = tmp_path / "voicelink-audio-helper"
    helper.write_text("test helper", encoding="utf-8")
    helper.chmod(0o755)
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["request"] = kwargs["input"].decode("utf-8")
        output_path = Path(command[command.index("--output") + 1])
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(48_000)
            wav_file.writeframes(b"\x00\x00" * 240)
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setenv("CHGRID_VOICE_BACKEND", "voicelink")
    monkeypatch.setenv("CHGRID_VOICELINK_TTS_HELPER", str(helper))
    monkeypatch.setenv("CHGRID_VOICELINK_AGENT", "clawdia")
    monkeypatch.setattr(voice_service.os, "access", lambda *args: True)
    monkeypatch.setattr(voice_service.subprocess, "run", fake_run)

    path, public_url = voice_service.synthesize_to_file(
        "The reply body, not the agent name.", runtime_root=tmp_path
    )

    assert captured["command"][0:3] == [str(helper), "--agent", "clawdia"]
    assert captured["command"][3] == "--output"
    assert captured["request"] == "The reply body, not the agent name."
    assert public_url == f"/voice/{path.name}"
    with wave.open(str(path), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 48_000
        assert wav_file.getnframes() == 240


def test_voicelink_backend_rejects_missing_wav(monkeypatch, tmp_path: Path) -> None:
    helper = tmp_path / "voicelink-audio-helper"
    helper.write_text("test helper", encoding="utf-8")
    helper.chmod(0o755)
    monkeypatch.setenv("CHGRID_VOICE_BACKEND", "voicelink")
    monkeypatch.setenv("CHGRID_VOICELINK_TTS_HELPER", str(helper))
    monkeypatch.setattr(voice_service.os, "access", lambda *args: True)
    monkeypatch.setattr(
        voice_service.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=b"", stderr=b""),
    )

    try:
        voice_service.synthesize_to_file("hello", runtime_root=tmp_path)
    except RuntimeError as exc:
        assert "no WAV audio" in str(exc)
    else:
        raise AssertionError("missing WAV was accepted")


def test_voicelink_is_default_and_never_falls_back_to_elevenlabs(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CHGRID_VOICE_BACKEND", raising=False)
    monkeypatch.setenv("CHGRID_VOICELINK_TTS_HELPER", str(tmp_path / "missing-helper"))
    monkeypatch.setattr(
        voice_service,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ElevenLabs called")),
    )

    try:
        voice_service.synthesize_to_file("hello", runtime_root=tmp_path)
    except RuntimeError as exc:
        assert "VoiceLink TTS helper is unavailable" in str(exc)
    else:
        raise AssertionError("missing VoiceLink helper did not fail closed")
