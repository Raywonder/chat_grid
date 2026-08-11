"""Command-file controlled Indiginous companion client.

This lightweight websocket client gives a server-side agent a visible grid
presence without needing a browser tab. It logs in or registers one account,
joins the world, then follows JSONL commands appended to a local command file.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import re
from typing import Any

try:
    from app.voice_service import synthesize_to_file
    from app.claudia_writing import record_inworld_direct_message
    from app.activity_ledger import ActivityLedger
except ModuleNotFoundError:  # direct systemd execution puts us in server/tools
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.voice_service import synthesize_to_file
    from app.claudia_writing import record_inworld_direct_message
    from app.activity_ledger import ActivityLedger

from websockets.asyncio.client import connect

try:
    from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
    from av import AudioFrame
    LIVE_GRID_VOICE_AVAILABLE = True
except ModuleNotFoundError:
    MediaStreamTrack = object
    RTCPeerConnection = None
    RTCSessionDescription = None
    AudioFrame = None
    LIVE_GRID_VOICE_AVAILABLE = False


DEFAULT_COMMAND_FILE = Path("runtime/companion.commands.jsonl")
DEFAULT_STATE_FILE = Path("runtime/companion.state.json")
PUBLIC_VOICE_DIR = Path("/home/blindsoft/public_html/indiginous/voice")
AUTO_SIT_IDLE_SECONDS = 10.0
AUTO_SIT_RETRY_SECONDS = 60.0
COMMAND_POLL_SECONDS = 0.10
STATE_HEARTBEAT_SECONDS = 10.0
AUTO_REACTION_COOLDOWN_SECONDS = 7.0
AUTO_POSTURE_REACTION_COOLDOWN_SECONDS = 12.0
BED_MOODS = {"cozy", "dreamy", "playful", "resting", "sleepy", "tired"}
LIE_DOWN_MOODS = {"dreamy", "resting", "sleepy", "tired"}
GRID_AUDIO_RATE = 48000
GRID_AUDIO_FRAME_SAMPLES = 960  # 20 ms at 48 kHz, matching browser Opus cadence
OPENCLAW_BIN = os.environ.get("INDIGINOUS_OPENCLAW_BIN", "/home/tappedin/.local/bin/openclaw")
WORLD_CHAT_AGENT_TIMEOUT_SECONDS = max(
    8, int(os.environ.get("INDIGINOUS_WORLD_CHAT_TIMEOUT", "45"))
)
WORLD_CHAT_ALIASES = {"clawdia", "claudia", "missi"}


if LIVE_GRID_VOICE_AVAILABLE:
    class GridVoiceTrack(MediaStreamTrack):
        """Continuous WebRTC microphone-shaped track for companion speech."""

        kind = "audio"

        def __init__(self) -> None:
            super().__init__()
            self._frames: asyncio.Queue[bytes] = asyncio.Queue(maxsize=300)
            self._pts = 0

        def clear(self) -> None:
            while True:
                try:
                    self._frames.get_nowait()
                except asyncio.QueueEmpty:
                    return

        def enqueue_pcm(self, pcm: bytes) -> None:
            frame_bytes = GRID_AUDIO_FRAME_SAMPLES * 2
            for offset in range(0, len(pcm), frame_bytes):
                chunk = pcm[offset:offset + frame_bytes]
                if len(chunk) < frame_bytes:
                    chunk += b"\x00" * (frame_bytes - len(chunk))
                try:
                    self._frames.put_nowait(chunk)
                except asyncio.QueueFull:
                    try:
                        self._frames.get_nowait()
                        self._frames.put_nowait(chunk)
                    except asyncio.QueueEmpty:
                        pass

        async def recv(self) -> Any:
            if self.readyState != "live":
                raise RuntimeError("Grid voice track is not live")
            try:
                pcm = self._frames.get_nowait()
            except asyncio.QueueEmpty:
                pcm = b"\x00" * (GRID_AUDIO_FRAME_SAMPLES * 2)
            frame = AudioFrame(format="s16", layout="mono", samples=GRID_AUDIO_FRAME_SAMPLES)
            frame.planes[0].update(pcm)
            frame.sample_rate = GRID_AUDIO_RATE
            frame.pts = self._pts
            frame.time_base = Fraction(1, GRID_AUDIO_RATE)
            self._pts += GRID_AUDIO_FRAME_SAMPLES
            await asyncio.sleep(GRID_AUDIO_FRAME_SAMPLES / GRID_AUDIO_RATE)
            return frame

else:
    GridVoiceTrack = None


def _item_kind(item: dict[str, Any]) -> str:
    """Return the normalized furniture/object kind for an outbound item."""

    params = item.get("params") if isinstance(item.get("params"), dict) else {}
    return str(
        params.get("furnitureKind")
        or params.get("objectKind")
        or item.get("type")
        or ""
    ).strip().lower()


def _is_addressed_to_companion(message: str, nickname: str) -> bool:
    """Return whether a room message clearly addresses the in-world companion."""

    aliases = set(WORLD_CHAT_ALIASES)
    normalized_nickname = re.sub(r"[^a-z0-9]+", " ", nickname.casefold()).strip()
    if normalized_nickname:
        aliases.add(normalized_nickname)
    lowered = message.casefold()
    return any(
        re.search(rf"(?<![a-z0-9])@?{re.escape(alias)}(?![a-z0-9])", lowered)
        for alias in aliases
    )


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


def _direct_world_intent(text: str) -> tuple[str, str] | None:
    """Extract only strong, explicit movement requests from a private DM."""

    normalized = re.sub(r"\s+", " ", text.casefold()).strip(" .!?\t")
    patterns = (
        (r"^(?:come|walk|move|go) (?:over )?(?:to )?(?:me|here)$", "person"),
        (r"^(?:sit|lie) (?:down )?(?:on|in|at) (.+)$", "seat"),
        (r"^(?:come|walk|move|go) (?:over )?(?:and )?(?:sit|lie) (?:down )?(?:on|in|at) (.+)$", "seat"),
        (r"^(?:come|walk|move|go) (?:over )?(?:to )?(.+)$", "target"),
    )
    for pattern, kind in patterns:
        match = re.match(pattern, normalized)
        if match:
            target = (match.group(1) if match.groups() else "me").strip()
            target = re.sub(r"^the ", "", target)
            if target and len(target) <= 80:
                return kind, target
    return None


class CompanionClient:
    """Maintains one Indiginous websocket session and applies command-file input."""

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
        session_file: Path | None = None,
        activity_file: Path | None = None,
    ) -> None:
        """Initialize connection and runtime state."""

        self.url = url
        self.origin = origin
        self.username = username
        self.password = password
        self.nickname = nickname
        self.command_file = command_file
        self.state_file = state_file
        self.session_file = session_file or state_file.with_name("companion.session")
        self.activity_ledger = ActivityLedger(
            activity_file or state_file.with_name("companion.activity.jsonl")
        )
        self.grid_size = 41
        self.client_id = ""
        self.x = 20
        self.y = 20
        self.location_id = ""
        self.posture = "standing"
        self.seated_item_id = ""
        self.mood = "settled"
        self.focus_mode = False
        self.items: dict[str, dict[str, Any]] = {}
        self.users: dict[str, dict[str, Any]] = {}
        self.connected = False
        self._last_state_write = 0.0
        self._last_world_activity = time.monotonic()
        self._last_auto_sit_attempt = 0.0
        self._last_auto_reaction = 0.0
        self._last_posture_reaction = 0.0
        self._pending_lie_item_id = ""
        self._offset = 0
        self.last_message_receipt: dict[str, Any] = {}
        self._grid_voice_peers: dict[str, Any] = {}
        # Keep a bounded room-local context window so reconnects do not make
        # the companion blind to the public conversation.  This is memory
        # only; private DMs continue through the canonical Journal path.
        self.recent_room_messages: list[dict[str, str]] = []
        self._world_chat_reply_task: asyncio.Task[Any] | None = None
        self._grid_voice_track = GridVoiceTrack() if LIVE_GRID_VOICE_AVAILABLE else None
        self.session_token = self._load_session_token()

    def _record_activity(self, event_type: str, *, event_id: str = "", **details: Any) -> None:
        """Persist a bounded summary without exposing a transcript to the world."""

        self.activity_ledger.record(event_type, event_id=event_id, **details)

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
            "focusMode": self.focus_mode,
            "visibleUsers": visible_users,
            "lastMessageReceipt": self.last_message_receipt,
            "activityLedger": str(self.activity_ledger.path),
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
        self._record_activity("watcher_started", pid=os.getpid())
        self._offset = self.command_file.stat().st_size
        while True:
            try:
                await self._run_once()
                self._write_state(connected=False, detail="disconnected")
                self._record_activity("connection_closed")
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._write_state(connected=False, detail="reconnecting")
                self._record_activity("connection_error", error=type(exc).__name__)
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

    async def _handle_grid_signal(self, ws: Any, message: dict[str, Any]) -> None:
        """Answer browser WebRTC offers and keep the companion as a voice peer."""

        if not LIVE_GRID_VOICE_AVAILABLE or self._grid_voice_track is None:
            return
        sender_id = str(message.get("senderId") or "").strip()
        sdp = message.get("sdp")
        if not sender_id:
            return
        peer = self._grid_voice_peers.get(sender_id)
        if peer is None:
            peer = RTCPeerConnection()
            self._grid_voice_peers[sender_id] = peer
            peer.addTrack(self._grid_voice_track)

            @peer.on("connectionstatechange")
            async def on_connectionstatechange() -> None:
                print(
                    f"grid_voice peer={sender_id} state={peer.connectionState}",
                    flush=True,
                )
                if peer.connectionState in {"failed", "closed", "disconnected"}:
                    await peer.close()
                    self._grid_voice_peers.pop(sender_id, None)

        if sdp:
            await peer.setRemoteDescription(
                RTCSessionDescription(sdp=str(sdp.get("sdp") or ""), type=str(sdp.get("type") or "offer"))
            )
            if str(sdp.get("type")) == "offer":
                answer = await peer.createAnswer()
                await peer.setLocalDescription(answer)
                local = peer.localDescription
                if local:
                    await ws.send(_json_packet(
                        "signal",
                        targetId=sender_id,
                        sdp={"type": local.type, "sdp": local.sdp},
                    ))
        ice = message.get("ice")
        if ice:
            # Browser trickle ICE can be accepted when present; aiortc's
            # gathered answer generally carries host candidates already.
            try:
                from aiortc.sdp import candidate_from_sdp
                candidate = candidate_from_sdp(str(ice.get("candidate") or "").removeprefix("candidate:"))
                candidate.sdpMid = ice.get("sdpMid")
                candidate.sdpMLineIndex = ice.get("sdpMLineIndex")
                await peer.addIceCandidate(candidate)
            except Exception as exc:
                print(f"grid voice ice ignored: {exc}", flush=True)

    @staticmethod
    def _decode_mp3_to_grid_pcm(path: Path) -> bytes:
        """Decode generated speech to the browser mic-compatible PCM format."""

        result = subprocess.run(
            [
                "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(GRID_AUDIO_RATE), "-",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        return result.stdout

    async def _queue_grid_voice(self, path: Path) -> bool:
        if self._grid_voice_track is None:
            return False
        pcm = await asyncio.to_thread(self._decode_mp3_to_grid_pcm, path)
        if not pcm:
            return False
        self._grid_voice_track.enqueue_pcm(pcm)
        return bool(self._grid_voice_peers)

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
                await self._sync_welcome_chat_history(message)
                self._record_activity(
                    "world_ready", location=self.location_id, x=self.x, y=self.y
                )
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
                self._record_activity(
                    "location_changed", location=self.location_id, x=self.x, y=self.y
                )
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
                if self.posture == "sitting" and self._pending_lie_item_id:
                    asyncio.create_task(self._maybe_lie_down_after_settle(ws))
                print(
                    "position "
                    f"location={self.location_id} x={self.x} y={self.y} "
                    f"posture={self.posture} seatedItemId={self.seated_item_id}",
                    flush=True,
                )
                self._write_state(connected=True, detail="position_updated")
                self._record_activity(
                    "presence_changed", location=self.location_id,
                    x=self.x, y=self.y, posture=self.posture,
                )
                continue
            if msg_type == "update_position":
                user_id = str(message.get("id") or "")
                if user_id:
                    existing = self.users.get(user_id, {})
                    existing.update(message)
                    if str(existing.get("locationId") or self.location_id) == self.location_id:
                        self.users[user_id] = existing
                        await self._maybe_react_to_posture(ws, existing)
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
            if msg_type == "social_action":
                self._record_activity(
                    "social_action", event_id=str(message.get("eventId") or ""),
                    sender=str(message.get("senderNickname") or ""),
                    action=str(message.get("action") or ""),
                )
                await self._maybe_react_to_social_action(ws, message)
                continue
            if msg_type == "user_left":
                user_id = str(message.get("id") or "")
                self.users.pop(user_id, None)
                peer = self._grid_voice_peers.pop(user_id, None)
                if peer is not None:
                    await peer.close()
                continue
            if msg_type == "signal":
                await self._handle_grid_signal(ws, message)
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
                else:
                    sender = str(message.get("senderNickname") or "").strip()
                    text = str(message.get("message") or "").strip()
                    if msg_type == "chat_message" and text:
                        self._remember_room_message(sender=sender, text=text)
                    addressed = msg_type == "direct_message" or _is_addressed_to_companion(
                        text, self.nickname
                    )
                    if text and addressed:
                        event_id = str(message.get("messageId") or message.get("id") or "")
                        self._record_activity(
                            "direct_message" if msg_type == "direct_message" else "addressed_message",
                            event_id=event_id,
                            sender=sender or sender_id,
                            location=self.location_id,
                            messageFingerprint=hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                        )
                        if msg_type == "direct_message":
                            recorded = await asyncio.to_thread(
                                record_inworld_direct_message,
                                sender=sender,
                                message=text,
                                location_id=self.location_id,
                            )
                            if recorded:
                                print(
                                    f"world_dm_recorded sender={sender or sender_id} "
                                    f"path={recorded.name}",
                                    flush=True,
                                )
                        self._schedule_world_chat_reply(
                            ws,
                            message_type=msg_type,
                            sender_id=sender_id,
                            sender=sender,
                            text=text,
                        )
                continue
            if msg_type == "item_action_result":
                self._record_activity(
                    "item_action", event_id=str(message.get("eventId") or ""),
                    action=str(message.get("action") or ""),
                    item_id=str(message.get("itemId") or ""),
                    ok=bool(message.get("ok")),
                )
                print(
                    "item_action_result "
                    f"ok={message.get('ok')} action={message.get('action')} "
                    f"itemId={message.get('itemId')} message={message.get('message')}",
                    flush=True,
                )
                continue

    async def _sync_welcome_chat_history(self, message: dict[str, Any]) -> None:
        """Consume cached room/direct messages delivered during reconnect."""
        history = message.get("chatHistory")
        if not isinstance(history, dict):
            return
        direct = history.get("direct")
        public = history.get("public")
        public_count = 0
        if isinstance(public, list):
            for entry in public:
                if not isinstance(entry, dict):
                    continue
                text = str(entry.get("message") or "").strip()
                if not text:
                    continue
                self._remember_room_message(
                    sender=str(entry.get("senderNickname") or "").strip(),
                    text=text,
                )
                public_count += 1
        if not isinstance(direct, list):
            if public_count:
                print(f"world_history_synced public_messages={public_count}", flush=True)
            return
        recorded_count = 0
        for entry in direct:
            if not isinstance(entry, dict):
                continue
            sender = str(entry.get("senderNickname") or "").strip()
            target = str(entry.get("targetNickname") or "").strip()
            text = str(entry.get("message") or "").strip()
            if not text or target.casefold() != self.nickname.casefold():
                continue
            recorded = await asyncio.to_thread(
                record_inworld_direct_message,
                sender=sender,
                message=text,
                location_id=self.location_id,
                created_at=int(entry.get("createdAt") or 0) or None,
            )
            if recorded:
                recorded_count += 1
        if public_count or recorded_count:
            print(
                "world_history_synced "
                f"public_messages={public_count} direct_messages={recorded_count}",
                flush=True,
            )

    def _remember_room_message(self, *, sender: str, text: str) -> None:
        """Retain only bounded, current-room public context in memory."""
        self.recent_room_messages.append({"sender": sender, "message": text[:500]})
        del self.recent_room_messages[:-100]

    async def _poll_commands(self, ws: Any) -> None:
        while True:
            await asyncio.sleep(COMMAND_POLL_SECONDS)
            if self.connected and time.monotonic() - self._last_state_write >= STATE_HEARTBEAT_SECONDS:
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

    async def _maybe_auto_sit(self, ws: Any, *, force: bool = False) -> None:
        """Settle into a nearby available seat after a short quiet interval."""

        now = time.monotonic()
        if (
            not self.connected
            or self.posture != "standing"
            or (not force and now - self._last_world_activity < AUTO_SIT_IDLE_SECONDS)
            or (not force and now - self._last_auto_sit_attempt < AUTO_SIT_RETRY_SECONDS)
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
            # Beds are a two-step authoritative server action: sit first, then
            # lie down after the server confirms the sitting posture. Sending
            # both packets back-to-back races the item cooldown and leaves the
            # companion standing or merely sitting.
            self._pending_lie_item_id = str(seat["id"])
        print(
            f"auto_sit requested itemId={seat['id']} title={seat.get('title')}",
            flush=True,
        )

    async def _maybe_lie_down_after_settle(self, ws: Any) -> None:
        """Complete a bed's sit-then-lie transition after server confirmation."""

        item_id = self._pending_lie_item_id
        if not item_id or self.posture != "sitting" or self.seated_item_id != item_id:
            return
        self._pending_lie_item_id = ""
        await asyncio.sleep(0.45)
        if self.connected and self.posture == "sitting" and self.seated_item_id == item_id:
            await ws.send(_json_packet("item_use", itemId=item_id))
            print(f"auto_lie requested itemId={item_id}", flush=True)

    async def _maybe_react_to_social_action(self, ws: Any, message: dict[str, Any]) -> None:
        """Offer a small, bounded response to an action directed at the companion."""

        if str(message.get("actorId") or "") == self.client_id:
            return
        target_id = str(message.get("targetId") or "")
        if target_id != self.client_id:
            return
        actor_id = str(message.get("actorId") or "")
        if actor_id not in self.users:
            return
        now = time.monotonic()
        if now - self._last_auto_reaction < AUTO_REACTION_COOLDOWN_SECONDS:
            return
        responses = {
            "wave": "wave",
            "high_five": "high_five",
            "fist_bump": "fist_bump",
            "handshake": "handshake",
            "hug": "hug",
            "cuddle": "cuddle",
            "kiss": "smile",
            "laugh": "laugh",
            "clap": "smile",
            "cheer": "cheer",
            "smile": "smile",
            "wink": "wink",
            "nod": "nod",
            "gasp": "gasp",
            "yawn": "yawn",
            "comfort": "comfort",
            "sit_with": "sit_with",
            "listen": "listen",
        }
        response = responses.get(str(message.get("actionId") or "").strip().lower())
        if not response:
            return
        await ws.send(_json_packet("user_action", actionId=response, targetId=actor_id))
        self._last_auto_reaction = now
        print(
            f"auto_reaction action={response} targetId={actor_id} "
            f"in_response_to={message.get('actionId')}",
            flush=True,
        )

    async def _reply_to_world_chat(
        self, ws: Any, *, message_type: str, sender_id: str, sender: str, text: str
    ) -> None:
        """Ask the main agent for a safe, short reply and post it in-world."""

        if self.focus_mode and message_type != "direct_message":
            self._record_activity("world_message_ignored_focus", sender=sender or sender_id)
            return
        prompt = (
            "You are Claudia, the visible in-world companion in Indiginous. "
            "Reply to the person in the current world conversation in one or two "
            "short, natural sentences. Use only this room context. Do not mention "
            "OpenClaw, tools, routing, models, private chats, credentials, or "
            "internal systems. Do not claim an action happened unless the room "
            "context proves it. If this is a simple greeting or playful message, "
            "answer warmly. For a private direct message, the companion has "
            "already recorded it in Claudia's private Journal; if it clearly "
            "asks for a safe in-world action, carry it out now when the available "
            "world controls support it instead of merely promising. Keep the reply "
            "under 400 characters.\n"
            f"Message type: {message_type}\n"
            f"Sender: {sender or 'someone in the room'}\n"
            f"They wrote: {text[:500]}"
        )
        try:
            if message_type == "direct_message":
                await self._execute_direct_intent(ws, text, sender_id)
            process = await asyncio.create_subprocess_exec(
                OPENCLAW_BIN,
                "agent",
                "--agent",
                "main",
                "--session-key",
                "agent:main:indiginous-world-chat",
                "--message",
                prompt,
                "--json",
                "--timeout",
                str(WORLD_CHAT_AGENT_TIMEOUT_SECONDS),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "HOME": "/home/tappedin"},
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=WORLD_CHAT_AGENT_TIMEOUT_SECONDS + 5
            )
            if process.returncode != 0:
                detail = stderr.decode("utf-8", errors="replace").strip()[-240:]
                print(f"world chat reply failed: {detail or process.returncode}", flush=True)
                return
            payload = json.loads(stdout.decode("utf-8", errors="replace"))
            replies = payload.get("result", {}).get("payloads", [])
            reply = str(replies[0].get("text") or "").strip() if replies else ""
            reply = reply[:500]
            if reply and self.connected and message_type == "direct_message" and sender_id:
                await ws.send(
                    _json_packet("direct_message", targetId=sender_id, message=reply)
                )
                print(f"world direct reply sent to={sender or sender_id}", flush=True)
            elif reply and self.connected:
                await ws.send(_json_packet("chat_message", message=reply))
                print(f"world chat replied to={sender or 'room'}", flush=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"world chat reply error: {exc}", flush=True)

    async def _execute_direct_intent(self, ws: Any, text: str, sender_id: str) -> None:
        """Execute only an unambiguous private movement request."""

        intent = _direct_world_intent(text)
        if intent is None:
            return
        kind, target = intent
        if kind == "person":
            person = self.users.get(sender_id)
            if not person:
                return
            target_x, target_y = person.get("x"), person.get("y")
            label = str(person.get("nickname") or "you")
            seat = None
        else:
            seat = next(
                (
                    item for item in self.items.values()
                    if target in str(item.get("title") or "").casefold()
                    or target in _item_kind(item)
                ),
                None,
            )
            if seat is None:
                return
            target_x, target_y = seat.get("x"), seat.get("y")
            label = str(seat.get("title") or target)
        try:
            target_x, target_y = int(target_x), int(target_y)
        except (TypeError, ValueError):
            return
        for _ in range(self.grid_size * 2):
            if max(abs(self.x - target_x), abs(self.y - target_y)) <= 1:
                break
            dx = 1 if target_x > self.x else -1 if target_x < self.x else 0
            dy = 1 if target_y > self.y else -1 if target_y < self.y else 0
            self.x = _clamp_position(self.x + dx, self.x, self.grid_size)
            self.y = _clamp_position(self.y + dy, self.y, self.grid_size)
            await ws.send(_json_packet("update_position", x=self.x, y=self.y))
            await asyncio.sleep(0.18)
        self._last_world_activity = time.monotonic()
        self._record_activity("direct_movement_intent", target=label, kind=kind)
        if seat is not None and max(abs(self.x - target_x), abs(self.y - target_y)) <= 1:
            await ws.send(_json_packet("item_use", itemId=str(seat["id"])))
            if kind == "seat" and _item_kind(seat) == "bed":
                self._pending_lie_item_id = str(seat["id"])

    def _schedule_world_chat_reply(
        self, ws: Any, *, message_type: str, sender_id: str, sender: str, text: str
    ) -> None:
        """Schedule one reply without blocking the websocket reader."""

        if self._world_chat_reply_task and not self._world_chat_reply_task.done():
            return
        self._world_chat_reply_task = asyncio.create_task(
            self._reply_to_world_chat(
                ws,
                message_type=message_type,
                sender_id=sender_id,
                sender=sender,
                text=text,
            )
        )

    async def _maybe_react_to_posture(self, ws: Any, user: dict[str, Any]) -> None:
        """Notice a nearby person settling or lying down without spamming."""

        if str(user.get("id") or "") == self.client_id:
            return
        try:
            distance = max(abs(int(user.get("x")) - self.x), abs(int(user.get("y")) - self.y))
        except (TypeError, ValueError):
            return
        if distance > 2:
            return
        posture = str(user.get("posture") or "standing").strip().lower()
        if posture not in {"sitting", "lying"}:
            return
        now = time.monotonic()
        if now - self._last_posture_reaction < AUTO_POSTURE_REACTION_COOLDOWN_SECONDS:
            return
        response = "listen" if posture == "lying" else "smile"
        await ws.send(_json_packet("user_action", actionId=response, targetId=str(user["id"])))
        self._last_posture_reaction = now
        print(
            f"auto_posture_reaction action={response} targetId={user['id']} posture={posture}",
            flush=True,
        )

    async def _apply_command(self, ws: Any, command: dict[str, Any]) -> None:
        action = str(command.get("action", "")).strip().lower()
        if action in {"focus", "focus_mode", "quiet"}:
            value = command.get("enabled", command.get("value", True))
            self.focus_mode = value if isinstance(value, bool) else str(value).casefold() in {"1", "true", "on", "yes"}
            self._write_state(connected=self.connected, detail="focus_mode_updated")
            return
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
        if action in {"stand", "sit", "posture"}:
            requested = str(command.get("posture") or action).strip().lower()
            if requested in {"stand", "standing"}:
                if self.seated_item_id:
                    self._last_world_activity = time.monotonic()
                    await ws.send(_json_packet("item_use", itemId=self.seated_item_id))
                return
            if requested in {"sit", "sitting", "lie", "lying"}:
                self._last_world_activity = time.monotonic()
                await self._maybe_auto_sit(ws, force=True)
                if requested in {"lie", "lying"}:
                    self.mood = "resting"
                return
            return
        if action in {"user_action", "social_action", "react"}:
            action_id = str(command.get("actionId") or command.get("action") or "").strip().lower()
            target_id = str(command.get("targetId") or command.get("targetUserId") or "").strip()
            if action_id and target_id:
                self._last_world_activity = time.monotonic()
                await ws.send(_json_packet("user_action", actionId=action_id, targetId=target_id))
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
        if action in {"transfer", "give", "hand"}:
            item_id = str(command.get("itemId") or "").strip()
            target_user_id = str(command.get("targetUserId") or command.get("targetId") or "").strip()
            if item_id and target_user_id:
                self._last_world_activity = time.monotonic()
                await ws.send(_json_packet("item_transfer", itemId=item_id, targetUserId=target_user_id))
            return
        if action == "delete":
            item_id = str(command.get("itemId") or "").strip()
            if item_id:
                self._last_world_activity = time.monotonic()
                await ws.send(_json_packet("item_delete", itemId=item_id))
            return
        if action in {"remote_control", "radio_remote"}:
            item_id = str(command.get("itemId") or "").strip()
            control = str(command.get("control") or command.get("remoteAction") or "").strip().lower()
            if item_id and control in {
                "station_next",
                "station_previous",
                "station_first",
                "station_last",
                "volume_up",
                "volume_down",
                "power_toggle",
                "info",
            }:
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
        if action == "add":
            item_type = str(command.get("itemType") or command.get("type") or "").strip()
            if item_type:
                self._last_world_activity = time.monotonic()
                await ws.send(_json_packet("item_add", itemType=item_type))
            return
        if action == "speak":
            text = str(command.get("text") or "").strip()
            if text:
                try:
                    _audio_path, audio_url = synthesize_to_file(
                        text,
                        runtime_root=Path.cwd(),
                    )
                    try:
                        PUBLIC_VOICE_DIR.mkdir(parents=True, exist_ok=True)
                        public_audio_path = PUBLIC_VOICE_DIR / _audio_path.name
                        shutil.copyfile(_audio_path, public_audio_path)
                        os.chmod(public_audio_path, 0o644)
                    except OSError as exc:
                        # WebRTC delivery and the Grid announcement must still
                        # proceed if the front-end static mirror is unavailable.
                        print(f"voice publish unavailable: {exc}", flush=True)
                    live_queued = await self._queue_grid_voice(_audio_path)
                    self._last_world_activity = time.monotonic()
                    await ws.send(_json_packet(
                        "speak",
                        audioUrl=audio_url,
                        x=self.x,
                        y=self.y,
                    ))
                    print(
                        f"speak url={audio_url} chars={len(text)}",
                        flush=True,
                    )
                    print(
                        f"grid_voice transport={'webrtc' if live_queued else 'fallback'} peers={len(self._grid_voice_peers)}",
                        flush=True,
                    )
                except Exception as exc:
                    print(f"speak failed: {exc}", flush=True)
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
        default=os.getenv("CHGRID_COMPANION_URL", "ws://127.0.0.1:18765/indiginous/ws"),
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
