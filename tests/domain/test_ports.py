"""The Null adapters are complete implementations of their ports."""

from __future__ import annotations

from pulse.domain.ports import (
    NullPromptPort,
    NullQuestionChannel,
    NullSessionLog,
    NullStreamSink,
    PromptPort,
    QuestionChannel,
    SessionLog,
    StreamSink,
)
from tests.fakes import FakeQuestionChannel, RecordingSessionLog


def test_the_null_adapters_implement_the_ports():
    assert isinstance(NullStreamSink(), StreamSink)
    assert isinstance(NullPromptPort(), PromptPort)
    assert isinstance(NullSessionLog(), SessionLog)
    assert isinstance(NullQuestionChannel(), QuestionChannel)


def test_the_fakes_implement_the_ports_the_runner_takes():
    assert isinstance(RecordingSessionLog(), SessionLog)
    assert isinstance(FakeQuestionChannel(), QuestionChannel)


def test_with_nobody_to_ask_every_menu_answers_nothing():
    """`None` is what makes the engine stop instead of guessing an answer."""
    assert NullPromptPort().select_choice("?", [("Refazer", "retry")], title="t") is None
    assert NullPromptPort().ask_text("?") is None


def test_with_nobody_to_ask_mid_turn_the_agent_gets_no_mcp_server():
    assert NullQuestionChannel().open(NullPromptPort(), lambda: None) == []
