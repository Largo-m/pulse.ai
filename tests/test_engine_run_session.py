from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pulse.client.run_session import EngineRunSession


class _FakeClient:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self.answers: list[tuple[str, Any]] = []

    def ensure_daemon(self) -> None:
        return None

    def start_run(self, workflow_id: str, *, prompt: str, workspace: str | None = None) -> dict[str, Any]:
        return {"id": "run-1", "workflow_id": workflow_id, "status": "running"}

    def stream_events(self, run_id: str):
        yield from self._events

    def answer_prompt(self, prompt_id: str, answer: Any) -> dict[str, Any]:
        self.answers.append((prompt_id, answer))
        return {"ok": True}

    def close(self) -> None:
        return None


def test_engine_run_session_maps_events():
    stream = MagicMock()
    prompt_handler = MagicMock()
    prompt_handler.respond_to_ask_question.return_value = {
        "outcome": {"outcome": "selected", "optionId": "y"}
    }
    events = [
        {"type": "run.started", "run_id": "run-1"},
        {"type": "phase.begin", "title": "Plan"},
        {
            "type": "session.update",
            "params": {
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": "hi"},
                }
            },
        },
        {
            "type": "prompt.request",
            "id": "p1",
            "kind": "ask_question",
            "payload": {"questions": []},
        },
        {"type": "run.finished", "exit_code": 0},
    ]
    client = _FakeClient(events)
    session = EngineRunSession(stream=stream, prompt_handler=prompt_handler, client=client)
    code = session.run(workflow_id="spec", user_prompt="x", workspace=Path("/tmp"))
    assert code == 0
    stream.begin_phase.assert_called_with("Plan")
    stream.handle_update.assert_called()
    prompt_handler.respond_to_ask_question.assert_called_once()
    assert client.answers == [("p1", {"outcome": {"outcome": "selected", "optionId": "y"}})]


def test_engine_run_session_maps_workflow_route():
    stream = MagicMock()
    prompt_handler = MagicMock()
    events = [
        {"type": "phase.begin", "title": "Classificar spec"},
        {"type": "workflow.route", "flow": "quick"},
        {"type": "run.finished", "exit_code": 0},
    ]
    session = EngineRunSession(
        stream=stream,
        prompt_handler=prompt_handler,
        client=_FakeClient(events),
    )
    code = session.run(workflow_id="spec", user_prompt="x", workspace=Path("/tmp"))
    assert code == 0
    stream.apply_routed_flow.assert_called_with("quick")
