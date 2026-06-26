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

    with patch("pulse.acp.session_runner.subprocess.Popen", return_value=_make_process(stdout_text)):
        with patch(
            "pulse.presentation.prompt.handler.questionary.select",
            return_value=type("Answer", (), {"ask": lambda self: "py"})(),
        ):
            runner = AcpSessionRunner(["agent", "acp"], cwd="/tmp", timeout_seconds=5)
            runner.start()
            time.sleep(0.05)
            runner.initialize()
            runner.new_session("/tmp")
            result = runner.prompt("sess-1", "setup")
            sent = runner._process.stdin.getvalue()
            runner.close()

    assert result["stopReason"] == "end_turn"
    assert '"answers"' in sent
    assert '"questionId"' in sent
