from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pulse.client.protocol import PING
from pulse.client.run_session import EngineRunSession

# Only sent to the fake daemon as a string; nothing touches the disk.
WORKSPACE = Path("/workspace/project")


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
    code = session.run(workflow_id="spec", user_prompt="x", workspace=WORKSPACE)
    assert code == 0
    stream.begin_phase.assert_called_with("Plan", turn=1)
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
    code = session.run(workflow_id="demo", user_prompt="x", workspace=WORKSPACE)
    assert code == 0
    prompt_handler.run_parsed_questionnaire.assert_called_once()
    questionnaire = prompt_handler.run_parsed_questionnaire.call_args[0][0]
    assert questionnaire.questions[0].prompt == "1. Qual stack?"
    assert client.answers == [("q1", "→ A) Python")]


def test_engine_run_session_recovers_questionnaire_from_agent_text():
    stream = MagicMock()
    stream.agent_text.return_value = (
        "Preciso de algumas informações antes de continuar.\n1. Qual stack?\nA) Python\nB) Dart\n"
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
    code = session.run(workflow_id="demo", user_prompt="x", workspace=WORKSPACE)
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
    code = session.run(workflow_id="demo", user_prompt="x", workspace=WORKSPACE)
    assert code == 1
    stream.error.assert_called_with(
        "Invalid questionnaire",
        "The agent asked for a questionnaire, but its questions could not be parsed.",
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
    code = session.run(workflow_id="spec", user_prompt="x", workspace=WORKSPACE)
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
    code = session.run(workflow_id="spec", user_prompt="x", workspace=WORKSPACE)
    assert code == 1
    stream.error.assert_called_with("Workflow falhou", "Falha na sessão ACP: timeout")


def test_attach_does_not_reopen_a_question_already_answered():
    """Attaching replays the run's past, except questions that already closed.

    Otherwise returning to the cockpit reopened every question of the run and
    answered ids the daemon had already forgotten.
    """
    from pulse.client.protocol import REPLAY_END

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

    assert [prompt_id for prompt_id, _ in client.answers] == ["p2"]
    assert prompt_handler.ask_text.call_count == 1


def test_attach_lets_the_screen_know_where_the_past_ends():
    from pulse.client.protocol import REPLAY_END

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
    """A freshly created run has no past: everything that arrives is live."""
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


def _replay(events: list[dict[str, Any]], *, prompt_handler: Any = None) -> tuple[Any, _FakeClient]:
    stream = MagicMock()
    client = _FakeClient(events)
    session = EngineRunSession(
        stream=stream, prompt_handler=prompt_handler or MagicMock(), client=client
    )
    session.run(workflow_id="demo", user_prompt="x")
    return stream, client


def test_run_context_and_session_id_reach_the_screen():
    """The artifacts pane points at the worktree, so cwd and branch must arrive as sent."""
    stream, _ = _replay(
        [
            {"type": "run.context", "cwd": "/repo/wt", "branch": "pulse/run-1"},
            {"type": "session.id", "session_id": "s-9"},
            {"type": "run.finished", "exit_code": 0},
        ]
    )
    stream.set_context.assert_called_once_with(cwd="/repo/wt", branch="pulse/run-1")
    stream.set_session_id.assert_called_once_with("s-9")


def test_awaiting_keeps_a_numeric_since_and_drops_anything_else():
    stream, _ = _replay(
        [
            {"type": "run.awaiting", "waiting": True, "since": 12.5},
            {"type": "run.awaiting", "waiting": False, "since": "soon"},
            {"type": "run.finished", "exit_code": 0},
        ]
    )
    assert stream.mark_awaiting.call_args_list == [
        ((True,), {"since": 12.5}),
        ((False,), {"since": None}),
    ]


def test_stop_and_stream_markers_are_forwarded():
    stream, _ = _replay(
        [
            {"type": "run.stopped"},
            {"type": "stream.finish_question"},
            {"type": "stream.finish"},
            {"type": "phase.info", "title": "note"},
            {"type": "something.unknown"},
            {"type": "run.finished", "exit_code": 130},
        ]
    )
    stream.mark_stopped.assert_called_once_with()
    stream.finish_question_prompt.assert_called_once_with()
    stream.info.assert_called_once_with("note")
    assert stream.finish.call_count == 2


def test_phase_sync_hands_the_step_list_and_statuses_to_the_screen():
    """A fan-out changes the step list mid-run; the screen rebuilds from this event."""
    steps = [{"id": "one", "label": "Um", "rounds": 1}, {"id": "two", "label": "Dois", "rounds": 2}]
    stream, _ = _replay(
        [
            {
                "type": "phases.sync",
                "steps": steps,
                "done_ids": ["one"],
                "skipped_ids": [],
                "failed_ids": ["two"],
                "blocked_ids": [],
            },
            {"type": "run.finished", "exit_code": 0},
        ]
    )
    stream.apply_phase_statuses.assert_called_once_with(
        steps=steps,
        done_ids=["one"],
        skipped_ids=[],
        failed_ids=["two"],
        blocked_ids=[],
    )


def test_each_prompt_kind_is_answered_by_its_handler():
    handler = MagicMock()
    handler.respond_to_create_plan.return_value = {"outcome": {"outcome": "approved"}}
    handler.respond_to_permission.return_value = {"outcome": {"outcome": "selected"}}
    handler.select_choice.return_value = 1
    _, client = _replay(
        [
            {"type": "prompt.request", "id": "plan", "kind": "create_plan", "payload": {"p": 1}},
            {
                "type": "prompt.request",
                "id": "perm",
                "kind": "permission",
                "payload": {"params": {"tool": "x"}, "policy": "deny_writes", "allow_terminal": 1},
            },
            {
                "type": "prompt.request",
                "id": "pick",
                "kind": "choice",
                "payload": {
                    "prompt": "which?",
                    "title": "T",
                    "choices": [{"label": "a", "index": 0}, {"label": "b", "index": 1}, "junk"],
                },
            },
            {"type": "prompt.request", "id": "odd", "kind": "mystery", "payload": None},
            {"type": "run.finished", "exit_code": 0},
        ],
        prompt_handler=handler,
    )
    handler.respond_to_create_plan.assert_called_once_with({"p": 1})
    handler.respond_to_permission.assert_called_once_with(
        {"tool": "x"}, policy="deny_writes", allow_terminal=True
    )
    handler.select_choice.assert_called_once_with("which?", [("a", 0), ("b", 1)], title="T")
    assert client.answers == [
        ("plan", {"outcome": {"outcome": "approved"}}),
        ("perm", {"outcome": {"outcome": "selected"}}),
        ("pick", {"index": 1}),
        ("odd", {"outcome": {"outcome": "cancelled"}}),
    ]


def test_permission_without_a_policy_asks():
    """Deny by default when unsure: a payload without a policy falls back to asking."""
    handler = MagicMock()
    handler.respond_to_permission.return_value = {}
    _replay(
        [
            {"type": "prompt.request", "id": "perm", "kind": "permission", "payload": {}},
            {"type": "run.finished", "exit_code": 0},
        ],
        prompt_handler=handler,
    )
    handler.respond_to_permission.assert_called_once_with({}, policy="ask", allow_terminal=False)


def test_a_ping_during_replay_ends_the_replay():
    """A run with no history yet sends a ping before anything else; the past is over."""
    stream = MagicMock()
    session = EngineRunSession(
        stream=stream,
        prompt_handler=MagicMock(),
        client=_FakeClient([{"type": PING}, {"type": "run.finished", "exit_code": 0}]),
    )
    assert session.attach("run-1") == 0
    stream.replay_finished.assert_called_once_with()


def test_a_later_turn_and_the_model_reach_the_screen_as_data():
    """The daemon sends the turn and the model as fields; the client composes no text.

    They used to travel as Portuguese titles the screen parsed back, which tied
    the TUI to the wording `acp/` produced. A turn the daemon omits, or sends as
    junk, is the phase's first.
    """
    from tests.fakes import RecordingStream

    stream = RecordingStream()
    events = [
        {"type": "phase.begin", "title": "Plan"},
        {"type": "session.model", "model": "GPT 5.5"},
        {"type": "phase.begin", "title": "Plan", "turn": 2},
        {"type": "phase.begin", "title": "Build", "turn": "two"},
        {"type": "run.finished", "exit_code": 0},
    ]
    session = EngineRunSession(
        stream=stream, prompt_handler=MagicMock(), client=_FakeClient(events)
    )

    assert session.run(workflow_id="demo", user_prompt="x", workspace=WORKSPACE) == 0
    assert stream.phases == ["Plan", "Plan", "Build"]
    assert stream.turns == [1, 2, 1]
    assert stream.models == ["GPT 5.5"]
