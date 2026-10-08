"""The ACP transport of `AcpSessionRunner`: lifecycle, the read loop and agent requests.

The agent is untrusted and may crash, hang or ask anything; the runner must
answer every request id it receives, ignore what is not addressed to it, and
degrade (not crash) when an optional protocol call fails.
"""

from __future__ import annotations

import json
import subprocess
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from pulse.acp import reply_clock, session_runner
from pulse.acp.session_runner import AcpSessionRunner
from pulse.domain import ui_text
from pulse.domain.control import RunControl
from pulse.domain.ports import AgentProfile, NullPromptPort
from pulse.domain.run import StepRecord
from pulse.store import runs as run_store
from tests.conftest import make_workflow
from tests.fakes import RecordingStream


class _Pipe(StringIO):
    """Stdin that keeps what was written after the runner closes it."""

    def __init__(self, *, fail_on_close: bool = False) -> None:
        super().__init__()
        self.text = ""
        self.was_closed = False
        self._fail_on_close = fail_on_close

    def flush(self) -> None:
        self.text = self.getvalue()

    def close(self) -> None:
        self.text = self.getvalue()
        self.was_closed = True
        if self._fail_on_close:
            self._fail_on_close = False
            raise OSError("broken pipe")
        super().close()

    def messages(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.text.splitlines() if line.strip()]


class FakeProcess:
    """An agent process whose whole stdout is known up front."""

    def __init__(
        self,
        lines: list[dict[str, Any] | str] | None = None,
        *,
        exits_on_wait: int = 0,
        fail_stdin_close: bool = False,
    ) -> None:
        text = "".join(
            (line if isinstance(line, str) else json.dumps(line)) + "\n" for line in lines or []
        )
        self.stdin = _Pipe(fail_on_close=fail_stdin_close)
        self.stdout: StringIO | None = StringIO(text)
        self.returncode: int | None = None
        self.signals: list[str] = []
        self._hangs_left = exits_on_wait

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        """Hangs (`TimeoutExpired`) for the first `exits_on_wait` timed waits."""
        if timeout is not None and self._hangs_left:
            self._hangs_left -= 1
            raise subprocess.TimeoutExpired("agent", timeout)
        self.returncode = 0
        return 0

    def terminate(self) -> None:
        self.signals.append("terminate")

    def kill(self) -> None:
        self.signals.append("kill")


class SpyStream(RecordingStream):
    def __init__(self) -> None:
        super().__init__()
        self.updates: list[dict[str, Any]] = []
        self.calls: list[str] = []

    def handle_update(self, params: dict[str, Any]) -> None:
        self.updates.append(params)
        super().handle_update(params)

    def finish(self) -> None:
        self.calls.append("finish")

    def finish_question_prompt(self) -> None:
        self.calls.append("finish_question_prompt")

    def begin_user_wait(self) -> None:
        self.calls.append("begin_user_wait")

    def end_user_wait(self) -> None:
        self.calls.append("end_user_wait")


class Port(NullPromptPort):
    """A user who answers with fixed replies and remembers what was asked."""

    def __init__(self, *, fail: str = "") -> None:
        self.asked: list[tuple[str, Any]] = []
        self._fail = fail

    def _ask(self, name: str, payload: Any) -> None:
        self.asked.append((name, payload))
        if name == self._fail:
            raise RuntimeError(f"{name} broke")

    def respond_to_ask_question(self, params):
        self._ask("ask_question", params)
        return {"outcome": {"outcome": "answered", "answers": []}}

    def respond_to_create_plan(self, params):
        self._ask("create_plan", params)
        return {"outcome": {"outcome": "accepted"}}

    def respond_to_permission(self, params, *, policy, allow_terminal=False):
        self._ask("permission", {"policy": policy, "allow_terminal": allow_terminal})
        return {"outcome": {"outcome": "selected", "optionId": "user-pick"}}


