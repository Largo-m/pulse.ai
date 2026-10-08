"""Edges of the daemon adapters: what each sink call publishes and how prompts degrade.

The cockpit is rebuilt from the bus alone (live or on replay), so every sink call
must land there with its fields; prompt answers that are missing or blank must
reach the engine as "no answer", never as an empty value.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import pulse.daemon.adapters as adapters_module
from pulse.client.protocol import REPLAY_END
from pulse.daemon.adapters import ApiPromptPort, ApiStreamSink
from pulse.daemon.events import EventBus
from pulse.replies.text_questionnaire import parse_text_questionnaire

QUESTIONNAIRE_TEXT = """
```text
1. Which database?

A) SQLite
B) Postgres
```
"""


def _replayed(bus: EventBus) -> list[dict]:
    events: list[dict] = []
    for event in bus.subscribe(after=0):
        if event.get("type") == REPLAY_END:
            break
        events.append(event)
    return events


def _without_seq(events: list[dict]) -> list[dict]:
    return [{k: v for k, v in event.items() if k not in {"seq", "ts"}} for event in events]


class _AnsweringCorrelator:
    """Stands in for the client: answers every prompt with the same value."""

    def __init__(self, answer: object) -> None:
        self._answer = answer
        self.asked: list[tuple[str, dict]] = []

    def request(self, kind: str, payload: dict, *, timeout: float | None = None) -> object:
        self.asked.append((kind, payload))
        return self._answer


def _chunk(text: str, *, content_type: str = "text", kind: str = "agent_message_chunk") -> dict:
    return {"update": {"sessionUpdate": kind, "content": {"type": content_type, "text": text}}}


def test_agent_text_accumulates_only_agent_text_chunks():
    """The captured text feeds outcome parsing; thoughts or images must not leak into it."""
    sink = ApiStreamSink(EventBus())

    sink.handle_update(_chunk("Hello "))
    sink.handle_update(_chunk("ignored", content_type="image"))
    sink.handle_update(_chunk("thinking", kind="agent_thought_chunk"))
    sink.handle_update({"update": "not-a-mapping"})
    sink.handle_update(_chunk("world"))

    assert sink.agent_text() == "Hello world"


def test_every_update_is_published_even_when_not_captured():
    bus = EventBus()
    params = _chunk("thinking", kind="agent_thought_chunk")

    ApiStreamSink(bus).handle_update(params)

    assert _without_seq(_replayed(bus)) == [{"type": "session.update", "params": params}]


def test_reset_capture_starts_a_fresh_agent_text():
    """Each step's outcome is parsed from its own text, not the previous step's."""
    sink = ApiStreamSink(EventBus())
    sink.handle_update(_chunk("old"))

    sink.reset_capture()
    sink.handle_update(_chunk("new"))

    assert sink.agent_text() == "new"


def test_sink_calls_publish_their_events_in_order(monkeypatch: pytest.MonkeyPatch):
    """Replay rebuilds the cockpit from these events, so each carries its fields."""
    monkeypatch.setattr(adapters_module.time, "time", lambda: 1234.5)
    bus = EventBus()
    sink = ApiStreamSink(bus)

    sink.begin_phase("Plan")
    sink.info("note")
    sink.error("Build", "exit 2")
    sink.error("Lint")
    sink.set_session_id("sess-1")
    sink.set_context(cwd="/w", branch="pulse/run")
    sink.begin_user_wait()
    sink.end_user_wait()
    sink.finish_question_prompt()
    sink.finish()

    assert _without_seq(_replayed(bus)) == [
        {"type": "phase.begin", "title": "Plan"},
        {"type": "phase.info", "title": "note"},
        {"type": "phase.error", "title": "Build", "reason": "exit 2"},
        {"type": "phase.error", "title": "Lint", "reason": ""},
        {"type": "session.id", "session_id": "sess-1"},
        {"type": "run.context", "cwd": "/w", "branch": "pulse/run"},
        {"type": "run.awaiting", "waiting": True, "since": 1234.5},
        {"type": "run.awaiting", "waiting": False},
        {"type": "stream.finish_question"},
        {"type": "stream.finish"},
    ]


def test_a_create_plan_answer_object_is_passed_through():
    answer = {"outcome": {"outcome": "selected", "optionId": "approve"}}
    correlator = _AnsweringCorrelator(answer)

    result = ApiPromptPort(correlator).respond_to_create_plan({"plan": "x"})

    assert result == answer
    assert correlator.asked == [("create_plan", {"plan": "x"})]


def test_a_missing_create_plan_answer_cancels():
    port = ApiPromptPort(_AnsweringCorrelator(None))

    assert port.respond_to_create_plan({}) == {"outcome": {"outcome": "cancelled"}}


def test_a_permission_the_policy_resolves_never_reaches_a_person():
    """Policy is not a question: a run with no cockpit must not block on it."""
    correlator = _AnsweringCorrelator(None)
    params = {
        "toolCall": {"kind": "read"},
        "options": [{"optionId": "yes", "kind": "allow_once"}],
    }

    answer = ApiPromptPort(correlator).respond_to_permission(params, policy="auto_approve")

    assert answer == {"outcome": {"outcome": "selected", "optionId": "yes"}}
    assert correlator.asked == []


def test_a_permission_under_ask_carries_policy_and_terminal_flag_to_the_client():
    correlator = _AnsweringCorrelator({"outcome": {"outcome": "selected", "optionId": "yes"}})
    params = {"toolCall": {"kind": "edit"}, "options": []}

    ApiPromptPort(correlator).respond_to_permission(params, policy="ask", allow_terminal=True)

    assert correlator.asked == [
        ("permission", {"params": params, "policy": "ask", "allow_terminal": True})
    ]


def test_a_text_questionnaire_is_sent_with_its_parsed_questions():
    questionnaire = parse_text_questionnaire(QUESTIONNAIRE_TEXT)
    assert questionnaire is not None
    correlator = _AnsweringCorrelator("1: A")

    answer = ApiPromptPort(correlator).run_parsed_questionnaire(questionnaire)

    kind, payload = correlator.asked[0]
    assert answer == "1: A"
    assert kind == "questionnaire"
    assert payload["raw"] == questionnaire.raw
    assert [option["label"] for option in payload["questions"][0]["options"]] == [
        "SQLite",
        "Postgres",
    ]


@dataclass(frozen=True)
class _OtherQuestionnaire:
    title: str
    raw: str


def test_a_questionnaire_of_another_shape_is_sent_as_title_and_raw():
    correlator = _AnsweringCorrelator(7)

    answer = ApiPromptPort(correlator).run_parsed_questionnaire(_OtherQuestionnaire("T", "raw"))

    assert answer == "7"
    assert correlator.asked == [("questionnaire", {"title": "T", "raw": "raw"})]


def test_an_unanswered_questionnaire_is_no_answer():
    questionnaire = _OtherQuestionnaire("T", "raw")

    assert ApiPromptPort(_AnsweringCorrelator(None)).run_parsed_questionnaire(questionnaire) is None


def test_text_without_a_questionnaire_asks_nobody():
    """Only the fenced block Pulse defined is a question; plain agent text is not."""
    correlator = _AnsweringCorrelator("A")

    assert ApiPromptPort(correlator).run_text_questionnaire("Just a status update.") is None
    assert correlator.asked == []


def test_text_with_a_questionnaire_is_asked():
    correlator = _AnsweringCorrelator("1: B")

    assert ApiPromptPort(correlator).run_text_questionnaire(QUESTIONNAIRE_TEXT) == "1: B"
    assert [kind for kind, _ in correlator.asked] == ["questionnaire"]


@pytest.mark.parametrize(("answer", "expected"), [("  ship it  ", "ship it"), ("   ", None)])
def test_a_text_answer_is_trimmed_and_blank_means_none(answer: object, expected: str | None):
    """A blank reply must not become an empty prompt for the next agent turn."""
    correlator = _AnsweringCorrelator(answer)

    assert ApiPromptPort(correlator).ask_text("Why?", title="Reason") == expected
    assert correlator.asked == [("text", {"prompt": "Why?", "title": "Reason"})]


def test_an_unanswered_text_prompt_is_none():
    assert ApiPromptPort(_AnsweringCorrelator(None)).ask_text("Why?") is None
