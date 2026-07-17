#!/usr/bin/env python3
"""Summarize Chat Grid runtime and web log errors for release triage."""

from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACCESS_LOG = Path("/var/log/nginx/blind.software.shared-ip-sni.access.log")
DEFAULT_ERROR_LOG = Path("/var/log/nginx/blind.software.shared-ip-sni.error.log")
DEFAULT_SERVER_LOG = DEFAULT_ROOT / "server/runtime/server.log"

ACCESS_RE = re.compile(
    r'^(?P<remote>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) (?P<protocol>[^"]+)" '
    r"(?P<status>\d{3}) (?P<size>\S+)"
)


def tail_lines(path: Path, limit: int) -> list[str]:
    """Return up to the last ``limit`` lines from a text log."""
    if limit <= 0 or not path.exists():
        return []
    with path.open("rb") as fp:
        fp.seek(0, 2)
        end = fp.tell()
        block_size = 8192
        data = bytearray()
        while end > 0 and data.count(b"\n") <= limit:
            read_size = min(block_size, end)
            end -= read_size
            fp.seek(end)
            data[:0] = fp.read(read_size)
    return data.decode("utf-8", errors="replace").splitlines()[-limit:]


def redact_query(path: str) -> str:
    """Keep endpoint signal without preserving stream keys or long query strings."""
    if "?" not in path:
        return path
    base, query = path.split("?", 1)
    if base.endswith("/media_proxy.php") and "url=" in query:
        return f"{base}?url=<redacted>"
    return f"{base}?<query>"


def bucket_path(path: str) -> str:
    """Group cache-busted and hashed URLs into stable buckets."""
    path = redact_query(path)
    path = re.sub(r"/assets/index-[A-Za-z0-9_-]+\.(js|css)$", r"/assets/index-*.\1", path)
    return path


def summarize_access(path: Path, lines: int) -> list[str]:
    """Summarize recent Chat Grid non-2xx/3xx access log entries."""
    statuses: collections.Counter[str] = collections.Counter()
    endpoints: collections.Counter[tuple[str, str]] = collections.Counter()
    examples: dict[tuple[str, str], str] = {}
    for line in tail_lines(path, lines):
        match = ACCESS_RE.match(line)
        if not match:
            continue
        request_path = match.group("path")
        if not request_path.startswith("/chatgrid"):
            continue
        status = match.group("status")
        if int(status) < 400:
            continue
        endpoint = bucket_path(request_path)
        key = (status, endpoint)
        statuses[status] += 1
        endpoints[key] += 1
        examples.setdefault(key, line)

    output: list[str] = []
    output.append("Access status counts:")
    if statuses:
        for status, count in sorted(statuses.items()):
            output.append(f"  {status}: {count}")
    else:
        output.append("  none")

    output.append("")
    output.append("Top failing endpoints:")
    if endpoints:
        for (status, endpoint), count in endpoints.most_common(12):
            output.append(f"  {status} {count}x {endpoint}")
            output.append(f"    example: {examples[(status, endpoint)]}")
    else:
        output.append("  none")
    return output


def summarize_error_log(path: Path, lines: int) -> list[str]:
    """Summarize recent nginx errors mentioning Chat Grid paths."""
    buckets: collections.Counter[str] = collections.Counter()
    examples: dict[str, str] = {}
    for line in tail_lines(path, lines):
        if "/chatgrid" not in line:
            continue
        normalized = re.sub(r"client: [^,]+", "client: <redacted>", line)
        normalized = re.sub(r'upstream: "[^"]+"', 'upstream: "<redacted>"', normalized)
        normalized = re.sub(r'request: "([^"]+)"', lambda m: f'request: "{bucket_path(m.group(1))}"', normalized)
        message = normalized.split("] ", 1)[-1]
        buckets[message] += 1
        examples.setdefault(message, normalized)

    output = ["Nginx error buckets:"]
    if buckets:
        for message, count in buckets.most_common(12):
            output.append(f"  {count}x {message}")
            output.append(f"    example: {examples[message]}")
    else:
        output.append("  none")
    return output


def summarize_server_log(path: Path, lines: int) -> list[str]:
    """Summarize app warnings/errors that should be reviewed before release."""
    buckets: collections.Counter[str] = collections.Counter()
    examples: dict[str, str] = {}
    interesting = (" WARNING ", " ERROR ", " CRITICAL ", "Traceback", "Exception")
    timestamp_re = re.compile(r"^\d{4}-\d{2}-\d{2} ")
    for line in tail_lines(path, lines):
        if not any(token in line for token in interesting):
            continue
        if not timestamp_re.match(line):
            # Traceback bodies are noisy; the timestamped ERROR/WARNING line is
            # the stable release-triage signal.
            continue
        message = re.sub(r"id=[0-9a-f-]{36}", "id=<redacted>", line)
        message = re.sub(r"ip=[0-9a-fA-F:.]+", "ip=<redacted>", message)
        message = re.sub(r"window=\d+", "window=<window>", message)
        message = message.split(" ", 3)[-1] if len(message.split(" ", 3)) == 4 else message
        buckets[message] += 1
        examples.setdefault(message, line)

    output = ["Server warning/error buckets:"]
    if buckets:
        for message, count in buckets.most_common(12):
            output.append(f"  {count}x {message}")
            output.append(f"    example: {examples[message]}")
    else:
        output.append("  none")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-log", type=Path, default=DEFAULT_ACCESS_LOG)
    parser.add_argument("--error-log", type=Path, default=DEFAULT_ERROR_LOG)
    parser.add_argument("--server-log", type=Path, default=DEFAULT_SERVER_LOG)
    parser.add_argument("--lines", type=int, default=5000)
    args = parser.parse_args()

    sections = [
        summarize_access(args.access_log, args.lines),
        summarize_error_log(args.error_log, args.lines),
        summarize_server_log(args.server_log, args.lines),
    ]
    for index, section in enumerate(sections):
        if index:
            print()
        print("\n".join(section))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
