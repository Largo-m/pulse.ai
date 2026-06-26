import json
import time
from io import StringIO
from unittest.mock import MagicMock, patch

from pulse.acp.client import AcpClient, probe_acp_connection


def _make_process(stdout_text: str) -> MagicMock:
    process = MagicMock()
    process.stdin = StringIO()
    process.stdout = StringIO(stdout_text)
    process.stderr = StringIO()
    process.wait.return_value = 0
    process.terminate.return_value = None
    return process


def test_acp_client_initialize_and_session():
    stdout_text = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": 1}}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "sessionId": "sess-1",
                        "models": {"availableModels": [{"modelId": "m1", "name": "Model 1"}]},
                    },
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": "Hello"},
                        }
                    },
                }
            ),
            json.dumps({"jsonrpc": "2.0", "id": 3, "result": {"stopReason": "end_turn"}}),
        ]
    ) + "\n"

    with patch("pulse.acp.client.subprocess.Popen", return_value=_make_process(stdout_text)):
        client = AcpClient(["agent", "acp"], timeout_seconds=5)
        client.start()
        time.sleep(0.05)
        client.initialize()
        session = client.new_session("/tmp")
        assert session["sessionId"] == "sess-1"
        client.prompt("sess-1", "Say hello")
        assert client.collect_message_text() == "Hello"
        client.close()


def test_probe_acp_connection_success():
    stdout_text = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": 1}}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "sessionId": "sess-1",
                        "models": {"availableModels": [{"modelId": "m1", "name": "composer-2.5"}]},
                    },
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": "Olá"},
                        }
                    },
                }
            ),
            json.dumps({"jsonrpc": "2.0", "id": 3, "result": {"stopReason": "end_turn"}}),
        ]
    ) + "\n"

    with patch("pulse.acp.client.subprocess.Popen", return_value=_make_process(stdout_text)):
        result = probe_acp_connection(command=["agent", "acp"], cwd="/tmp", timeout_seconds=5)

    assert result.success is True
    assert "Olá" in result.response_text
    assert "composer-2.5" in result.available_models