def _request(request_id: int, method: str, params: dict[str, Any] | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def _reply(request_id: int, result: dict[str, Any]) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _runner(**kwargs: Any) -> AcpSessionRunner:
    kwargs.setdefault("enable_mcp_ask", False)
    kwargs.setdefault("timeout_seconds", 5)
    return AcpSessionRunner(["agent", "acp"], cwd="/repo", **kwargs)


def _read(runner: AcpSessionRunner, lines: list[dict[str, Any] | str]) -> FakeProcess:
    """Run the read loop to the end of `lines`, on this thread."""
    process = FakeProcess(lines)
    runner._process = process  # type: ignore[assignment]  # duck-typed Popen
    runner._read_stdout()
    return process


def _offline(runner: AcpSessionRunner) -> list[dict[str, Any]]:
    """Process-less runner: records what it sends; replies are queued by the test."""
    sent: list[dict[str, Any]] = []
    runner._send = sent.append  # type: ignore[method-assign]
    return sent


def _queue(runner: AcpSessionRunner, response: dict[str, Any]) -> None:
    runner._responses[response["id"]] = response
    runner._response_queue.put(response["id"])


# --- agent requests ------------------------------------------------------------


def test_an_ask_question_is_counted_answered_and_closes_the_text_prompt():
    port, stream = Port(), SpyStream()
    runner = _runner(prompt_handler=port, stream=stream)

    process = _read(runner, [_request(41, "cursor/ask_question", {"questions": []})])

    assert process.stdin.messages() == [
        _reply(41, {"outcome": {"outcome": "answered", "answers": []}})
    ]
    assert runner.ask_question_count == 1
    assert stream.calls == ["finish_question_prompt", "begin_user_wait", "end_user_wait"]


def test_a_plan_request_is_answered_by_the_user():
    port, stream = Port(), SpyStream()
    runner = _runner(prompt_handler=port, stream=stream)

    process = _read(runner, [_request(5, "cursor/create_plan", {"plan": "steps"})])

    assert process.stdin.messages() == [_reply(5, {"outcome": {"outcome": "accepted"}})]
    assert port.asked == [("create_plan", {"plan": "steps"})]
    assert runner.ask_question_count == 0


@pytest.mark.parametrize("method", ["session/request_permission", "cursor/request_permission"])
def test_a_permission_the_policy_cannot_decide_goes_to_the_user(method):
    """Under `ask` only a person decides; the port gets the runner's policy."""
    port = Port()
    runner = _runner(prompt_handler=port)

    process = _read(runner, [_request(9, method, {"toolCall": {"kind": "edit"}})])

    assert port.asked == [("permission", {"policy": "ask", "allow_terminal": False})]
    assert process.stdin.messages() == [
        _reply(9, {"outcome": {"outcome": "selected", "optionId": "user-pick"}})
    ]


def test_a_permission_the_agent_policy_resolves_never_reaches_the_user():
    """Policy is not a question: a run with no screen attached must not block on it."""
    port = Port()
    runner = _runner(prompt_handler=port)
    runner.use_agent(AgentProfile(agent_id="dev", model=None, permission_policy="auto_approve"))
    options = [
        {"optionId": "always", "kind": "allow_always"},
        {"optionId": "once", "kind": "allow_once"},
    ]

    process = _read(
        runner,
        [
            _request(
                3, "session/request_permission", {"toolCall": {"kind": "edit"}, "options": options}
            )
        ],
    )

    assert port.asked == []
    assert process.stdin.messages() == [
        _reply(3, {"outcome": {"outcome": "selected", "optionId": "once"}})
    ]


def test_an_unknown_agent_request_is_answered_cancelled():
    """The agent waits on every id; silence would hang its turn."""
    port = Port()
    runner = _runner(prompt_handler=port)

    process = _read(runner, [_request(12, "fs/read_text_file", {"path": "/etc/passwd"})])

    assert process.stdin.messages() == [_reply(12, {"outcome": "cancelled"})]
    assert port.asked == []


def test_a_failing_permission_handler_answers_with_a_json_rpc_error_and_keeps_reading():
    port = Port(fail="permission")
    runner = _runner(prompt_handler=port)

    process = _read(
        runner,
        [
            _request(4, "session/request_permission", {"toolCall": {"kind": "edit"}}),
            _reply(1, {"protocolVersion": 1}),
        ],
    )

    assert process.stdin.messages() == [
        {"jsonrpc": "2.0", "id": 4, "error": {"code": -32603, "message": "permission broke"}}
    ]
    assert runner._responses == {1: _reply(1, {"protocolVersion": 1})}


# --- read loop -----------------------------------------------------------------


def _chunk(session_id: str | None, text: str) -> dict[str, Any]:
    params: dict[str, Any] = {
        "update": {
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": text},
        }
    }
    if session_id is not None:
        params["sessionId"] = session_id
    return {"jsonrpc": "2.0", "method": "session/update", "params": params}


def test_noise_on_stdout_is_skipped_and_replies_are_queued():
    """Agents print banners and blank lines; only JSON-RPC with an int id is a reply."""
    runner = _runner()

    _read(
        runner,
        [
            "",
            "Starting agent v1.2…",
            {"jsonrpc": "2.0", "method": "$/progress", "params": {}},
            {"jsonrpc": "2.0", "id": "text-id", "result": {}},
            _reply(2, {"sessionId": "sess-1"}),
        ],
    )

    assert runner._responses == {2: _reply(2, {"sessionId": "sess-1"})}
    assert runner._response_queue.get_nowait() == 2
    assert runner._response_queue.empty()


def test_updates_of_another_session_are_not_shown():
    """A late update from the previous step's session must not leak into this step."""
    stream = SpyStream()
    runner = _runner(stream=stream)
    runner._session_id = "sess-2"

    _read(runner, [_chunk("sess-1", "old"), _chunk("sess-2", "new"), _chunk(None, "untagged")])

    assert stream.agent_text() == "newuntagged"


def test_updates_before_any_session_are_shown():
    stream = SpyStream()
    runner = _runner(stream=stream)

    _read(runner, [_chunk("sess-9", "hello")])

    assert stream.agent_text() == "hello"


def test_a_process_without_stdout_ends_the_read_loop_at_once():
    runner = _runner()
    process = FakeProcess()
    process.stdout = None
    runner._process = process  # type: ignore[assignment]  # duck-typed Popen

    runner._read_stdout()

    assert runner._response_queue.empty()


# --- lifecycle -------------------------------------------------------------------


def _handshake(auth_methods: list[Any]) -> list[dict[str, Any] | str]:
    return [
        _reply(1, {"protocolVersion": 1, "authMethods": auth_methods}),
        _reply(2, {}),
        _reply(3, {"sessionId": "sess-1"}),
        _chunk("sess-1", "hi"),
        _reply(4, {"stopReason": "end_turn"}),
    ]


def test_run_prompt_handshakes_logs_in_prompts_and_closes(monkeypatch, tmp_path):
    advertised = [{"id": "cursor_login"}, "garbage", {"name": "no id"}]
    process = FakeProcess(_handshake(advertised))
    monkeypatch.setattr(session_runner.subprocess, "Popen", lambda *_a, **_k: process)
    stream = SpyStream()
    runner = AcpSessionRunner(
        ["agent", "acp"], cwd=str(tmp_path), stream=stream, enable_mcp_ask=False
    )

    result = runner.run_prompt("say hi")

    methods = [message.get("method") for message in process.stdin.messages()]
    assert methods == [
        "initialize",
        "notifications/initialized",
        "authenticate",
        "session/new",
        "session/prompt",
    ]
    assert process.stdin.messages()[2]["params"] == {"methodId": "cursor_login"}
    assert result == {"stopReason": "end_turn"}
    assert stream.calls[-1] == "finish"
    assert process.stdin.was_closed
    assert runner.last_session_id == "sess-1"


def test_run_prompt_without_a_session_id_fails_and_still_closes(monkeypatch, tmp_path):
    process = FakeProcess([_reply(1, {"protocolVersion": 1}), _reply(2, {})])
    monkeypatch.setattr(session_runner.subprocess, "Popen", lambda *_a, **_k: process)
    stream = SpyStream()
    runner = AcpSessionRunner(
        ["agent", "acp"], cwd=str(tmp_path), stream=stream, enable_mcp_ask=False
    )

    with pytest.raises(RuntimeError, match="no sessionId"):
        runner.run_prompt("say hi")

    assert "session/prompt" not in [m.get("method") for m in process.stdin.messages()]
    assert stream.calls == ["finish"]
    assert process.stdin.was_closed


def test_an_agent_without_auth_methods_is_not_asked_to_authenticate():
    """Agents logged in through their own CLI advertise none, and reject the call."""
    runner = _runner()
    sent = _offline(runner)

    assert runner.authenticate() == {}
    assert sent == []


def test_a_rejected_authentication_does_not_fail_the_run():
    """The runtime's own login may still be valid; the first real request will tell."""
    runner = _runner()
    sent = _offline(runner)
    runner._auth_methods = ["cursor_login"]
    _queue(runner, {"id": 1, "error": {"message": "already logged in"}})

    assert runner.authenticate() == {}
    assert sent[0]["method"] == "authenticate"


def test_a_session_new_advertises_the_ask_bridge_while_it_runs(monkeypatch):
    """The agent asks questions through the MCP bridge only Pulse knows the url of."""
    monkeypatch.setattr(session_runner.subprocess, "Popen", lambda *_a, **_k: FakeProcess())
    runner = AcpSessionRunner(["agent", "acp"], cwd="/repo", timeout_seconds=5)
    runner.start()
    sent = _offline(runner)
    _queue(runner, _reply(1, {"sessionId": "sess-1"}))
    _queue(runner, _reply(2, {"sessionId": "sess-2"}))

    runner.new_session("/repo", workflow="demo")
    runner.close()
    runner.new_session("/repo")

    (server,) = sent[0]["params"]["mcpServers"]
    assert server["type"] == "http"
    assert server["url"].startswith("http://127.0.0.1:")
    assert sent[0]["params"]["_meta"]["pulse"]["workflow"] == "demo"
    assert sent[1]["params"]["mcpServers"] == []


def test_close_survives_a_broken_stdin_and_escalates_a_process_that_will_not_exit():
    """A hung agent must not keep the daemon from closing: terminate, then kill."""
    runner = _runner()
    process = FakeProcess(exits_on_wait=2, fail_stdin_close=True)
    runner._process = process  # type: ignore[assignment]  # duck-typed Popen

    runner.close()

    assert process.stdin.was_closed
    assert process.signals == ["terminate", "kill"]
    assert process.returncode == 0


def test_close_terminates_a_slow_process_without_killing_it():
    runner = _runner()
    process = FakeProcess(exits_on_wait=1)
    runner._process = process  # type: ignore[assignment]  # duck-typed Popen

    runner.close()

    assert process.signals == ["terminate"]


def test_close_without_a_process_is_a_no_op():
    runner = _runner()

    runner.close()
    runner.close()

    assert runner._process is None


def test_revive_leaves_a_healthy_agent_alone():
    runner = _runner()
    process = FakeProcess()
    runner._process = process  # type: ignore[assignment]  # duck-typed Popen

    assert runner.revive() is False
    assert process.stdin.was_closed is False


def test_revive_restarts_a_dead_agent_and_drops_its_stale_replies(monkeypatch):
    """A retry after a crash must not read a reply meant for the dead process."""
    fresh = FakeProcess([_reply(1, {"protocolVersion": 1})])
    monkeypatch.setattr(session_runner.subprocess, "Popen", lambda *_a, **_k: fresh)
    runner = _runner()
    dead = FakeProcess()
    dead.returncode = 1
    runner._process = dead  # type: ignore[assignment]  # duck-typed Popen
    runner._session_id = "sess-old"
    runner._next_id = 1
    _queue(runner, _reply(7, {"stale": True}))

    assert runner.revive() is True

    assert dead.stdin.was_closed
    assert runner._process is fresh
    assert [m.get("method") for m in fresh.stdin.messages()] == [
        "initialize",
        "notifications/initialized",
    ]
    assert 7 not in runner._responses


# --- optional protocol calls ----------------------------------------------------


MODEL_SESSION = {"models": {"availableModels": [{"modelId": "gpt-5.5", "name": "GPT 5.5"}]}}


def test_apply_model_announces_the_model_it_set():
    stream = SpyStream()
    runner = _runner(stream=stream)
    sent = _offline(runner)
    runner._session_id = "sess-1"
    _queue(runner, _reply(1, {}))

    runner.apply_model(MODEL_SESSION, "gpt-5.5")

    assert sent == [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "session/set_model",
            "params": {"sessionId": "sess-1", "modelId": "gpt-5.5"},
        }
    ]
    titles = [update["update"].get("title") for update in stream.updates]
    assert titles == [ui_text.model_notice("GPT 5.5")]


