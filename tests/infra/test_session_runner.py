import json
import time
from io import StringIO
from unittest.mock import MagicMock, patch

from pulse.acp.session_runner import AcpSessionRunner


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
        )
        runner.start()
        time.sleep(0.05)
        runner.initialize()
        runner.new_session("/workspace/repo")
        result = runner.prompt("sess-1", "setup")
        sent = runner._process.stdin.getvalue()
        runner.close()

    assert result["stopReason"] == "end_turn"
    assert '"answers"' in sent
    assert '"questionId"' in sent


def test_the_runner_is_the_agent_session_adapter():
    from pulse.domain.ports import AgentSession

    assert isinstance(AcpSessionRunner(["agent", "acp"], cwd="/workspace/repo"), AgentSession)


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
            ["agent", "acp"], cwd="/elsewhere", timeout_seconds=5, enable_mcp_ask=False
        )
        runner.open(tmp_path)
        runner.close()

    assert popen.call_args.kwargs["cwd"] == str(tmp_path)
