"""`ConsoleStreamSink`: what a plain terminal shows of a run, from the engine's own calls."""

from __future__ import annotations

from pulse.cli.console_sink import ConsoleStreamSink
from pulse.domain.ports import StreamSink


def _sink() -> tuple[ConsoleStreamSink, list[str]]:
    lines: list[str] = []
    return ConsoleStreamSink("Demo", write=lines.append), lines


def test_the_console_is_a_stream_sink():
    sink, _lines = _sink()

    assert isinstance(sink, StreamSink)


def test_the_context_prints_the_banner_with_the_branch():
    sink, lines = _sink()

    sink.set_context(cwd="/repo/.wt", branch="pulse/demo-1")

    assert lines == ["", "=== Demo ===", "Workspace: /repo/.wt", "Branch: pulse/demo-1", ""]


def test_a_detached_head_prints_no_branch_line():
    sink, lines = _sink()

    sink.set_context(cwd="/repo", branch="")

    assert "Branch: " not in "\n".join(lines)


def test_each_step_is_reported_once_when_it_settles():
    """The engine resends the whole list on every change; repeating lines would bury the log."""
    sink, lines = _sink()
    steps = [{"id": "one", "label": "Um", "rounds": 1}, {"id": "two", "label": "Dois", "rounds": 1}]

    sink.apply_phase_statuses(steps=steps, done_ids=["one"])
    sink.apply_phase_statuses(steps=steps, done_ids=["one"], skipped_ids=["two"])

    assert lines == ["✓ Um", "⏭  Dois skipped"]


def test_failed_and_blocked_steps_print_nothing_on_their_own():
    """Their reason arrives as a notice; a bare status line would say less than it."""
    sink, lines = _sink()

    sink.apply_phase_statuses(
        steps=[{"id": "one", "label": "Um", "rounds": 1}],
        failed_ids=["one"],
        blocked_ids=["one"],
    )

    assert lines == []


def test_notices_and_errors_are_tagged():
    sink, lines = _sink()

    sink.info("Refazendo Um")
    sink.error("Step Um falhou", "a sessão caiu")
    sink.error("Sem motivo")

    assert lines == [
        "[pulse] Refazendo Um",
        "[pulse] Step Um falhou: a sessão caiu",
        "[pulse] Sem motivo",
    ]


def test_agent_text_is_captured_for_the_engine_but_not_echoed():
    sink, lines = _sink()

    chunk = {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "oi"}}

    sink.handle_update({"update": chunk})

    assert sink.agent_text() == "oi"
    assert lines == []
