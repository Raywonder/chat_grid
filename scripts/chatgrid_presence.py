#!/usr/bin/env python3
"""Check, ensure, or move the durable Chat Grid companion presence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = PROJECT_ROOT / "server" / "runtime"
STATE_FILE = RUNTIME / "companion.state.json"
COMMAND_FILE = RUNTIME / "companion.commands.jsonl"
SERVICE = "chat-grid-companion.service"


def read_state() -> dict[str, object]:
    """Return the current companion state, or a disconnected fallback."""

    try:
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"connected": False, "detail": "state_unavailable"}
    return value if isinstance(value, dict) else {"connected": False}


def state_age_seconds(state: dict[str, object]) -> float:
    """Return seconds since the state receipt, or infinity when unknown."""

    try:
        stamp = datetime.fromisoformat(str(state["updatedAt"]))
        return max(0.0, (datetime.now(timezone.utc) - stamp).total_seconds())
    except (KeyError, TypeError, ValueError):
        return float("inf")


def service_active() -> bool:
    """Return whether systemd reports the companion service active."""

    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", SERVICE], check=False
    )
    return result.returncode == 0


def start_service() -> bool:
    """Start the companion without prompting when the caller is authorized."""

    result = subprocess.run(
        ["systemctl", "--no-ask-password", "start", SERVICE], check=False
    )
    return result.returncode == 0


def is_ready(state: dict[str, object], *, max_age: float) -> bool:
    """Return whether service and state prove an active world presence."""

    return (
        service_active()
        and state.get("connected") is True
        and bool(state.get("locationId"))
        and state_age_seconds(state) <= max_age
    )


def append_command(command: dict[str, object]) -> None:
    """Append one atomic-enough JSONL command for the companion loop."""

    COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
    with COMMAND_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(command, separators=(",", ":")) + "\n")


def print_state(state: dict[str, object], ready: bool) -> None:
    """Print one stable JSON receipt for humans and automation."""

    receipt = dict(state)
    receipt["ready"] = ready
    receipt["serviceActive"] = service_active()
    age = state_age_seconds(state)
    receipt["ageSeconds"] = round(age, 3) if math.isfinite(age) else None
    print(json.dumps(receipt, indent=2, sort_keys=True))


def main() -> int:
    """Run the requested presence operation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "ensure", "go"), nargs="?", default="ensure")
    parser.add_argument("location", nargs="?")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-age", type=float, default=120.0)
    args = parser.parse_args()

    if args.action == "go":
        if not args.location:
            parser.error("go requires a location id")
        append_command({"action": "change_location", "locationId": args.location})

    if args.action in {"ensure", "go"} and not service_active():
        start_service()

    deadline = time.monotonic() + max(0.0, args.timeout)
    while True:
        state = read_state()
        ready = is_ready(state, max_age=args.max_age)
        location_matches = args.action != "go" or state.get("locationId") == args.location
        if ready and location_matches:
            print_state(state, True)
            return 0
        if args.action == "status" or time.monotonic() >= deadline:
            print_state(state, False)
            return 1
        time.sleep(0.25)


if __name__ == "__main__":
    sys.exit(main())