def test_a_rejected_model_is_not_announced_and_does_not_fail_the_session():
    """Showing a model that was never applied would mislead the user."""
    stream = SpyStream()
    runner = _runner(stream=stream)
    _offline(runner)
    runner._session_id = "sess-1"
    _queue(runner, {"id": 1, "error": {"message": "unknown model"}})

    runner.apply_model(MODEL_SESSION, "gpt-5.5")

    assert stream.updates == []


@pytest.mark.parametrize(
    ("session_id", "model"), [(None, "gpt-5.5"), ("sess-1", "a model the agent lacks")]
)
def test_apply_model_sends_nothing_without_a_session_or_a_matching_model(session_id, model):
    runner = _runner()
    sent = _offline(runner)
    runner._session_id = session_id

    runner.apply_model(MODEL_SESSION, model)

    assert sent == []


def test_a_rejected_mode_does_not_fail_the_session():
    runner = _runner()
    sent = _offline(runner)
    runner._session_id = "sess-1"
    _queue(runner, {"id": 1, "error": {"message": "mode locked"}})

    runner.apply_mode({}, execute=True)

    assert sent[0]["params"] == {"sessionId": "sess-1", "modeId": "agent"}


def test_apply_mode_sends_nothing_when_no_mode_fits():
    """An agent whose modes match none of ours and that names no current mode keeps its own."""
    runner = _runner()
    sent = _offline(runner)

    runner.apply_mode({}, execute=True)
    runner._session_id = "sess-1"
    runner.apply_mode({"modes": {"availableModes": [{"id": "yolo"}]}}, execute=True)

    assert sent == []


