from __future__ import annotations

from pulse.tui.state import CockpitState
from pulse.tui.widgets.log_stream import LogStream, _assistant_line, format_assistant_lines
from tests.conftest import configure_from_db, make_workflow

FOUR = [("one", "Um"), ("two", "Dois"), ("three", "Três"), ("four", "Quatro")]


def test_format_assistant_lines_wraps_and_keeps_paragraphs():
    body = (
        "Vou seguir o step `plan`: ler as referencias "
        "da skill e os artefatos do projeto para capturar o escopo sem implementar.\n\n"
        "**Problema:** a home mostra KPIs hardcoded."
    )
    lines = format_assistant_lines(body, width=48)
    assert lines
    assert all(len(line) <= 48 for line in lines if line)
    assert lines[-1].startswith("**Problema:**") or any("Problema" in line for line in lines)
    assert "" in lines


def test_assistant_line_styles_code_and_bold():
    styled = _assistant_line("Use `path` e **large** agora")
    plain = styled.plain
    assert plain == "Use path e large agora"
    spans = list(styled.spans)
    assert spans


def test_render_qa_entries_in_stream():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    configure_from_db(state, "demo")
    state.begin_phase("Fase 1 — Análise do projeto")
    state.add_qa("1. O que você está construindo?", "A) Produto / plataforma")
    stream = LogStream(state)
    plain = stream._render_entries(state).plain
    assert "Pergunta" in plain
    assert "O que você está construindo?" in plain
    assert "Você" in plain
    assert "Produto / plataforma" in plain


def test_elapsed_label_does_not_show_966_minutes():
    """A spec resumed the next day used to show "966:46" in the time column."""
    from pulse.history.events import format_elapsed

    assert format_elapsed(0) == "00:00"
    assert format_elapsed(46) == "00:46"
    assert format_elapsed(3 * 60 + 38) == "03:38"
    assert format_elapsed(59 * 60 + 59) == "59:59"
    assert format_elapsed(3600) == "1h00"
    assert format_elapsed(966 * 60 + 46) == "16h06"
    assert format_elapsed(50 * 3600) == "2d02"


def test_elapsed_label_only_runs_while_the_step_runs():
    """Only a running step has a ticking clock; the rest stay frozen."""
    import time

    from pulse.history.events import PhaseItem, PhaseStatus

    now = time.monotonic()

    running = PhaseItem(id="prd", label="PRD", status=PhaseStatus.RUNNING, started_at=100.0)
    assert running.elapsed_label(163.0) == "01:03"

    hydrated = PhaseItem(
        id="prd",
        label="PRD",
        status=PhaseStatus.RUNNING,
        started_at=0.0,
        ended_at=150.0,
    )
    assert hydrated.elapsed_label(now) == "02:30"

    for status in (PhaseStatus.DONE, PhaseStatus.SKIPPED, PhaseStatus.FAILED):
        frozen = PhaseItem(id="x", label="x", status=status, started_at=10.0, ended_at=40.0)
        assert frozen.elapsed_label(now) == "00:30"
        assert frozen.elapsed_label(now + 60) == "00:30"

    assert PhaseItem(id="x", label="x").elapsed_label(now) == ""
    stopped = PhaseItem(id="x", label="x", status=PhaseStatus.DONE, started_at=10.0)
    assert stopped.elapsed_label(now) == ""
