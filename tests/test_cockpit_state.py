from __future__ import annotations

from pulse.tui.state import CockpitState, LogKind, PhaseStatus


def test_configure_workflow_sets_phases():
    state = CockpitState()
    state.configure_workflow("new-issue")
    assert [phase.id for phase in state.phases] == ["specify", "design", "tasks", "execute"]
    assert state.workflow_label == "NEW ISSUE"
    assert state.done_count() == 0
    assert state.total_count() == 4


def test_begin_phase_marks_running_and_completes_previous():
    state = CockpitState()
    state.configure_workflow("fix-bug")
    state.begin_phase("Fase 1 — Planejando quick task")
    assert state.phases[0].status == PhaseStatus.RUNNING
    assert state.phases[0].started_at is not None
    assert state.running is True

    state.begin_phase("Fase 2 — Implementando quick task")
    assert state.phases[0].status == PhaseStatus.DONE
    assert state.phases[1].status == PhaseStatus.RUNNING
    assert state.done_count() == 1


def test_assistant_and_tool_entries():
    state = CockpitState()
    state.configure_workflow("setup-project")
    state.begin_phase("Fase 1 — Análise do projeto")
    state.append_assistant("Hello ")
    state.append_assistant("world")
    assert len(state.entries) == 1
    assert state.entries[0].kind == LogKind.ASSISTANT
    assert state.entries[0].body == "Hello world"

    state.add_tool_entry(LogKind.READ, "Read pulse/cli.py", "pulse/cli.py")
    assert len(state.entries) == 2
    assert state.entries[1].kind == LogKind.READ
    assert state.phases[0].files == 1
    assert state.done_count() == 0


def test_mark_finished():
    state = CockpitState()
    state.configure_workflow("analyze-codebase")
    state.begin_phase("Fase 1 — Explorando")
    state.mark_finished(0)
    assert state.running is False
    assert state.exit_code == 0
    assert state.phases[0].status == PhaseStatus.DONE