def test_set_model_sends_the_model_for_the_session():
    runner = _runner()
    sent = _offline(runner)
    _queue(runner, _reply(1, {"ok": True}))

    assert runner.set_model("sess-1", "gpt-5.5") == {"ok": True}
    assert sent[0]["method"] == "session/set_model"
    assert sent[0]["params"] == {"sessionId": "sess-1", "modelId": "gpt-5.5"}


def test_close_session_without_an_open_session_sends_nothing():
    runner = _runner()
    sent = _offline(runner)

    runner.close_session()

    assert sent == []


def test_a_stop_without_an_active_session_sends_no_cancel(monkeypatch):
    monkeypatch.setattr(reply_clock, "CANCEL_GRACE_SECONDS", 0.0)
    control = RunControl()
    control.stop()
    runner = _runner(control=control)
    sent = _offline(runner)

    assert runner._request("session/prompt", {}) == {"stopReason": "cancelled"}
    assert [payload["method"] for payload in sent] == ["session/prompt"]


def test_a_cancel_that_cannot_be_sent_still_ends_the_turn_as_cancelled(monkeypatch):
    """The pipe may already be gone when the user stops; the stop must still land."""
    monkeypatch.setattr(reply_clock, "CANCEL_GRACE_SECONDS", 0.0)
    control = RunControl()
    control.stop()
    runner = _runner(control=control)
    runner._session_id = "sess-1"
    sent: list[str] = []

    def send(payload: dict[str, Any]) -> None:
        if payload["method"] == "session/cancel":
            raise OSError("broken pipe")
        sent.append(payload["method"])

    runner._send = send  # type: ignore[method-assign]

    assert runner._request("session/prompt", {}) == {"stopReason": "cancelled"}
    assert sent == ["session/prompt"]


