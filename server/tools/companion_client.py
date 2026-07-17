"""Command-file controlled Chat Grid companion client.

This lightweight websocket client gives a server-side agent a visible grid
presence without needing a browser tab. It logs in or registers one account,
joins the world, then follows JSONL commands appended to a local command file.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any

from websockets.asyncio.client import connect


DEFAULT_COMMAND_FILE = Path("runtime/companion.commands.jsonl")
DEFAULT_STATE_FILE = Path("runtime/companion.state.json")
AUTO_SIT_IDLE_SECONDS = 10.0
AUTO_SIT_RETRY_SECONDS = 60.0
BED_MOODS = {"cozy", "dreamy", "playful", "resting", "sleepy", "tired"}
LIE_DOWN_MOODS = {"dreamy", "resting", "sleepy", "tired"}


def _item_kind(item: dict[str, Any]) -> str:
    """Return the normalized furniture/object kind for an outbound item."""

    params = item.get("params") if isinstance(item.get("params"), dict) else {}
    return str(
        params.get("furnitureKind")
        or params.get("objectKind")
        or item.get("type")
        or ""
    ).strip().lower()


def _seating_capacity(item: dict[str, Any]) -> int:
    """Mirror the server's bounded capacity defaults for considerate choices."""

    params = item.get("params") if isinstance(item.get("params"), dict) else {}
    raw_capacity = params.get("seatingCapacity")
    if raw_capacity is not None:
        try:
            return max(0, min(6, int(raw_capacity)))
        except (TypeError, ValueError):
            return 0
    kind = _item_kind(item)
    if kind == "bed":
        return 2
    if kind in {"couch", "sofa", "booth"}:
        return 4
    if kind in {"bench", "loveseat"}:
        return 3
    if kind in {"chair", "stool"}:
        return 1
    return 0


def _is_auto_seatable(item: dict[str, Any], *, mood: str = "settled") -> bool:
    """Return whether the companion may automatically sit on this item."""

    if item.get("carrierId"):
        return False
    params = item.get("params") if isinstance(item.get("params"), dict) else {}
    posture = str(params.get("postureMode") or "").strip().lower()
    kind = _item_kind(item)
    if kind == "bed":
        return mood in BED_MOODS and _seating_capacity(item) > 0
    if posture == "lie":
        return False
    return _seating_capacity(item) > 0 and (
        posture in {"sit", "sit_lie"}
        or kind in {"chair", "couch", "sofa", "bench", "booth", "stool", "loveseat"}
    )


