"""The Null adapters are complete implementations of their ports."""

from __future__ import annotations

from pulse.domain.ports import (
    NullPromptPort,
    NullQuestionChannel,
    NullRuntimeDialect,
    NullSessionLog,
    NullStreamSink,
    PromptPort,
    QuestionChannel,
    RuntimeDialect,
    SessionLog,
    StreamSink,
)
from tests.fakes import FakeQuestionChannel, RecordingSessionLog


def test_the_null_adapters_implement_the_ports():
    assert isinstance(NullStreamSink(), StreamSink)
    assert isinstance(NullPromptPort(), PromptPort)
    assert isinstance(NullSessionLog(), SessionLog)
    assert isinstance(NullQuestionChannel(), QuestionChannel)
    assert isinstance(NullRuntimeDialect(), RuntimeDialect)


def test_the_fakes_implement_the_ports_the_runner_takes():
    assert isinstance(RecordingSessionLog(), SessionLog)
    assert isinstance(FakeQuestionChannel(), QuestionChannel)


def test_with_nobody_to_ask_every_menu_answers_nothing():
    """`None` is what makes the engine stop instead of guessing an answer."""
    assert NullPromptPort().select_choice("?", [("Refazer", "retry")], title="t") is None
    assert NullPromptPort().ask_text("?") is None


def test_with_nobody_to_ask_mid_turn_the_agent_gets_no_mcp_server():
    assert NullQuestionChannel().open(NullPromptPort(), lambda: None) == []


def test_plain_acp_skips_authentication_model_and_mode():
    """A runtime with no dialect of its own sends only what ACP itself requires."""
    dialect = NullRuntimeDialect()
    session = {"models": {"availableModels": [{"modelId": "m1"}]}, "modes": {"currentModeId": "x"}}

    assert dialect.auth_method(["cursor_login", "api_key"]) is None
    assert dialect.model_request(session, "m1", session_id="s-1") is None
    assert dialect.resolve_mode(session, execute=True) is None
