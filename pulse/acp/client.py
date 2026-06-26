from __future__ import annotations

import json
import subprocess
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any

from pulse.acp.capabilities import PULSE_CLIENT_CAPABILITIES, PULSE_CLIENT_INFO
from pulse.acp.logger import AcpLogger


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
        timeout_seconds: float = 60.0,
        run_id: str | None = None,
    ) -> None:
        self._command = command
        self._timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._responses: dict[int, dict[str, Any]] = {}
        self._response_queue: Queue[int] = Queue()
        self._reader: threading.Thread | None = None
        self._next_id = 1
        self._session_updates: list[dict[str, Any]] = []
        self._logger = AcpLogger(run_id or str(uuid.uuid4()))

    def start(self) -> None:
        self._logger.log_event("process_start", {"command": self._command})
        self._process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def close(self) -> None:
        self._logger.log_event("process_close")
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
            self._logger.log_received(message)
            if "method" in message and "id" not in message:
                if message.get("method") == "session/update":
                    params = message.get("params", {})
                    self._logger.log_update(params)
                    self._session_updates.append(params)
                continue
            message_id = message.get("id")
            if isinstance(message_id, int):
                self._responses[message_id] = message
                self._response_queue.put(message_id)

    def _send(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Processo ACP não iniciado")
        self._logger.log_sent(payload)
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
            raise TimeoutError(f"Timeout aguardando resposta de `{method}`") from error

        response = self._responses.pop(response_id, {})
        if "error" in response:
            error = response["error"]
            raise RuntimeError(error.get("message", "Erro ACP desconhecido"))
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
        result = self._request("session/new", {"cwd": cwd, "mcpServers": []})
        session_id = result.get("sessionId")
        if session_id:
            self._logger.set_session_id(str(session_id))
        return result

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


def _extract_models(session_result: dict[str, Any]) -> list[str]:
    models = session_result.get("models", {})
    available = models.get("availableModels", [])
    result: list[str] = []
    for item in available:
        if not isinstance(item, dict):
            continue
        model_id = item.get("modelId")
        name = item.get("name", model_id)
        if model_id:
            result.append(str(name or model_id))
    return result


def probe_acp_connection(
    *,
    command: list[str] | None = None,
    cwd: str,
    prompt_text: str = "Say hello",
    timeout_seconds: float = 60.0,
    on_status: Callable[[str], None] | None = None,
) -> AcpProbeResult:
    acp_command = command or ["agent", "acp"]
    client = AcpClient(acp_command, timeout_seconds=timeout_seconds)

    def status(message: str) -> None:
        if on_status:
            on_status(message)

    try:
        status("Iniciando agente ACP…")
        client.start()
        status("Handshake initialize…")
        client.initialize()
        status("Criando sessão…")
        session = client.new_session(cwd)
        session_id = session.get("sessionId")
        if not session_id:
            return AcpProbeResult(
                success=False,
                message="Sessão ACP não retornou sessionId",
                error="missing_session_id",
            )

        models = _extract_models(session)
        status(f'Enviando prompt de teste: "{prompt_text}"…')
        client.prompt(str(session_id), prompt_text)
        response_text = client.collect_message_text().strip()

        if not response_text:
            return AcpProbeResult(
                success=False,
                message="ACP respondeu sem conteúdo de mensagem",
                available_models=models,
                error="empty_response",
            )

        return AcpProbeResult(
            success=True,
            message="Conexão ACP validada",
            response_text=response_text,
            available_models=models,
        )
    except (RuntimeError, TimeoutError, OSError) as error:
        return AcpProbeResult(
            success=False,
            message="Falha no teste ACP",
            error=str(error),
        )
    finally:
        client.close()
