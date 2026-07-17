#!/usr/bin/env python3
"""Build seamless web ambience loops and an admin-facing FX catalog."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path("/home/tappedin/public_html/wp-content/uploads/Archive/fx/Ambiance")
OUTPUT_DIR = ROOT / "client/public/sounds/ambience/fx"
PUBLIC_CATALOG = ROOT / "client/public/ambience-catalog.json"
SERVER_CATALOG = ROOT / "server/config/ambience_catalog.json"

CATEGORY_LABELS = {
    "Emrg": "Emergency",
    "Fant": "Fantasy",
    "Farm": "Farm",
    "Forst": "Forest",
    "Hist": "Historical",
    "Home": "Home",
    "Hosp": "Hospital",
    "Ind": "Industrial",
    "Lake": "Lake",
    "Misc": "Miscellaneous",
    "Mrkt": "Market",
    "Offc": "Office",
    "Park": "Park and garden",
    "Prisn": "Prison",
    "Rest": "Restaurant and gathering",
    "Rlgn": "Spiritual",
    "Room": "Room tone",
    "Rurl": "Rural",
    "Schl": "School",
    "Sci": "Science fiction",
    "Sea": "Sea and beach",
    "Subn": "Suburban",
    "Trop": "Tropical",
    "Urbn": "Urban",
}


def probe_duration(path: Path) -> float:
    """Return source duration in seconds."""

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def describe(path: Path) -> tuple[str, str, str]:
    """Create stable id, category, and readable label from an archive filename."""

    stem = path.stem.replace("-Elevenlabs", "")
    match = re.match(r"^AMB([A-Za-z]+)-(.*)$", stem)
    code = match.group(1) if match else "Misc"
    phrase = match.group(2) if match else stem
    category = CATEGORY_LABELS.get(code, code)
    phrase = phrase.replace("_", " ").replace("“", "").replace("”", "")
    phrase = re.sub(r"\s+", " ", phrase).strip(" ,-_")
    suffix = " alternate" if "(1)" in path.stem else ""
    label = f"{category}: {phrase}{suffix}".strip()
    # Keep the complete normalized filename. The previous 48-character cap
    # made distinct source names look identical in menus and on disk.
    slug = re.sub(r"[^a-z0-9]+", "-", f"{code}-{phrase}".lower()).strip("-")
    digest = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:8]
    return f"amb-{slug}-{digest}", category, label


def build_loop(source: Path, target: Path, duration: float) -> None:
    """Encode a web loop whose end crossfades into its beginning."""

    crossfade = min(2.0, max(0.5, duration / 8.0))
    middle_end = max(crossfade, duration - crossfade)
    filter_graph = (
        f"[0:a]atrim=start={crossfade:.6f}:end={middle_end:.6f},asetpts=PTS-STARTPTS[mid];"
        f"[0:a]atrim=start={middle_end:.6f}:end={duration:.6f},asetpts=PTS-STARTPTS[tail];"
        f"[0:a]atrim=start=0:end={crossfade:.6f},asetpts=PTS-STARTPTS[head];"
        f"[tail][head]acrossfade=d={crossfade:.6f}:c1=qsin:c2=qsin[seam];"
        "[mid][seam]concat=n=2:v=0:a=1,aresample=48000,aformat=channel_layouts=stereo[out]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-filter_complex",
            filter_graph,
            "-map",
            "[out]",
            "-c:a",
            "libopus",
            "-b:a",
            "64k",
            "-vbr",
            "on",
            str(target),
        ],
        check=True,
    )


def main() -> int:
    """Build all ElevenLabs ambience sources into one categorized catalog."""

    sources = sorted(SOURCE_DIR.glob("AMB*.wav"), key=lambda path: path.name.casefold())
    if not sources:
        raise RuntimeError(f"No ambience WAV files found in {SOURCE_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    expected_files: set[str] = set()
    for source in sources:
        sound_id, category, label = describe(source)
        target = OUTPUT_DIR / f"{sound_id}.ogg"
        duration = probe_duration(source)
        build_loop(source, target, duration)
        output_duration = probe_duration(target)
        expected_files.add(target.name)
        entries.append(
            {
                "id": sound_id,
                "label": label,
                "category": category,
                "url": f"sounds/ambience/fx/{target.name}?v=20260716-fx-loops",
                "sourceFilename": source.name,
                "durationSeconds": round(output_duration, 3),
                "loopStartSeconds": 0,
                "loopEndSeconds": round(output_duration, 3),
                "seamCrossfadeSeconds": round(min(2.0, max(0.5, duration / 8.0)), 3),
            }
        )
    for old_file in OUTPUT_DIR.glob("*.ogg"):
        if old_file.name not in expected_files:
            old_file.unlink()
    payload = {
        "version": "20260716-fx-loops",
        "source": "TappedIn Archive/fx/Ambiance",
        "sounds": entries,
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    PUBLIC_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    SERVER_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_CATALOG.write_text(rendered, encoding="utf-8")
    SERVER_CATALOG.write_text(rendered, encoding="utf-8")
    print(f"built {len(entries)} seamless ambience loops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
