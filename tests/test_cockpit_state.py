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


def test_begin_phase_marks_prior_pending_when_resuming_mid_flow():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Execute")
    assert [phase.status for phase in state.phases] == [
        PhaseStatus.DONE,
        PhaseStatus.DONE,
        PhaseStatus.DONE,
        PhaseStatus.RUNNING,
    ]
    assert state.done_count() == 3


def test_begin_phase_preserves_timer_across_same_phase_waves():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Specify")
    specify_started = state.phases[0].started_at
    assert specify_started is not None

    state.begin_phase("Fase Specify — continuação (2)")
    assert state.phases[0].status == PhaseStatus.RUNNING
    assert state.phases[0].started_at == specify_started

    state.begin_phase("Execute — Wave 1 (sequencial): T1")
    execute_started = state.phases[3].started_at
    assert execute_started is not None
    assert execute_started != specify_started
    assert state.phases[0].status == PhaseStatus.DONE

    state.begin_phase("Execute — Wave 2 (paralela): T2, T3")
    assert state.phases[3].status == PhaseStatus.RUNNING
    assert state.phases[3].started_at == execute_started


def test_apply_phase_statuses_hydrates_resume_state():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.apply_phase_statuses(done_ids=("specify", "tasks"), skipped_ids=("design",))
    assert state.phases[0].status == PhaseStatus.DONE
    assert state.phases[1].status == PhaseStatus.SKIPPED
    assert state.phases[2].status == PhaseStatus.DONE
    assert state.phases[3].status == PhaseStatus.PENDING
    assert state.done_count() == 3


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
    assert state.phases[0].files == 0
    assert state.record_files(["pulse/cli.py"]) is True
    assert state.phases[0].files == 1
    assert state.record_issue("tool-1") is True
    assert state.phases[0].issues == 1
    assert state.done_count() == 0


def test_add_qa_records_question_and_answer():
    state = CockpitState()
    state.configure_workflow("setup-project")
    state.begin_phase("Fase 1 — Análise do projeto")
    state.append_assistant("Vou perguntar")
    state.add_qa("1. O que você está construindo?", "A) Produto / plataforma")
    kinds = [entry.kind for entry in state.visible_entries()]
    assert LogKind.QUESTION in kinds
    assert LogKind.ANSWER in kinds
    question = next(entry for entry in state.entries if entry.kind == LogKind.QUESTION)
    answer = next(entry for entry in state.entries if entry.kind == LogKind.ANSWER)
    assert question.body == "1. O que você está construindo?"
    assert answer.body == "A) Produto / plataforma"
    assert question.phase_id == "phase1"
    assert answer.phase_id == "phase1"


def test_mark_finished():
    state = CockpitState()
    state.configure_workflow("analyze-codebase")
    state.begin_phase("Fase 1 — Explorando")
    state.mark_finished(0)
    assert state.running is False
    assert state.exit_code == 0
    assert state.phases[0].status == PhaseStatus.DONE
    assert state.phases[0].ended_at is not None
    assert state.phases[0].elapsed_label() != ""


def test_entries_are_scoped_to_selected_step():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Specify")
    state.append_assistant("spec draft")
    state.add_tool_entry(LogKind.WRITE, "spec.md", "spec.md")
    assert {entry.phase_id for entry in state.entries} == {"specify"}
    assert [entry.title for entry in state.visible_entries()] == ["Assistant", "spec.md"]

    state.begin_phase("Fase Design")
    state.append_assistant("design draft")
    assert state.selected_phase_index == 1
    assert [entry.body for entry in state.visible_entries() if entry.kind == LogKind.ASSISTANT] == [
        "design draft"
    ]
    assert "spec draft" not in [entry.body for entry in state.visible_entries()]

    state.select_phase(0)
    visible = state.visible_entries()
    assert [entry.phase_id for entry in visible] == ["specify", "specify"]
    assert visible[0].body == "spec draft"
    assert "design draft" not in [entry.body for entry in visible]


def test_browsing_a_past_step_does_not_follow_new_phase():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Specify")
    state.append_assistant("spec")
    state.begin_phase("Fase Design")
    state.select_phase(0)
    assert state.selected_phase_index == 0

    state.begin_phase("Fase Tasks")
    assert state.selected_phase_index == 0
    assert state.phases[2].status == PhaseStatus.RUNNING
    assert [entry.phase_id for entry in state.visible_entries()] == ["specify"]


def test_following_live_stays_on_running_step():
    state = CockpitState()
    state.configure_workflow("fix-bug")
    state.begin_phase("Fase 1 — Planejando quick task")
    state.begin_phase("Fase 2 — Implementando quick task")
    assert state.selected_phase_index == 1
    state.select_phase(1)
    state.append_assistant("implementando")
    assert state.visible_entries()[-1].phase_id == "implement"
