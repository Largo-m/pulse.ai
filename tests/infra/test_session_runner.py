import json
from io import StringIO
from unittest.mock import MagicMock, patch

from pulse.acp.session_runner import AcpSessionRunner
from pulse.runtimes import get_runtime


def _make_process(stdout_text: str) -> MagicMock:
    process = MagicMock()
    process.stdin = StringIO()
    process.stdout = StringIO(stdout_text)
    process.stderr = StringIO()
    process.poll.return_value = None
    process.wait.return_value = 0
    process.terminate.return_value = None
    return process


def test_session_runner_handles_ask_question_request():
    stdout_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": 1}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"sessionId": "sess-1"}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 99,
                "method": "cursor/ask_question",
                "params": {
                    "questions": [
                        {
                            "id": "q1",
                            "prompt": "Qual stack?",
                            "options": [
                                {"id": "py", "label": "Python"},
                                {"id": "ts", "label": "TypeScript"},
                            ],
                        }
                    ]
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {"stopReason": "end_turn"}}),
    ]
    stdout_text = "\n".join(stdout_lines) + "\n"

    class FakePrompt:
        def respond_to_ask_question(self, params):
            return {
                "outcome": {
                    "outcome": "answered",
                    "answers": [{"questionId": "q1", "selectedOptionIds": ["py"]}],
                }
            }

        def respond_to_create_plan(self, params):
            return {"outcome": {"outcome": "cancelled"}}

        def respond_to_permission(self, params, *, policy, allow_terminal=False):
            return {"outcome": {"outcome": "cancelled"}}

        def run_parsed_questionnaire(self, questionnaire):
            return None

        def run_text_questionnaire(self, text):
            return None

    with patch(
        "pulse.acp.session_runner.subprocess.Popen", return_value=_make_process(stdout_text)
    ):
        runner = AcpSessionRunner(
            ["agent", "acp"],
            cwd="/workspace/repo",
            timeout_seconds=5,
            prompt_handler=FakePrompt(),
            runtime=get_runtime("cursor"),
        )
        runner.start()
        runner.initialize()
        runner.new_session("/workspace/repo")
        result = runner.prompt("sess-1", "setup")
        sent = runner._process.stdin.getvalue()
        runner.close()

    assert result["stopReason"] == "end_turn"
    assert '"answers"' in sent
    assert '"questionId"' in sent


def test_a_step_on_another_runtime_restarts_the_agent_process(tmp_path):
    """The run opens on the project runtime; a step whose agent names another
    one must talk to that CLI, or its model is applied to the wrong catalog.
    """
    from pulse.domain.ports import AgentProfile
    from pulse.runtimes.codex import CODEX_ACP_PACKAGE, CODEX_ACP_VERSION

    codex_command = ["npx", "-y", f"{CODEX_ACP_PACKAGE}@{CODEX_ACP_VERSION}"]
    first = _make_process(
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": 1}}) + "\n"
    )
    second = _make_process(
        json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"protocolVersion": 1}}) + "\n"
    )
    with patch("pulse.acp.session_runner.subprocess.Popen", side_effect=[first, second]) as popen:
        runner = AcpSessionRunner(
            ["agent", "acp"], cwd=str(tmp_path), timeout_seconds=5, runtime=get_runtime("cursor")
        )
        runner.open(tmp_path)
        runner.use_agent(
            AgentProfile(
                agent_id="implement",
                model="6 Luna (medium)",
                permission_policy="auto_approve",
                runtime_id="codex",
                acp_command=tuple(codex_command),
                dialect=get_runtime("codex"),
            )
        )
        runner.close()

    assert popen.call_count == 2
    assert popen.call_args_list[1].args[0] == codex_command
    assert runner._runtime is get_runtime("codex")


def test_a_step_on_the_same_runtime_keeps_the_agent_process(tmp_path):
    from pulse.domain.ports import AgentProfile

    handshake = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": 1}}) + "\n"
    with patch(
        "pulse.acp.session_runner.subprocess.Popen",
        return_value=_make_process(handshake),
    ) as popen:
        runner = AcpSessionRunner(
            ["agent", "acp"], cwd=str(tmp_path), timeout_seconds=5, runtime=get_runtime("cursor")
        )
        runner.open(tmp_path)
        runner.use_agent(
            AgentProfile(
                agent_id="prd",
                model="grok-4.7",
                permission_policy="ask",
                runtime_id="cursor",
                acp_command=("agent", "acp"),
                dialect=get_runtime("cursor"),
            )
        )
        runner.close()

    assert popen.call_count == 1


def test_the_runner_is_the_agent_session_adapter():
    from pulse.domain.ports import AgentSession

    assert isinstance(
        AcpSessionRunner(["agent", "acp"], cwd="/workspace/repo", runtime=get_runtime("cursor")),
        AgentSession,
    )


def test_open_starts_the_agent_where_the_run_works(tmp_path):
    """The engine learns the worktree after the session is built; the agent must start there."""
    handshake = "\n".join(
        json.dumps({"jsonrpc": "2.0", "id": index, "result": {"protocolVersion": 1}})
        for index in (1, 2)
    )
    with patch(
        "pulse.acp.session_runner.subprocess.Popen",
        return_value=_make_process(handshake + "\n"),
    ) as popen:
        runner = AcpSessionRunner(
            ["agent", "acp"], cwd="/elsewhere", timeout_seconds=5, runtime=get_runtime("cursor")
        )
        runner.open(tmp_path)
        runner.close()

    assert popen.call_args.kwargs["cwd"] == str(tmp_path)


def test_every_registered_runtime_is_a_dialect_the_runner_accepts():
    from pulse.domain.ports import RuntimeDialect
    from pulse.runtimes import RUNTIMES

    assert all(isinstance(runtime, RuntimeDialect) for runtime in RUNTIMES.values())


def test_the_mcp_channel_hands_out_its_url_until_closed():
    from pulse.domain.ports import NullPromptPort, QuestionChannel
    from pulse.mcp.channel import McpQuestionChannel

    channel = McpQuestionChannel()
    assert isinstance(channel, QuestionChannel)

    (server,) = channel.open(NullPromptPort(), lambda: None)
    try:
        assert server["type"] == "http"
        assert str(server["url"]).startswith("http://127.0.0.1:")
    finally:
        channel.close()
    channel.close()


def test_the_runner_tells_its_log_where_it_is_and_what_the_agent_did():
    """The log adapter only sees what the runner forwards; a missed call is a hole in history."""
    from types import SimpleNamespace

    from tests.fakes import RecordingSessionLog, RecordingStream

    log = RecordingSessionLog()
    runner = AcpSessionRunner(
        ["agent", "acp"],
        cwd="/repo",
        runtime=get_runtime("cursor"),
        stream=RecordingStream(),
        session_log=log,
        pulse_agent="tester",
    )
    update = {"sessionId": "sess-1", "update": {"sessionUpdate": "agent_message_chunk"}}
    lines = [json.dumps({"jsonrpc": "2.0", "method": "session/update", "params": update})]

    runner.bind_run("run-1")
    runner._enter_phase("plan")
    runner._activate_session("sess-1")
    runner._process = SimpleNamespace(stdout=iter(lines), poll=lambda: None)  # type: ignore[assignment]  # only stdout is read
    runner._read_stdout()
    runner._begin_phase("Plan")

    assert [name for name, _args in log.calls] == [
        "bind_run",
        "enter_step",
        "enter_session",
        "update",
        "flush",
        "phase",
    ]
    assert log.named("enter_session") == [("sess-1", "/repo", "tester")]
    assert log.named("update") == [(update,)]
