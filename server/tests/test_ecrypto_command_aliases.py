from pathlib import Path

import pytest

from app.client import ClientConnection
from app.server import SignalingServer


@pytest.mark.asyncio
async def test_ecrypto_command_aliases_are_accepted(tmp_path: Path) -> None:
    server = SignalingServer(
        "127.0.0.1", 8765, None, None, auth_db_path=tmp_path / "auth.db"
    )
    try:
        session = server.auth_service.register("aliasuser", "password123")
        client = ClientConnection(websocket=object(), id="u1", nickname="Alias")
        client.authenticated = True
        client.user_id = session.user.id
        client.username = session.user.username
        calls: list[str] = []

        async def capture(_client: ClientConnection, command_line: str) -> None:
            calls.append(command_line)

        server._send_ecrypto_command_result = capture  # type: ignore[method-assign]
        for alias in ("ecrypto", "ecripto", "ecr", "ecr*"):
            assert await server._handle_chat_command(client, f"/{alias} help") is True

        assert calls == ["help"] * 4
    finally:
        server.auth_service.close()