def test_send_before_start_is_an_error():
    with pytest.raises(RuntimeError, match="not started"):
        _runner().set_mode("sess-1", "plan")


# --- user waits -------------------------------------------------------------------


class _Waits:
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[tuple[str, ...]] = []
        self._fail = fail

    def user_wait_began(self) -> None:
        if self._fail:
            raise ValueError("clock store down")
        self.events.append(("began",))

    def user_wait_ended(self, step_id: str, seconds: float) -> None:
        self.events.append(("ended", step_id))


def test_nested_questions_count_as_one_user_wait():
    """A question opened inside another must not pause the step clock twice."""
    stream, waits = SpyStream(), _Waits()
    runner = _runner(stream=stream)
    runner.bind_run("", waits)
    runner._phase_id = "plan"

    runner._begin_user_wait()
    runner._begin_user_wait()
    runner._end_user_wait()
    assert stream.calls == ["begin_user_wait"]
    runner._end_user_wait()

    assert stream.calls == ["begin_user_wait", "end_user_wait"]
    assert waits.events == [("began",), ("ended", "plan")]


def test_a_wait_listener_failure_is_logged_and_the_answer_still_arrives(tmp_path: Path):
    make_workflow("demo", steps=[("plan", "Plan")])
    run_store.create_run(
        run_id="run-1",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[StepRecord(step_id="plan", position=1, label="Plan")],
    )
    port = Port()
    runner = _runner(prompt_handler=port)
    runner.bind_run("run-1", _Waits(fail=True))
    runner._phase_id = "plan"

    answer = runner.prompts.respond_to_create_plan({"plan": "x"})

    assert answer == {"outcome": {"outcome": "accepted"}}
    events = [(row["kind"], row["title"], row["detail"]) for row in run_store.list_events("run-1")]
    assert ("Info", "User wait not recorded", "ValueError: clock store down") in events


def test_the_runner_exposes_the_control_it_was_given():
    control = RunControl()

    assert _runner(control=control).control is control