def _choose_auto_seat(
    *,
    items: dict[str, dict[str, Any]],
    users: dict[str, dict[str, Any]],
    x: int,
    y: int,
    mood: str = "settled",
) -> dict[str, Any] | None:
    """Choose a nearby seat whose known occupancy is below capacity."""

    candidates: list[tuple[int, float, str, dict[str, Any]]] = []
    for item in items.values():
        if not _is_auto_seatable(item, mood=mood):
            continue
        try:
            distance = max(abs(int(item.get("x")) - x), abs(int(item.get("y")) - y))
        except (TypeError, ValueError):
            continue
        if distance > 1:
            continue
        capacity = _seating_capacity(item)
        occupants = sum(
            1 for user in users.values() if user.get("seatedItemId") == item.get("id")
        )
        if occupants >= capacity:
            continue
        occupancy_ratio = occupants / capacity
        candidates.append(
            (distance, occupancy_ratio, str(item.get("title") or ""), item)
        )
    return min(candidates, default=None, key=lambda value: value[:3])[3] if candidates else None


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
        state_file: Path,
        session_file: Path,
    ) -> None:
        """Initialize connection and runtime state."""

        self.url = url
        self.origin = origin
        self.username = username
        self.password = password
        self.nickname = nickname
        self.command_file = command_file
        self.state_file = state_file
        self.session_file = session_file
        self.grid_size = 41
        self.client_id = ""
        self.x = 20
        self.y = 20
        self.location_id = ""
        self.posture = "standing"
        self.seated_item_id = ""
        self.mood = "settled"
        self.items: dict[str, dict[str, Any]] = {}
        self.users: dict[str, dict[str, Any]] = {}
        self.connected = False
        self._last_state_write = 0.0
        self._last_world_activity = time.monotonic()
        self._last_auto_sit_attempt = 0.0
        self._offset = 0
        self.last_message_receipt: dict[str, Any] = {}
        self.session_token = self._load_session_token()

    def _load_session_token(self) -> str:
        """Load the private resumable session token, if one exists."""

        try:
            return self.session_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return ""
        except OSError as exc:
            print(f"companion session read failed: {exc}", flush=True)
            return ""

    def _save_session_token(self, token: str) -> None:
        """Persist the session token in a private file for reconnects."""

        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.session_file.with_suffix(self.session_file.suffix + ".tmp")
        temporary.write_text(token + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.session_file)
        os.chmod(self.session_file, 0o600)

    def _clear_session_token(self) -> None:
        """Remove a revoked/expired token so the next attempt can log in."""

        self.session_token = ""
        try:
            self.session_file.unlink()
        except FileNotFoundError:
            pass

    def _write_state(self, *, connected: bool, detail: str = "") -> None:
        """Atomically publish the companion's current connection and world state."""

        visible_users = [
            {
                "id": str(user.get("id") or ""),
                "nickname": str(user.get("nickname") or ""),
                "locationId": str(user.get("locationId") or self.location_id),
                "x": user.get("x"),
                "y": user.get("y"),
            }
            for user in self.users.values()
            if str(user.get("id") or "") != self.client_id
        ]
        visible_users.sort(key=lambda user: (user["nickname"].casefold(), user["id"]))
        state = {
            "connected": connected,
            "detail": detail,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "clientId": self.client_id,
            "nickname": self.nickname,
            "locationId": self.location_id,
            "x": self.x,
            "y": self.y,
            "posture": self.posture,
            "seatedItemId": self.seated_item_id,
            "mood": self.mood,
            "visibleUsers": visible_users,
            "lastMessageReceipt": self.last_message_receipt,
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_file)
        self.connected = connected
        self._last_state_write = time.monotonic()

    async def run_forever(self) -> None:
        """Reconnect forever, keeping the companion available after restarts."""

        self.command_file.parent.mkdir(parents=True, exist_ok=True)
        self.command_file.touch(exist_ok=True)
        self._write_state(connected=False, detail="starting")
        self._offset = self.command_file.stat().st_size
        while True:
            try:
                await self._run_once()
                self._write_state(connected=False, detail="disconnected")
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._write_state(connected=False, detail="reconnecting")
                print(f"companion disconnected: {exc}", flush=True)
                await asyncio.sleep(3)

    async def _run_once(self) -> None:
        async with connect(self.url, origin=self.origin, max_size=2_000_000) as ws:
            if self.session_token:
                self._auth_attempt = "resume"
                await ws.send(_json_packet("auth_resume", sessionToken=self.session_token))
            else:
                self._auth_attempt = "login"
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
                if self._auth_attempt == "resume":
                    self._clear_session_token()
                    self._auth_attempt = "login"
                    await ws.send(
                        _json_packet(
                            "auth_login", username=self.username, password=self.password
                        )
                    )
                elif "check your details" in text or "invalid" in text:
                    await ws.send(
                        _json_packet(
                            "auth_register",
                            username=self.username,
                            password=self.password,
                        )
                    )
                continue
            if msg_type == "auth_result" and message.get("ok"):
                token = str(message.get("sessionToken") or "").strip()
                if token:
                    self.session_token = token
                    self._save_session_token(token)
                continue
            if msg_type == "welcome":
                self.client_id = str(message.get("id") or self.client_id)
                world = message.get("worldConfig") or {}
                self.grid_size = max(1, int(world.get("gridSize") or self.grid_size))
                self.location_id = str(world.get("locationId") or self.location_id)
                player = message.get("player") or {}
                self.x = _clamp_position(player.get("x"), self.x, self.grid_size)
                self.y = _clamp_position(player.get("y"), self.y, self.grid_size)
                self.posture = str(player.get("posture") or "standing")
                self.seated_item_id = str(player.get("seatedItemId") or "")
                self.items = {
                    str(item.get("id")): item
                    for item in message.get("items", [])
                    if isinstance(item, dict) and item.get("id")
                }
                self.users = {
                    str(user.get("id")): user
                    for user in message.get("users", [])
                    if isinstance(user, dict) and user.get("id")
                }
                self._last_world_activity = time.monotonic()
                print(
                    "welcome "
                    f"location={self.location_id} x={self.x} y={self.y} "
                    f"posture={self.posture} items={len(self.items)}",
                    flush=True,
                )
                await ws.send(_json_packet("welcome_ready"))
                await ws.send(_json_packet("update_nickname", nickname=self.nickname))
                await ws.send(_json_packet("update_position", x=self.x, y=self.y))
                self._write_state(connected=True, detail="welcome_ready")
                continue
            if msg_type == "location_changed" and str(message.get("id") or "") == self.client_id:
                self.location_id = str(message.get("locationId") or self.location_id)
                self.x = _clamp_position(message.get("x"), self.x, self.grid_size)
                self.y = _clamp_position(message.get("y"), self.y, self.grid_size)
                self.posture = "standing"
                self.seated_item_id = ""
                self.items.clear()
                self.users.clear()
                self._last_world_activity = time.monotonic()
                print(
                    f"location_changed location={self.location_id} x={self.x} y={self.y}",
                    flush=True,
                )
                self._write_state(connected=True, detail="location_changed")
                continue
            if msg_type == "location_changed":
                user_id = str(message.get("id") or "")
                if user_id:
                    if str(message.get("locationId") or "") == self.location_id:
                        self.users[user_id] = message
                    else:
                        self.users.pop(user_id, None)
                continue
            if msg_type == "item_upsert":
                item = message.get("item")
                if isinstance(item, dict) and item.get("id"):
                    self.items[str(item["id"])] = item
                continue
            if msg_type == "item_delete":
                self.items.pop(str(message.get("id") or ""), None)
                continue
            if msg_type == "update_position" and str(message.get("id") or "") == self.client_id:
                self.x = _clamp_position(message.get("x"), self.x, self.grid_size)
                self.y = _clamp_position(message.get("y"), self.y, self.grid_size)
                self.posture = str(message.get("posture") or "standing")
                self.seated_item_id = str(message.get("seatedItemId") or "")
                self._last_world_activity = time.monotonic()
                print(
                    "position "
                    f"location={self.location_id} x={self.x} y={self.y} "
                    f"posture={self.posture} seatedItemId={self.seated_item_id}",
                    flush=True,
                )
                self._write_state(connected=True, detail="position_updated")
                continue
            if msg_type == "update_position":
                user_id = str(message.get("id") or "")
                if user_id:
                    existing = self.users.get(user_id, {})
                    existing.update(message)
                    if str(existing.get("locationId") or self.location_id) == self.location_id:
                        self.users[user_id] = existing
                continue
            if msg_type == "update_mood" and str(message.get("id") or "") == self.client_id:
                self.mood = str(message.get("mood") or "settled")
                self._write_state(connected=True, detail="mood_updated")
                continue
            if msg_type == "update_mood":
                user_id = str(message.get("id") or "")
                if user_id:
                    existing = self.users.get(user_id, {})
                    existing.update(message)
                    self.users[user_id] = existing
                continue
            if msg_type == "user_left":
                self.users.pop(str(message.get("id") or ""), None)
                continue
            if msg_type in {"chat_message", "direct_message"}:
                sender_id = str(message.get("senderId") or "")
                if sender_id == self.client_id:
                    self.last_message_receipt = {
                        "status": "delivered",
                        "type": msg_type,
                        "message": str(message.get("message") or "")[:500],
                        "targetNickname": str(message.get("targetNickname") or ""),
                        "receivedAt": datetime.now(timezone.utc).isoformat(),
                    }
                    self._write_state(connected=True, detail="message_delivered")
                    print(
                        "message_delivered "
                        f"type={msg_type} target={self.last_message_receipt['targetNickname']}",
                        flush=True,
                    )
                continue
            if msg_type == "item_action_result":
                print(
                    "item_action_result "
                    f"ok={message.get('ok')} action={message.get('action')} "
                    f"itemId={message.get('itemId')} message={message.get('message')}",
                    flush=True,
                )
                continue

    async def _poll_commands(self, ws: Any) -> None:
        while True:
            await asyncio.sleep(0.25)
            if self.connected and time.monotonic() - self._last_state_write >= 30:
                self._write_state(connected=True, detail="heartbeat")
            await self._maybe_auto_sit(ws)
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

    async def _maybe_auto_sit(self, ws: Any) -> None:
        """Settle into a nearby available seat after a short quiet interval."""

        now = time.monotonic()
        if (
            not self.connected
            or self.posture != "standing"
            or now - self._last_world_activity < AUTO_SIT_IDLE_SECONDS
            or now - self._last_auto_sit_attempt < AUTO_SIT_RETRY_SECONDS
        ):
            return
        seat = _choose_auto_seat(
            items=self.items,
            users=self.users,
            x=self.x,
            y=self.y,
            mood=self.mood,
        )
        if seat is None:
            return
        self._last_auto_sit_attempt = now
        await ws.send(_json_packet("item_use", itemId=str(seat["id"])))
        if _item_kind(seat) == "bed" and self.mood in LIE_DOWN_MOODS:
            await ws.send(_json_packet("item_use", itemId=str(seat["id"])))
        print(
            f"auto_sit requested itemId={seat['id']} title={seat.get('title')}",
            flush=True,
        )

    async def _apply_command(self, ws: Any, command: dict[str, Any]) -> None:
        action = str(command.get("action", "")).strip().lower()
        if action == "mood":
            mood = str(command.get("mood") or command.get("value") or "").strip().lower()
            if mood:
                self.mood = mood[:40]
                self._last_world_activity = time.monotonic()
                self._write_state(connected=self.connected, detail="mood_updated")
            return
        if action == "chat":
            message = str(command.get("message", "")).strip()
            if message:
                await ws.send(_json_packet("chat_message", message=message[:500]))
            return
        if action in {"dm", "direct_message"}:
            message = str(command.get("message", "")).strip()
            target_name = str(
                command.get("target") or command.get("nickname") or ""
            ).strip().casefold()
            target_id = str(command.get("targetId") or "").strip()
            if not target_id and target_name:
                for candidate_id, user in self.users.items():
                    nickname = str(user.get("nickname") or "").strip().casefold()
                    if nickname == target_name:
                        target_id = candidate_id
                        break
            if message and target_id:
                await ws.send(
                    _json_packet(
                        "direct_message", targetId=target_id, message=message[:500]
                    )
                )
            elif message:
                self.last_message_receipt = {
                    "status": "target_unavailable",
                    "type": "direct_message",
                    "message": message[:500],
                    "targetNickname": target_name,
                    "receivedAt": datetime.now(timezone.utc).isoformat(),
                }
                self._write_state(connected=True, detail="message_not_sent")
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
            self._last_world_activity = time.monotonic()
            await ws.send(_json_packet("update_position", x=self.x, y=self.y))
            return
        if action == "teleport":
            self.x = _clamp_position(command.get("x"), self.x, self.grid_size)
            self.y = _clamp_position(command.get("y"), self.y, self.grid_size)
            self._last_world_activity = time.monotonic()
            await ws.send(_json_packet("teleport_complete", x=self.x, y=self.y))
            return
        if action == "use":
            item_id = str(command.get("itemId") or "").strip()
            title = str(command.get("title") or command.get("item") or "").strip().lower()
            if not item_id and title:
                for candidate_id, item in self.items.items():
                    candidate_title = str(item.get("title") or "").strip().lower()
                    if candidate_title == title or title in candidate_title:
                        item_id = candidate_id
                        break
            if item_id:
                self._last_world_activity = time.monotonic()
                await ws.send(_json_packet("item_use", itemId=item_id))
            return
        if action in {"pickup", "take"}:
            item_id = str(command.get("itemId") or "").strip()
            if item_id:
                self._last_world_activity = time.monotonic()
                await ws.send(_json_packet("item_pickup", itemId=item_id))
            return
        if action in {"remote_control", "radio_remote"}:
            item_id = str(command.get("itemId") or "").strip()
            control = str(command.get("control") or command.get("remoteAction") or "").strip().lower()
            if item_id and control in {"station_next", "station_previous", "volume_up", "volume_down"}:
                self._last_world_activity = time.monotonic()
                await ws.send(_json_packet("item_remote_control", itemId=item_id, action=control))
            return
        if action in {"update", "decorate"}:
            item_id = str(command.get("itemId") or "").strip()
            params = command.get("params")
            if item_id and isinstance(params, dict):
                self._last_world_activity = time.monotonic()
                packet = {"type": "item_update", "itemId": item_id, "params": params}
                if command.get("title") is not None:
                    packet["title"] = str(command.get("title"))[:80]
                await ws.send(json.dumps(packet, separators=(",", ":")))
            return
        if action in {"go", "location", "change_location"}:
            location_id = str(
                command.get("locationId") or command.get("location") or command.get("target") or ""
            ).strip()
            if location_id:
                self._last_world_activity = time.monotonic()
                await ws.send(_json_packet("change_location", locationId=location_id))


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
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(
            os.getenv("CHGRID_COMPANION_STATE_FILE", str(DEFAULT_STATE_FILE))
        ),
    )
    parser.add_argument(
        "--session-file",
        type=Path,
        default=Path(
            os.getenv(
                "CHGRID_COMPANION_SESSION_FILE",
                "runtime/companion.session",
            )
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
        state_file=args.state_file,
        session_file=args.session_file,
    )
    print(f"companion starting at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    asyncio.run(client.run_forever())


if __name__ == "__main__":
    main()
