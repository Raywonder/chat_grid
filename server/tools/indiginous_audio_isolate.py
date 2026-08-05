#!/usr/bin/env python3
"""Separate an agent recording into voice and world-sound WAV stems."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    from app.audio_isolation import AudioIsolationError, available_backends, isolate_file
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.audio_isolation import AudioIsolationError, available_backends, isolate_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("output_dir", type=Path, nargs="?")
    parser.add_argument("--backend", choices=("auto", "demucs", "moises"), default="auto")
    parser.add_argument("--list-backends", action="store_true")
    args = parser.parse_args()
    if args.list_backends:
        print(" ".join(available_backends()) or "none")
        return 0
    if args.input is None or args.output_dir is None:
        parser.error("input and output_dir are required unless --list-backends is used")
    try:
        result = isolate_file(args.input, args.output_dir, backend=args.backend)
    except AudioIsolationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"backend={result.backend}")
    print(f"voice={result.voice_path}")
    print(f"world={result.world_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
