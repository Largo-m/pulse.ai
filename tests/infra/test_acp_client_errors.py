"""`AcpClient`, the one-shot client behind `pulse doctor` and model discovery.

It talks to an agent CLI the user may not have installed, logged in, or that may
print noise; every failure must come back as a result (an empty model list, a
failed probe with its reason), never as an exception in the doctor.
"""

from __future__ import annotations

import json
import subprocess
from io import StringIO
from typing import Any

import pytest

from pulse.acp import client as acp_client
from pulse.acp.client import AcpClient, fetch_acp_available_models, probe_acp_connection

MODELS = {"availableModels": [{"modelId": "m1", "name": "composer-2.5"}]}


class _Pipe(StringIO):
    def __init__(self, *, fail_on_close: bool = False) -> None:
        super().__init__()
        self.text = ""
        self._fail_on_close = fail_on_close

    def flush(self) -> None:
        self.text = self.getvalue()

    def close(self) -> None:
        self.text = self.getvalue()
        if self._fail_on_close:
            self._fail_on_close = False
            raise OSError("broken pipe")
        super().close()

    def methods(self) -> list[str]:
        return [json.loads(line).get("method", "") for line in self.text.splitlines()]


class FakeProcess:
    """An agent CLI whose whole stdout is known up front."""

    def __init__(
        self,
        lines: list[dict[str, Any] | str] | None = None,
        *,
        hangs: bool = False,
        fail_stdin_close: bool = False,
    ) -> None:
        text = "".join(
            (line if isinstance(line, str) else json.dumps(line)) + "\n" for line in lines or []
        )
        self.stdin = _Pipe(fail_on_close=fail_stdin_close)
        self.stdout: StringIO | None = StringIO(text)
        self.stderr = StringIO()
        self.terminated = False
        self._hangs = hangs

    def wait(self, timeout: float | None = None) -> int:
        if self._hangs:
            raise subprocess.TimeoutExpired("agent", timeout or 0)
        return 0

    def terminate(self) -> None:
        self.terminated = True


