"""The Null adapters are complete implementations of their ports."""

from __future__ import annotations

from pulse.domain.ports import NullPromptPort, NullStreamSink, PromptPort, StreamSink


def test_the_null_adapters_implement_the_ports():
    assert isinstance(NullStreamSink(), StreamSink)
    assert isinstance(NullPromptPort(), PromptPort)


def test_with_nobody_to_ask_every_menu_answers_nothing():
    """`None` is what makes the engine stop instead of guessing an answer."""
    assert NullPromptPort().select_choice("?", [("Refazer", "retry")], title="t") is None
    assert NullPromptPort().ask_text("?") is None
