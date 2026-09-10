from __future__ import annotations

from pulse.tui.state import CockpitState, LogKind
from pulse.tui.widgets.log_stream import LogStream, _assistant_line, format_assistant_lines


def test_format_assistant_lines_wraps_and_keeps_paragraphs():
    body = (
        "Vou seguir o workflow Specify do `tlc-spec-driven`: ler as referencias "
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
    state.configure_workflow("setup-project")
    state.begin_phase("Fase 1 — Análise do projeto")
    state.add_qa("1. O que você está construindo?", "A) Produto / plataforma")
    stream = LogStream(state)
    plain = stream._render_entries(state).plain
    assert "Pergunta" in plain
    assert "O que você está construindo?" in plain
    assert "Você" in plain
    assert "Produto / plataforma" in plain
