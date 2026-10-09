from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pulse.domain.ports import NullPromptPort, PromptPort

SOCKET_ENV = "PULSE_ASK_SOCKET"
DEFAULT_SOCKET_TIMEOUT = 600.0


class AskQuestionBridgeServer:
    def __init__(
        self,
        *,
        socket_path: Path,
        prompt_handler: PromptPort | None = None,
        on_question: Callable[[], None] | None = None,
    ) -> None:
        self._socket_path = socket_path
        self._prompt_handler = prompt_handler or NullPromptPort()
        self._on_question = on_question
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    def start(self) -> None:
        if self._socket_path.exists():
            self._socket_path.unlink()
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(self._socket_path))
        self._server.listen(5)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def close(self) -> None:
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        if self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except OSError:
                pass

    def _serve(self) -> None:
        if self._server is None:
            return
        while True:
            try:
                connection, _ = self._server.accept()
            except OSError:
                return
            threading.Thread(
                target=self._handle_connection,
                args=(connection,),
                daemon=True,
            ).start()

    def _handle_connection(self, connection: socket.socket) -> None:
        try:
            with connection:
                chunks: list[bytes] = []
                while True:
                    data = connection.recv(65536)
                    if not data:
                        break
                    chunks.append(data)
                if not chunks:
                    return
                payload = json.loads(b"".join(chunks).decode("utf-8"))
                if self._on_question is not None:
                    self._on_question()
                result = self._prompt_handler.respond_to_ask_question(payload)
                connection.sendall(json.dumps(result).encode("utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return


def request_ask_question_via_socket(
    params: dict[str, Any],
    *,
    socket_path: str,
    timeout: float = DEFAULT_SOCKET_TIMEOUT,
) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(socket_path)
        client.sendall(json.dumps(params).encode("utf-8"))
        client.shutdown(socket.SHUT_WR)
        chunks: list[bytes] = []
        while True:
            data = client.recv(65536)
            if not data:
                break
            chunks.append(data)
    if not chunks:
        return {"outcome": {"outcome": "cancelled"}}
    return json.loads(b"".join(chunks).decode("utf-8"))
