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

    def start_run(self, workflow_id: str, **kwargs: Any) -> dict[str, Any]:
        self.start_kwargs = kwargs
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


def test_engine_run_session_runs_questionnaire_from_questions():
    stream = MagicMock()
    prompt_handler = MagicMock()
    prompt_handler.run_parsed_questionnaire.return_value = "→ A) Python"
    events = [
        {
            "type": "prompt.request",
            "id": "q1",
            "kind": "questionnaire",
            "payload": {
                "title": "Preciso de algumas informações",
                "questions": [
                    {
                        "id": "q1",
                        "prompt": "1. Qual stack?",
                        "options": [{"id": "A", "label": "Python"}],
                    }
                ],
            },
        },
        {"type": "run.finished", "exit_code": 0},
    ]
    client = _FakeClient(events)
    session = EngineRunSession(stream=stream, prompt_handler=prompt_handler, client=client)
    code = session.run(workflow_id="demo", user_prompt="x", workspace=Path("/tmp"))
    assert code == 0
    prompt_handler.run_parsed_questionnaire.assert_called_once()
    questionnaire = prompt_handler.run_parsed_questionnaire.call_args[0][0]
    assert questionnaire.questions[0].prompt == "1. Qual stack?"
    assert client.answers == [("q1", "→ A) Python")]


def test_engine_run_session_recovers_questionnaire_from_agent_text():
    stream = MagicMock()
    stream.agent_text.return_value = (
        "Preciso de algumas informações antes de continuar.\n"
        "1. Qual stack?\n"
        "A) Python\n"
        "B) Dart\n"
    )
    prompt_handler = MagicMock()
    prompt_handler.run_parsed_questionnaire.return_value = "→ A) Python"
    session = EngineRunSession(
        stream=stream,
        prompt_handler=prompt_handler,
        client=_FakeClient(
            [
                {
                    "type": "prompt.request",
                    "id": "q1",
                    "kind": "questionnaire",
                    "payload": {"title": "Preciso de algumas informações"},
                },
                {"type": "run.finished", "exit_code": 0},
            ]
        ),
    )
    code = session.run(workflow_id="demo", user_prompt="x", workspace=Path("/tmp"))
    assert code == 0
    questionnaire = prompt_handler.run_parsed_questionnaire.call_args[0][0]
    assert questionnaire.questions[0].options[0] == ("A", "Python")


def test_engine_run_session_errors_when_questionnaire_missing():
    stream = MagicMock()
    stream.agent_text.return_value = ""
    prompt_handler = MagicMock()
    session = EngineRunSession(
        stream=stream,
        prompt_handler=prompt_handler,
        client=_FakeClient(
            [
                {"type": "prompt.request", "id": "q1", "kind": "questionnaire", "payload": {}},
                {"type": "run.finished", "exit_code": 1},
            ]
        ),
    )
    code = session.run(workflow_id="demo", user_prompt="x", workspace=Path("/tmp"))
    assert code == 1
    stream.error.assert_called_with(
        "Questionário inválido",
        "O agente pediu um questionário, mas as perguntas não puderam ser abertas.",
    )


def test_engine_run_session_maps_phase_error():
    stream = MagicMock()
    session = EngineRunSession(
        stream=stream,
        prompt_handler=MagicMock(),
        client=_FakeClient(
            [
                {
                    "type": "phase.error",
                    "title": "Classificação cancelada",
                    "reason": "O agente não definiu o flow (quick ou full).",
                },
                {"type": "run.finished", "exit_code": 1},
            ]
        ),
    )
    code = session.run(workflow_id="spec", user_prompt="x", workspace=Path("/tmp"))
    assert code == 1
    stream.error.assert_called_with(
        "Classificação cancelada",
        "O agente não definiu o flow (quick ou full).",
    )


def test_engine_run_session_maps_run_finished_error():
    stream = MagicMock()
    session = EngineRunSession(
        stream=stream,
        prompt_handler=MagicMock(),
        client=_FakeClient(
            [{"type": "run.finished", "exit_code": 1, "error": "Falha na sessão ACP: timeout"}]
        ),
    )
    code = session.run(workflow_id="spec", user_prompt="x", workspace=Path("/tmp"))
    assert code == 1
    stream.error.assert_called_with("Workflow falhou", "Falha na sessão ACP: timeout")




def test_attach_does_not_reopen_a_question_already_answered():
    """Anexar reexecuta o passado da run — menos as perguntas que já fecharam.

    Sem isto, voltar ao cockpit reabria cada pergunta da run inteira e ainda
    respondia a ids que o daemon já tinha esquecido.
    """
    from pulse.daemon.protocol import REPLAY_END

    stream = MagicMock()
    prompt_handler = MagicMock()
    prompt_handler.ask_text.return_value = "resposta"
    events = [
        {"type": "run.started", "run_id": "run-1"},
        {"type": "phase.begin", "title": "Um"},
        {"type": "prompt.request", "id": "p1", "kind": "text", "payload": {"prompt": "a?"}},
        {"type": "prompt.answered", "id": "p1"},
        {"type": "prompt.request", "id": "p2", "kind": "text", "payload": {"prompt": "b?"}},
        {"type": REPLAY_END, "count": 5},
    ]
    client = _FakeClient(events)
    session = EngineRunSession(stream=stream, prompt_handler=prompt_handler, client=client)
    session.attach("run-1")

    # p1 fechou durante o replay; p2 é a que ainda espera alguém.
    assert [prompt_id for prompt_id, _ in client.answers] == ["p2"]
    assert prompt_handler.ask_text.call_count == 1


def test_attach_lets_the_screen_know_where_the_past_ends():
    from pulse.daemon.protocol import REPLAY_END

    stream = MagicMock()
    events = [
        {"type": "phase.begin", "title": "Um"},
        {"type": REPLAY_END, "count": 1},
        {"type": "phase.info", "title": "vivo"},
    ]
    session = EngineRunSession(
        stream=stream,
        prompt_handler=MagicMock(),
        client=_FakeClient(events),
    )
    session.attach("run-1")
    stream.replay_finished.assert_called_once()


def test_a_fresh_run_never_defers_a_prompt():
    """Run recém-criada não tem passado: tudo que chega é agora."""
    prompt_handler = MagicMock()
    prompt_handler.ask_text.return_value = "ok"
    client = _FakeClient(
        [
            {"type": "prompt.request", "id": "p1", "kind": "text", "payload": {"prompt": "a?"}},
            {"type": "run.finished", "exit_code": 0},
        ]
    )
    session = EngineRunSession(
        stream=MagicMock(),
        prompt_handler=prompt_handler,
        client=client,
    )
    assert session.run(workflow_id="demo", user_prompt="x") == 0
    assert [prompt_id for prompt_id, _ in client.answers] == ["p1"]
