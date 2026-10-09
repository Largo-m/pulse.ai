from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from pulse.domain.ports import JsonObject, NullPromptPort, PromptPort
from pulse.mcp.ask_protocol import dispatch_message

ENDPOINT_PATH = "/mcp"
FORBIDDEN = 403
LOOPBACK = "127.0.0.1"
LOCAL_HOSTNAMES = frozenset({LOOPBACK, "localhost"})


class AskQuestionHttpServer:
    def __init__(
        self,
        *,
        prompt_handler: PromptPort | None = None,
        on_question: Callable[[], None] | None = None,
    ) -> None:
        self._prompt_handler = prompt_handler or NullPromptPort()
        self._on_question = on_question
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._session_token = uuid.uuid4().hex

    @property
    def url(self) -> str:
        if self._httpd is None:
            raise RuntimeError("MCP HTTP server not started")
        host, port = self._httpd.socket.getsockname()[:2]
        return f"http://{host}:{port}{ENDPOINT_PATH}"

    def start(self) -> None:
        self._httpd = ThreadingHTTPServer((LOOPBACK, 0), self._build_handler())
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except OSError:
                pass
            self._httpd = None
        self._thread = None

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                if _sent_by_a_web_page(self):
                    bridge._send_empty(self, FORBIDDEN)
                    return
                bridge._handle_post(self)

            def do_GET(self) -> None:
                self.send_response(405)
                self.send_header("Allow", "POST, DELETE")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_DELETE(self) -> None:
                if _sent_by_a_web_page(self):
                    bridge._send_empty(self, FORBIDDEN)
                    return
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        return Handler

    def _handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        length = int(handler.headers.get("Content-Length", 0) or 0)
        raw = handler.rfile.read(length) if length else b""
        try:
            message = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(
                handler,
                400,
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            )
            return

        if isinstance(message, list):
            responses = [
                response
                for item in message
                if isinstance(item, dict)
                for response in (self._dispatch(item),)
                if response is not None
            ]
            if responses:
                self._send_json(handler, 200, responses)
            else:
                self._send_empty(handler, 202)
            return

        if not isinstance(message, dict):
            self._send_empty(handler, 202)
            return

        is_initialize = message.get("method") == "initialize"
        response = self._dispatch(message)
        if response is None:
            self._send_empty(handler, 202)
            return

        extra = {"Mcp-Session-Id": self._session_token} if is_initialize else None
        self._send_json(handler, 200, response, extra_headers=extra)

    def _dispatch(self, message: dict[str, Any]) -> dict[str, Any] | None:
        return dispatch_message(
            message,
            prompt_handler=self._prompt_handler,
            on_question=self._on_question,
        )

    def _send_json(
        self,
        handler: BaseHTTPRequestHandler,
        status: int,
        payload: JsonObject | list[JsonObject],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for name, value in extra_headers.items():
                handler.send_header(name, value)
        handler.end_headers()
        handler.wfile.write(body)

    def _send_empty(self, handler: BaseHTTPRequestHandler, status: int) -> None:
        handler.send_response(status)
        handler.send_header("Content-Length", "0")
        handler.end_headers()


def _sent_by_a_web_page(handler: BaseHTTPRequestHandler) -> bool:
    """The MCP spec requires validating `Origin` on a local HTTP transport.

    Agent CLIs send neither `Origin` nor a foreign `Host`; a browser page sends
    `Origin`, and a DNS-rebinding page sends its own hostname as `Host`.
    """
    if handler.headers.get("Origin") is not None:
        return True
    hostname = (handler.headers.get("Host") or "").rsplit(":", 1)[0]
    return hostname not in LOCAL_HOSTNAMES
