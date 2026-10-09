import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pulse.mcp.ask_bridge import AskQuestionBridgeServer, request_ask_question_via_socket


@pytest.fixture
def socket_path() -> Iterator[Path]:
    """A short private directory: `tmp_path` can exceed the AF_UNIX path limit on macOS."""
    with tempfile.TemporaryDirectory(prefix="pulse-ask-") as directory:
        yield Path(directory) / "ask.sock"


def test_ask_bridge_socket_roundtrip(socket_path: Path):
    handler = MagicMock()
    handler.respond_to_ask_question.return_value = {
        "outcome": {
            "outcome": "answered",
            "answers": [{"questionId": "q1", "selectedOptionIds": ["a"]}],
        }
    }
    server = AskQuestionBridgeServer(socket_path=socket_path, prompt_handler=handler)
    server.start()

    try:
        result = request_ask_question_via_socket(
            {
                "questions": [
                    {
                        "id": "q1",
                        "prompt": "Qual stack?",
                        "options": [{"id": "a", "label": "Python"}],
                    }
                ]
            },
            socket_path=str(socket_path),
        )
    finally:
        server.close()

    assert result["outcome"]["outcome"] == "answered"
    handler.respond_to_ask_question.assert_called_once()


def test_ask_bridge_handles_concurrent_connections(socket_path: Path):
    handler = MagicMock()
    handler.respond_to_ask_question.return_value = {
        "outcome": {"outcome": "answered", "answers": []}
    }
    server = AskQuestionBridgeServer(socket_path=socket_path, prompt_handler=handler)
    server.start()

    def client_call() -> dict:
        return request_ask_question_via_socket(
            {"questions": [{"id": "q1", "prompt": "Pergunta?", "options": []}]},
            socket_path=str(socket_path),
        )

    thread = threading.Thread(target=client_call)
    thread.start()
    thread.join(timeout=5)
    server.close()
    assert not thread.is_alive()