def _reply(request_id: int, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _chunk(text: str, kind: str = "text") -> dict[str, Any]:
    update = {"sessionUpdate": "agent_message_chunk", "content": {"type": kind, "text": text}}
    return {"jsonrpc": "2.0", "method": "session/update", "params": {"update": update}}


def _spawn(monkeypatch: pytest.MonkeyPatch, process: FakeProcess) -> list[list[str]]:
    commands: list[list[str]] = []

    def popen(command: list[str], **_kwargs: object) -> FakeProcess:
        commands.append(command)
        return process

    monkeypatch.setattr(acp_client.subprocess, "Popen", popen)
    return commands


def _missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    def popen(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("agent")

    monkeypatch.setattr(acp_client.subprocess, "Popen", popen)


def _started(process: FakeProcess) -> AcpClient:
    """A client wired to `process` with its read loop already drained, on this thread."""
    client = AcpClient(["agent", "acp"], timeout_seconds=5)
    client._process = process  # type: ignore[assignment]  # duck-typed Popen
    client._read_stdout()
    return client


# --- AcpClient -----------------------------------------------------------------


def test_noise_and_foreign_notifications_are_ignored_by_the_read_loop():
    """Only `session/update` text is the agent's answer; banners and other methods are not."""
    process = FakeProcess(
        [
            "",
            "agent v1.0 starting",
            {"jsonrpc": "2.0", "method": "$/progress", "params": {"pct": 10}},
            {"jsonrpc": "2.0", "id": "abc", "result": {}},
            _chunk("Hel"),
            _chunk("<img>", kind="image"),
            {"jsonrpc": "2.0", "method": "session/update", "params": {"update": {"x": 1}}},
            _chunk("lo"),
            _reply(1, {"protocolVersion": 1}),
        ]
    )

    client = _started(process)

    assert client.collect_message_text() == "Hello"
    assert client._responses == {1: _reply(1, {"protocolVersion": 1})}


def test_the_read_loop_without_a_process_does_nothing():
    client = AcpClient(["agent", "acp"])

    client._read_stdout()

    assert client.collect_message_text() == ""


def test_an_error_reply_raises_the_agent_message():
    process = FakeProcess([{"jsonrpc": "2.0", "id": 1, "error": {"message": "not logged in"}}])
    client = _started(process)

    with pytest.raises(RuntimeError, match="^not logged in$"):
        client.initialize()


def test_an_error_reply_without_a_message_still_raises():
    client = _started(FakeProcess([{"jsonrpc": "2.0", "id": 1, "error": {}}]))

    with pytest.raises(RuntimeError, match="unknown ACP error"):
        client.new_session("/repo")


def test_a_silent_agent_times_out_naming_the_request():
    client = AcpClient(["agent", "acp"], timeout_seconds=0.0)
    client._process = FakeProcess()  # type: ignore[assignment]  # duck-typed Popen

    with pytest.raises(TimeoutError, match="session/new"):
        client.new_session("/repo")


def test_sending_before_start_is_an_error():
    with pytest.raises(RuntimeError, match="not started"):
        AcpClient(["agent", "acp"]).prompt("sess-1", "hi")


def test_close_terminates_an_agent_that_does_not_exit_and_survives_a_broken_pipe():
    client = AcpClient(["agent", "acp"])
    process = FakeProcess(hangs=True, fail_stdin_close=True)
    client._process = process  # type: ignore[assignment]  # duck-typed Popen

    client.close()

    assert process.terminated is True
    assert client._process is None


def test_close_before_start_is_a_no_op():
    client = AcpClient(["agent", "acp"])

    client.close()

    assert client._process is None


# --- fetch_acp_available_models ---------------------------------------------------


def test_available_models_come_from_the_new_session(monkeypatch):
    process = FakeProcess(
        [_reply(1, {"protocolVersion": 1}), _reply(2, {"sessionId": "s", "models": MODELS})]
    )
    commands = _spawn(monkeypatch, process)

    models = fetch_acp_available_models(cwd="/repo", timeout_seconds=5)

    assert models == ["composer-2.5"]
    assert commands == [["agent", "acp"]]
    assert process.stdin.methods() == ["initialize", "notifications/initialized", "session/new"]


def test_a_missing_agent_cli_yields_no_models(monkeypatch):
    """The settings screen shows the default list instead of crashing."""
    _missing_binary(monkeypatch)

    assert fetch_acp_available_models(command=["claude-acp"], cwd="/repo") == []


def test_a_failing_handshake_yields_no_models(monkeypatch):
    process = FakeProcess([{"jsonrpc": "2.0", "id": 1, "error": {"message": "auth required"}}])
    _spawn(monkeypatch, process)

    assert fetch_acp_available_models(cwd="/repo", timeout_seconds=5) == []
    assert process.stdin.text.count("\n") == 1, "nothing is sent after the failed handshake"


# --- probe_acp_connection ----------------------------------------------------------


def test_the_probe_reports_each_stage_to_the_caller(monkeypatch):
    process = FakeProcess(
        [
            _reply(1, {"protocolVersion": 1}),
            _reply(2, {"sessionId": "sess-1", "models": MODELS}),
            _chunk("  Olá  "),
            _reply(3, {"stopReason": "end_turn"}),
        ]
    )
    commands = _spawn(monkeypatch, process)
    statuses: list[str] = []

    result = probe_acp_connection(
        cwd="/repo", prompt_text="ping", timeout_seconds=5, on_status=statuses.append
    )

    assert result.success is True
    assert result.response_text == "Olá"
    assert result.available_models == ["composer-2.5"]
    assert commands == [["agent", "acp"]]
    assert len(statuses) == 4
    assert '"ping"' in statuses[-1]


def test_a_session_without_an_id_fails_the_probe(monkeypatch):
    process = FakeProcess([_reply(1, {"protocolVersion": 1}), _reply(2, {"models": MODELS})])
    _spawn(monkeypatch, process)

    result = probe_acp_connection(cwd="/repo", timeout_seconds=5)

    assert result.success is False
    assert result.error == "missing_session_id"
    assert "session/prompt" not in process.stdin.methods()


def test_an_agent_that_answers_nothing_fails_the_probe_but_lists_models(monkeypatch):
    """A connected but mute agent is not healthy; its models are still useful to show."""
    process = FakeProcess(
        [
            _reply(1, {"protocolVersion": 1}),
            _reply(2, {"sessionId": "sess-1", "models": MODELS}),
            _reply(3, {"stopReason": "end_turn"}),
        ]
    )
    _spawn(monkeypatch, process)

    result = probe_acp_connection(cwd="/repo", timeout_seconds=5)

    assert result.success is False
    assert result.error == "empty_response"
    assert result.available_models == ["composer-2.5"]


def test_a_missing_agent_cli_fails_the_probe_with_the_reason(monkeypatch):
    _missing_binary(monkeypatch)

    result = probe_acp_connection(command=["agent", "acp"], cwd="/repo")

    assert result.success is False
    assert result.message == "ACP test failed"
    assert result.error == "agent"
