"""Optional voice/world stem isolation for agent audio input.

Indiginous keeps live peer audio on WebRTC.  This module is intentionally a
separate, file-based boundary for agent recordings and uploaded world audio:
Demucs and Moises-style tools are not safe to invoke in the browser or on the
signalling event loop.  The returned stems are suitable for transcription,
voice activity detection, or world-sound analysis by an agent.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Literal

from .host_tools import find_tool


IsolationBackend = Literal["auto", "demucs", "moises"]


class AudioIsolationError(RuntimeError):
    """Raised when a configured isolation backend cannot produce stems."""


@dataclass(frozen=True)
class IsolatedAudio:
    """Paths to the voice and non-voice/world stems produced by a backend."""

    backend: str
    voice_path: Path
    world_path: Path


def available_backends() -> tuple[str, ...]:
    """Return installed/configured isolation backends without running them."""

    found: list[str] = []
    if find_tool("moises", override=os.getenv("CHGRID_MOISES_COMMAND", "moises")):
        found.append("moises")
    if find_tool("demucs", override=os.getenv("CHGRID_DEMUCS_COMMAND", "demucs")):
        found.append("demucs")
    return tuple(found)


def isolate_file(
    input_path: Path,
    output_dir: Path,
    *,
    backend: IsolationBackend = "auto",
) -> IsolatedAudio:
    """Separate speech/voice from world sound in *input_path*.

    ``auto`` prefers a configured Moises command, then Demucs.  The Moises
    command is deliberately an adapter contract rather than an invented API:
    set ``CHGRID_MOISES_COMMAND`` to a local wrapper accepting
    ``{input}``, ``{output_dir}``, ``{voice_output}``, and ``{world_output}``.
    """

    source = input_path.expanduser().resolve()
    if not source.is_file():
        raise AudioIsolationError(f"audio input does not exist: {source}")
    destination = output_dir.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    chosen = backend
    if chosen == "auto":
        chosen = "moises" if "moises" in available_backends() else "demucs"
    if chosen == "moises":
        return _run_moises(source, destination)
    if chosen == "demucs":
        return _run_demucs(source, destination)
    raise AudioIsolationError(f"unsupported isolation backend: {backend}")


def _run_demucs(source: Path, destination: Path) -> IsolatedAudio:
    """Run Demucs two-stem separation and locate its generated WAV files."""

    configured = os.getenv("CHGRID_DEMUCS_COMMAND", "demucs")
    tool = find_tool("demucs", override=configured)
    if tool is None:
        raise AudioIsolationError(
            "Demucs is not installed; install it or configure CHGRID_MOISES_COMMAND."
        )
    model = os.getenv("CHGRID_DEMUCS_MODEL", "htdemucs")
    _run([tool.executable, "--two-stems=vocals", "-n", model, "-o", str(destination), str(source)])
    stem_dir = destination / model / source.stem
    voice = stem_dir / "vocals.wav"
    world = stem_dir / "no_vocals.wav"
    if not voice.is_file() or not world.is_file():
        raise AudioIsolationError(f"Demucs completed without expected stems in {stem_dir}")
    return IsolatedAudio("demucs", voice, world)


def _run_moises(source: Path, destination: Path) -> IsolatedAudio:
    """Run the configured Moises-compatible local wrapper."""

    template = os.getenv("CHGRID_MOISES_COMMAND", "moises")
    tool = find_tool("moises", override=template)
    if tool is None:
        raise AudioIsolationError(
            "Moises is not installed/configured; set CHGRID_MOISES_COMMAND to a local wrapper."
        )
    voice = destination / f"{source.stem}.voice.wav"
    world = destination / f"{source.stem}.world.wav"
    values = {
        "input": str(source),
        "output_dir": str(destination),
        "voice_output": str(voice),
        "world_output": str(world),
    }
    command = [tool.executable, *[part.format(**values) for part in template.split()[1:]]]
    _run(command)
    if not voice.is_file() or not world.is_file():
        raise AudioIsolationError(
            "Moises wrapper completed without the configured voice/world output files."
        )
    return IsolatedAudio("moises", voice, world)


def _run(command: list[str]) -> None:
    """Run one bounded local audio command without a shell."""

    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=900)
    except FileNotFoundError as exc:
        raise AudioIsolationError(f"audio isolation command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "no command output").strip()[-1000:]
        raise AudioIsolationError(f"audio isolation failed: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioIsolationError("audio isolation timed out after 15 minutes") from exc


def _command_executable(command_template: str) -> str:
    """Return the executable token from a simple command template."""

    return command_template.strip().split(maxsplit=1)[0] if command_template.strip() else ""
