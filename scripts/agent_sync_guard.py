#!/usr/bin/env python3
"""Prevent agents from editing or releasing from a stale shared checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".agent" / "claims"
CLAIM_TTL_SECONDS = 12 * 60 * 60


def host_name() -> str:
    """Return a stable host name on Windows, macOS, and Linux."""
    return platform.node() or os.environ.get("COMPUTERNAME") or "unknown"


def process_is_alive(pid: object) -> bool:
    """Return whether a host-local claim owner process is still running."""
    try:
        process_id = int(pid)
    except (TypeError, ValueError):
        return False
    if process_id <= 0:
        return False
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def fingerprint(repo: Path) -> dict[str, str]:
    head = run_git(repo, "rev-parse", "HEAD").strip()
    status = run_git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    digest = hashlib.sha256(status.encode("utf-8")).hexdigest()
    return {"head": head, "status_sha256": digest}


def claim_path(repo: Path) -> Path:
    key = hashlib.sha256(str(repo).encode("utf-8")).hexdigest()[:20]
    return STATE_DIR / f"{key}.json"


def load_claim(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        claim = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid active claim {path}: {error}") from error
    if time.time() - float(claim.get("updated_at", 0)) > CLAIM_TTL_SECONDS:
        return None
    return claim


def require_contract() -> None:
    contract = ROOT / "AGENT-CONNECTION-CONTRACT.md"
    if not contract.is_file():
        raise SystemExit(f"missing canonical agent contract: {contract}")


def connect(args: argparse.Namespace) -> int:
    require_contract()
    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"not a git worktree: {repo}")
    current = fingerprint(repo)
    path = claim_path(repo)
    existing = load_claim(path)
    if existing and existing.get("agent") != args.agent:
        same_host = existing.get("host") == host_name()
        if same_host and not process_is_alive(existing.get("pid")):
            print(
                f"taking over abandoned claim from {existing.get('agent')} "
                f"(pid {existing.get('pid')}); source fingerprint will be rechecked"
            )
        else:
            raise SystemExit(
                f"repository is claimed by {existing.get('agent')} since "
                f"{existing.get('updated_at')}; stop and coordinate before editing"
            )
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    claim = {
        "agent": args.agent,
        "repo": str(repo),
        "host": host_name(),
        "pid": os.getpid(),
        "updated_at": time.time(),
        **current,
    }
    path.write_text(json.dumps(claim, indent=2) + "\n", encoding="utf-8")
    print(f"agent claim ok: {args.agent} {repo} @ {current['head']} ({current['status_sha256'][:12]})")
    return 0


def check(args: argparse.Namespace) -> int:
    require_contract()
    repo = Path(args.repo).resolve()
    path = claim_path(repo)
    claim = load_claim(path)
    if not claim:
        raise SystemExit(f"no active claim for {repo}; run connect first")
    if claim.get("agent") != args.agent:
        raise SystemExit(f"claim belongs to {claim.get('agent')}, not {args.agent}")
    current = fingerprint(repo)
    for field in ("head", "status_sha256"):
        if current[field] != claim.get(field):
            raise SystemExit(
                f"stale claim: {field} changed for {repo}; stop, inspect the newer state, "
                "and reacquire instead of continuing from this checkout"
            )
    claim["updated_at"] = time.time()
    path.write_text(json.dumps({**claim, **current}, indent=2) + "\n", encoding="utf-8")
    print(f"agent claim current: {args.agent} {repo} @ {current['head']} ({current['status_sha256'][:12]})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("connect", connect), ("check", check)):
        command = sub.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--agent", required=True)
        command.set_defaults(func=func)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
