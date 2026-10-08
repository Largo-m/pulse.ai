from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any

from pulse.acp.capabilities import PULSE_CLIENT_CAPABILITIES, PULSE_CLIENT_INFO
from pulse.acp.models import extract_model_labels


@dataclass
class AcpProbeResult:
    success: bool
    message: str
    response_text: str = ""
    available_models: list[str] = field(default_factory=list)
    error: str | None = None


class AcpClient:
    def __init__(
        self,
        command: list[str],
        *,
        cwd: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._command = command
        self._cwd = cwd
        self._timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._responses: dict[int, dict[str, Any]] = {}
        self._response_queue: Queue[int] = Queue()
        self._reader: threading.Thread | None = None
        self._next_id = 1
        self._session_updates: list[dict[str, Any]] = []

    def start(self) -> None:
        # argv list from the user's effective config, never from agent output.
        self._process = subprocess.Popen(  # noqa: S603
            self._command,
            cwd=self._cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def close(self) -> None:
        if self._process is None:
            return
        if self._process.stdin:
            try:
                self._process.stdin.close()
            except OSError:
                pass
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.terminate()
        self._process = None

    def _read_stdout(self) -> None:
        if self._process is None or self._process.stdout is None:
            return
        for line in self._process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "method" in message and "id" not in message:
                if message.get("method") == "session/update":
                    params = message.get("params", {})
                    self._session_updates.append(params)
                continue
            message_id = message.get("id")
            if isinstance(message_id, int):
                self._responses[message_id] = message
                self._response_queue.put(message_id)

    def _send(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("ACP process not started")
        self._process.stdin.write(json.dumps(payload) + "\n")
        self._process.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        try:
            response_id = self._response_queue.get(timeout=self._timeout_seconds)
        except Empty as error:
            raise TimeoutError(f"timed out waiting for a response to `{method}`") from error

        response = self._responses.pop(response_id, {})
        if "error" in response:
            failure = response["error"]
            raise RuntimeError(failure.get("message", "unknown ACP error"))
        return response.get("result", {})

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": PULSE_CLIENT_CAPABILITIES,
                "clientInfo": PULSE_CLIENT_INFO,
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return result

    def new_session(self, cwd: str) -> dict[str, Any]:
        return self._request("session/new", {"cwd": cwd, "mcpServers": []})

    def prompt(self, session_id: str, text: str) -> dict[str, Any]:
        return self._request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": text}],
            },
        )

    def collect_message_text(self) -> str:
        chunks: list[str] = []
        for params in self._session_updates:
            update = params.get("update", {})
            if update.get("sessionUpdate") != "agent_message_chunk":
                continue
            content = update.get("content", {})
            if content.get("type") == "text":
                chunks.append(str(content.get("text", "")))
        return "".join(chunks)


def fetch_acp_available_models(
    *,
    command: list[str] | None = None,
    cwd: str,
    timeout_seconds: float = 30.0,
) -> list[str]:
    acp_command = command or ["agent", "acp"]
    client = AcpClient(acp_command, cwd=cwd, timeout_seconds=timeout_seconds)
    try:
        client.start()
        client.initialize()
        session = client.new_session(cwd)
        return extract_model_labels(session)
    except (RuntimeError, TimeoutError, OSError):
        return []
    finally:
        client.close()


def _extract_models(session_result: dict[str, Any]) -> list[str]:
    return extract_model_labels(session_result)


def probe_acp_connection(
    *,
    command: list[str] | None = None,
    cwd: str,
    prompt_text: str = "Say hello",
    timeout_seconds: float = 60.0,
    on_status: Callable[[str], None] | None = None,
) -> AcpProbeResult:
    acp_command = command or ["agent", "acp"]
    client = AcpClient(acp_command, cwd=cwd, timeout_seconds=timeout_seconds)

    def status(message: str) -> None:
        if on_status:
            on_status(message)

    try:
        status("Starting the ACP agent…")
        client.start()
        status("Handshake initialize…")
        client.initialize()
        status("Creating a session…")
        session = client.new_session(cwd)
        session_id = session.get("sessionId")
        if not session_id:
            return AcpProbeResult(
                success=False,
                message="ACP session returned no sessionId",
                error="missing_session_id",
            )

        models = _extract_models(session)
        status(f'Sending the test prompt: "{prompt_text}"…')
        client.prompt(str(session_id), prompt_text)
        response_text = client.collect_message_text().strip()

        if not response_text:
            return AcpProbeResult(
                success=False,
                message="ACP replied with no message content",
                available_models=models,
                error="empty_response",
            )

        return AcpProbeResult(
            success=True,
            message="ACP connection verified",
            response_text=response_text,
            available_models=models,
        )
    except (RuntimeError, TimeoutError, OSError) as error:
        return AcpProbeResult(
            success=False,
            message="ACP test failed",
            error=str(error),
        )
    finally:
        client.close()
