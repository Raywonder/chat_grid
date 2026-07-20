"""System-browser authentication handoff for the desktop client."""

from __future__ import annotations

from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
import hmac
import re
import secrets
import threading
from urllib.parse import parse_qs, urlencode, urlsplit


CALLBACK_PATH = "/chatgrid-client-auth/callback"
ASSERTION_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


class BrowserAuthFlow:
    """Receive one short-lived BlindSoftware assertion on a loopback callback."""

    def __init__(self, server_origin: str, grid_url: str, timeout_seconds: float = 180.0) -> None:
        origin = urlsplit(server_origin)
        if origin.scheme != "https" or not origin.hostname or origin.username or origin.password:
            raise ValueError("Browser authentication requires a valid HTTPS server origin.")
        self.server_origin = f"https://{origin.netloc}"
        self.grid_url = grid_url
        self.timeout_seconds = timeout_seconds
        self.state = secrets.token_urlsafe(32)
        self.assertion: str | None = None
        self.error: str | None = None
        self._server = HTTPServer(("127.0.0.1", 0), self._handler_type())
        port = int(self._server.server_address[1])
        self.callback_url = f"http://127.0.0.1:{port}{CALLBACK_PATH}"
        self.authorization_url = self.server_origin + "/?" + urlencode(
            {
                "route": "chatgrid_client_auth_start",
                "callback": self.callback_url,
                "state": self.state,
            }
        )

    def _handler_type(self) -> type[BaseHTTPRequestHandler]:
        flow = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                parsed = urlsplit(self.path)
                values = parse_qs(parsed.query)
                supplied_state = values.get("state", [""])[0]
                assertion = values.get("assertion", [""])[0]
                valid = (
                    parsed.path == CALLBACK_PATH
                    and hmac.compare_digest(supplied_state, flow.state)
                    and 1 <= len(assertion) <= 8192
                    and ASSERTION_RE.fullmatch(assertion) is not None
                )
                if valid:
                    flow.assertion = assertion
                    self._reply(200, "Endiginous sign-in complete", "Return to Endiginous. This browser tab can be closed.")
                else:
                    flow.error = "The browser returned an invalid or expired Endiginous sign-in response."
                    self._reply(400, "Endiginous sign-in failed", flow.error)

            def _reply(self, status: int, title: str, message: str) -> None:
                body = (
                    "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
                    f"<title>{title}</title><main><h1>{title}</h1><p>{message}</p></main></html>"
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                """Never place assertions or callback query strings in logs."""

        return CallbackHandler

    def start(
        self,
        on_success: Callable[[str, str], None],
        on_error: Callable[[str], None],
    ) -> threading.Thread:
        """Wait once in the background and report the result through callbacks."""

        def worker() -> None:
            try:
                self._server.timeout = self.timeout_seconds
                self._server.handle_request()
                if self.assertion:
                    on_success(self.grid_url, self.assertion)
                else:
                    on_error(self.error or "Browser sign-in timed out. Try again from Endiginous.")
            finally:
                self._server.server_close()

        thread = threading.Thread(target=worker, name="chat-grid-browser-auth", daemon=True)
        thread.start()
        return thread

    def close(self) -> None:
        """Close the loopback listener when browser launch cannot start."""
        self._server.server_close()
