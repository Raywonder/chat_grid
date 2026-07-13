"""Command-file controlled Chat Grid companion client.

This lightweight websocket client gives a server-side agent a visible grid
presence without needing a browser tab. It logs in or registers one account,
joins the world, then follows JSONL commands appended to a local command file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import time
from typing import Any

from websockets.asyncio.client import connect


DEFAULT_COMMAND_FILE = Path("runtime/companion.commands.jsonl")


def _json_packet(packet_type: str, **values: Any) -> str:
    return json.dumps({"type": packet_type, **values}, separators=(",", ":"))


def _clamp_position(value: object, fallback: int, grid_size: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(0, min(grid_size - 1, parsed))


class CompanionClient:
    """Maintains one Chat Grid websocket session and applies command-file input."""

    def __init__(
        self,
        *,
        url: str,
        origin: str,
        username: str,
        password: str,
        nickname: str,
        command_file: Path,
    ) -> None:
        """Initialize connection and runtime state."""

        self.url = url
        self.origin = origin
        self.username = username
        self.password = password
        self.nickname = nickname
        self.command_file = command_file
        self.grid_size = 41
        self.x = 20
        self.y = 20
        self._offset = 0

    async def run_forever(self) -> None:
        """Reconnect forever, keeping the companion available after restarts."""

        self.command_file.parent.mkdir(parents=True, exist_ok=True)
        self.command_file.touch(exist_ok=True)
        self._offset = self.command_file.stat().st_size
        while True:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"companion disconnected: {exc}", flush=True)
                await asyncio.sleep(3)

    async def _run_once(self) -> None:
        async with connect(self.url, origin=self.origin, max_size=2_000_000) as ws:
            await ws.send(
                _json_packet(
                    "auth_login", username=self.username, password=self.password
                )
            )
            reader = asyncio.create_task(self._read_messages(ws))
            commander = asyncio.create_task(self._poll_commands(ws))
            done, pending = await asyncio.wait(
                {reader, commander}, return_when=asyncio.FIRST_EXCEPTION
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()

    async def _read_messages(self, ws: Any) -> None:
        async for raw in ws:
            message = json.loads(str(raw))
            msg_type = message.get("type")
            if msg_type == "auth_result" and not message.get("ok"):
                text = str(message.get("message", "")).lower()
                if "check your details" in text or "invalid" in text:
                    await ws.send(
                        _json_packet(
                            "auth_register",
                            username=self.username,
                            password=self.password,
                        )
                    )
                continue
            if msg_type == "welcome":
                world = message.get("worldConfig") or {}
                self.grid_size = max(1, int(world.get("gridSize") or self.grid_size))
                player = message.get("player") or {}
                self.x = _clamp_position(player.get("x"), self.x, self.grid_size)
                self.y = _clamp_position(player.get("y"), self.y, self.grid_size)
                await ws.send(_json_packet("welcome_ready"))
                await ws.send(_json_packet("update_nickname", nickname=self.nickname))
                await ws.send(_json_packet("update_position", x=self.x, y=self.y))
                continue

    async def _poll_commands(self, ws: Any) -> None:
        while True:
            await asyncio.sleep(0.25)
            with self.command_file.open("r", encoding="utf-8") as handle:
                handle.seek(self._offset)
                lines = handle.readlines()
                self._offset = handle.tell()
            for raw_line in lines:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    command = json.loads(line)
                except json.JSONDecodeError:
                    continue
                await self._apply_command(ws, command)

    async def _apply_command(self, ws: Any, command: dict[str, Any]) -> None:
        action = str(command.get("action", "")).strip().lower()
        if action == "chat":
            message = str(command.get("message", "")).strip()
            if message:
                await ws.send(_json_packet("chat_message", message=message[:500]))
            return
        if action == "move":
            dx = int(command.get("dx") or 0)
            dy = int(command.get("dy") or 0)
            self.x = _clamp_position(
                self.x + max(-1, min(1, dx)), self.x, self.grid_size
            )
            self.y = _clamp_position(
                self.y + max(-1, min(1, dy)), self.y, self.grid_size
            )
            await ws.send(_json_packet("update_position", x=self.x, y=self.y))
            return
        if action == "teleport":
            self.x = _clamp_position(command.get("x"), self.x, self.grid_size)
            self.y = _clamp_position(command.get("y"), self.y, self.grid_size)
            await ws.send(_json_packet("teleport_complete", x=self.x, y=self.y))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments and environment fallbacks."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv("CHGRID_COMPANION_URL", "ws://127.0.0.1:18765/chatgrid/ws"),
    )
    parser.add_argument(
        "--origin", default=os.getenv("CHGRID_COMPANION_ORIGIN", "https://blind.software")
    )
    parser.add_argument(
        "--username", default=os.getenv("CHGRID_COMPANION_USERNAME", "clawdia")
    )
    parser.add_argument("--password", default=os.getenv("CHGRID_COMPANION_PASSWORD", ""))
    parser.add_argument(
        "--nickname", default=os.getenv("CHGRID_COMPANION_NICKNAME", "Clawdia")
    )
    parser.add_argument(
        "--command-file",
        type=Path,
        default=Path(
            os.getenv("CHGRID_COMPANION_COMMAND_FILE", str(DEFAULT_COMMAND_FILE))
        ),
    )
    return parser.parse_args()


def main() -> None:
    """Run the companion client until interrupted."""

    args = parse_args()
    password = str(args.password).strip()
    if not password:
        raise SystemExit("CHGRID_COMPANION_PASSWORD or --password is required")
    client = CompanionClient(
        url=str(args.url),
        origin=str(args.origin),
        username=str(args.username),
        password=password,
        nickname=str(args.nickname),
        command_file=args.command_file,
    )
    print(f"companion starting at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    asyncio.run(client.run_forever())


if __name__ == "__main__":
    main()
