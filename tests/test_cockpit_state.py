from __future__ import annotations

from pulse.tui.state import CockpitState, LogKind, PhaseStatus, progress_bar


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
        PhaseStatus.PENDING,
        PhaseStatus.PENDING,
        PhaseStatus.PENDING,
        PhaseStatus.RUNNING,
    ]
    assert state.done_count() == 0


def test_begin_phase_preserves_timer_across_same_phase_tasks():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Specify")
    specify_started = state.phases[0].started_at
    assert specify_started is not None

    state.begin_phase("Fase Specify — continuação (2)")
    assert state.phases[0].status == PhaseStatus.RUNNING
    assert state.phases[0].started_at == specify_started

    state.begin_phase("Execute — Task T1: One")
    execute_started = state.phases[3].started_at
    assert execute_started is not None
    assert execute_started != specify_started
    assert state.phases[0].status == PhaseStatus.DONE

    state.begin_phase("Execute — Task T2: Two")
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


def test_add_error_keeps_title_and_reason():
    state = CockpitState()
    state.configure_workflow("spec")
    state.add_error("Classificação cancelada", "O agente não definiu o flow (quick ou full).")
    assert state.has_error() is True
    entry = state.entries[-1]
    assert entry.kind == LogKind.ERROR
    assert entry.title == "Classificação cancelada"
    assert "flow" in entry.detail


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


def test_mark_finished_on_error_marks_failed():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Specify")
    state.mark_finished(1)
    assert state.running is False
    assert state.exit_code == 1
    assert state.phases[0].status == PhaseStatus.FAILED
    assert state.phases[1].status == PhaseStatus.PENDING
    assert state.done_count() == 0


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


def test_upsert_artifact_keeps_collection_and_follow_live():
    state = CockpitState()
    state.configure_workflow("setup-project")
    state.begin_phase("Fase 2 — Gerando specs")
    first = state.upsert_artifact(".pulse/specs/project/PROJECT.md", ready=False)
    second = state.upsert_artifact("/repo/.pulse/specs/project/ROADMAP.md", ready=True, has_content=True)
    third = state.upsert_artifact(".pulse/specs/project/STATE.md", ready=True, has_content=True)
    assert first is not None and second is not None and third is not None
    assert [item.path for item in state.artifacts] == [
        ".pulse/specs/project/PROJECT.md",
        ".pulse/specs/project/ROADMAP.md",
        ".pulse/specs/project/STATE.md",
    ]
    assert state.selected_artifact_path == ".pulse/specs/project/STATE.md"
    assert state.follow_artifact is True
    assert state.artifact_pane_open is False  # a aba só abre a pedido

    again = state.upsert_artifact(".pulse/specs/project/PROJECT.md", ready=True, has_content=True)
    assert again is first
    assert len(state.artifacts) == 3
    assert state.selected_artifact_path == ".pulse/specs/project/PROJECT.md"


def test_manual_artifact_select_disables_follow():
    state = CockpitState()
    state.configure_workflow("setup-project")
    state.begin_phase("Fase 2 — Gerando specs")
    state.upsert_artifact(".pulse/specs/project/PROJECT.md", ready=True, has_content=True)
    state.upsert_artifact(".pulse/specs/project/ROADMAP.md", ready=True, has_content=True)
    state.select_artifact(".pulse/specs/project/PROJECT.md")
    assert state.follow_artifact is False
    assert state.selected_artifact_path == ".pulse/specs/project/PROJECT.md"
    state.upsert_artifact(".pulse/specs/project/STATE.md", ready=True, has_content=True)
    assert state.selected_artifact_path == ".pulse/specs/project/PROJECT.md"
    state.move_artifact(1)
    assert state.selected_artifact_path == ".pulse/specs/project/ROADMAP.md"


def test_visible_artifacts_are_scoped_to_selected_phase():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Specify")
    state.upsert_artifact(".pulse/specs/features/demo/spec.md", ready=True, has_content=True)
    state.begin_phase("Fase Design")
    state.upsert_artifact(".pulse/specs/features/demo/design.md", ready=True, has_content=True)
    assert [item.path for item in state.visible_artifacts()] == [
        ".pulse/specs/features/demo/design.md"
    ]
    state.select_phase(0)
    assert [item.path for item in state.visible_artifacts()] == [
        ".pulse/specs/features/demo/spec.md"
    ]


def test_upsert_ignores_non_spec_paths():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Specify")
    assert state.upsert_artifact("pulse/cli.py", ready=True, has_content=True) is None
    assert state.upsert_artifact(".pulse/skills/pulse-spec-driven/SKILL.md", ready=True, has_content=True) is None
    assert state.artifacts == []
    assert state.artifact_pane_open is False


def test_reveal_artifact_from_prompt_opens_matching_file():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Specify")
    state.upsert_artifact(".pulse/specs/features/demo/spec.md", ready=True, has_content=True)
    state.upsert_artifact(".pulse/specs/features/demo/context.md", ready=True, has_content=True)
    assert state.artifact_pane_open is False
    opened = state.reveal_artifact_from_prompt(
        "Aprovar Specify (.pulse/specs/features/demo/spec.md) e avançar?"
    )
    assert opened is True
    assert state.artifact_pane_open is True
    assert state.selected_artifact_path == ".pulse/specs/features/demo/spec.md"
    assert state.follow_artifact is False


def test_toggle_focus_cycles_artifact_when_pane_open():
    state = CockpitState()
    state.configure_workflow("fix-bug")
    assert state.focus_target == "phases"
    state.toggle_focus()
    assert state.focus_target == "stream"
    state.toggle_focus()
    assert state.focus_target == "phases"
    state.begin_phase("Planejar")
    state.upsert_artifact(".pulse/specs/quick/001-x/TASK.md", ready=True, has_content=True)
    state.open_artifact_pane()
    state.focus_target = "phases"
    state.toggle_focus()
    assert state.focus_target == "stream"
    state.toggle_focus()
    assert state.focus_target == "artifact"
    state.toggle_focus()
    assert state.focus_target == "phases"
    state.toggle_artifact_pane()
    assert state.artifact_pane_open is False
    state.focus_target = "artifact"
    state.toggle_focus()
    assert state.focus_target == "stream"


def test_close_artifact_pane_hides_and_moves_focus():
    state = CockpitState()
    state.configure_workflow("setup-project")
    state.begin_phase("Fase 2 — Gerando specs")
    state.upsert_artifact(".pulse/specs/project/PROJECT.md", ready=True, has_content=True)
    state.open_artifact_pane()
    state.focus_target = "artifact"
    assert state.artifact_pane_open is True
    state.close_artifact_pane()
    assert state.artifact_pane_open is False
    assert state.focus_target == "stream"
    state.close_artifact_pane()
    assert state.artifact_pane_open is False


def test_open_artifact_pane_shows_again():
    state = CockpitState()
    state.configure_workflow("setup-project")
    state.begin_phase("Fase 2 — Gerando specs")
    state.upsert_artifact(".pulse/specs/project/PROJECT.md", ready=True, has_content=True)
    state.close_artifact_pane()
    assert state.artifact_pane_open is False
    state.open_artifact_pane()
    assert state.artifact_pane_open is True
    state.open_artifact_pane()
    assert state.artifact_pane_open is True


def test_phase_has_artifacts_follows_selected_phase():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Specify")
    state.upsert_artifact(".pulse/specs/features/demo/spec.md", ready=True, has_content=True)
    assert state.phase_has_artifacts() is True
    state.begin_phase("Fase Design")
    assert state.phase_has_artifacts() is False
    state.select_phase(0)
    assert state.phase_has_artifacts() is True


def test_tasks_are_navigable_and_scope_logs():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.set_tasks([("T1", "One", "pending"), ("T2", "Two", "pending")])
    assert state.task_total_count() == 2
    assert state.task_done_count() == 0
    assert progress_bar(0, 2, width=4) == "...."

    state.begin_phase("Execute — Task T1: One")
    state.begin_task("T1", "One")
    state.append_assistant("trabalho t1")
    assert state.selected_nav_kind == "task"
    assert state.selected_task().id == "T1"
    assert [entry.body for entry in state.visible_entries() if entry.kind == LogKind.ASSISTANT] == [
        "trabalho t1"
    ]

    state.begin_phase("Execute — Task T2: Two")
    state.begin_task("T2", "Two")
    state.append_assistant("trabalho t2")
    assert state.selected_task().id == "T2"
    assert "trabalho t1" not in [entry.body for entry in state.visible_entries()]

    state.select_task(0)
    assert state.selected_nav_kind == "task"
    visible = state.visible_entries()
    assert {entry.task_id for entry in visible} == {"T1"}
    assert visible[-1].body == "trabalho t1"

    state.begin_phase("Execute — Task T2: Two")
    state.begin_task("T2", "Two")
    assert state.selected_task_index == 0
    assert state.tasks[1].status == PhaseStatus.RUNNING

    state.select_task(1)
    state.move_nav(-1)
    assert state.selected_nav_kind == "task"
    assert state.selected_task_index == 0
    state.move_nav(-1)
    assert state.selected_nav_kind == "phase"
    assert state.selected_phase().id == "execute"


def test_live_task_does_not_steal_browsed_step():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.set_tasks([("T1", "One", "pending"), ("T2", "Two", "pending")])
    state.begin_phase("Execute — Task T1: One")
    state.begin_task("T1", "One")
    state.select_phase(0)
    assert state.selected_phase().id == "specify"
    state.append_assistant("ainda no t1")
    state.begin_phase("Execute — Task T2: Two")
    state.begin_task("T2", "Two")
    assert state.selected_nav_kind == "phase"
    assert state.selected_phase().id == "specify"
    assert state.tasks[1].status == PhaseStatus.RUNNING


def test_nav_items_nest_tasks_under_execute():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.set_tasks([("T1", "One", "pending"), ("T2", "Two", "pending")])
    assert state.nav_items() == [
        ("phase", 0),
        ("phase", 1),
        ("phase", 2),
        ("phase", 3),
        ("task", 0),
        ("task", 1),
    ]


def test_sink_begin_phase_binds_task_from_label():
    from pulse.tui.adapters.cockpit_sink import CockpitSink

    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state)
    sink.set_tasks([("T1", "One", "pending"), ("T2", "Two", "pending")])
    sink.begin_phase("Execute — Task T1: One")
    assert state.tasks[0].status == PhaseStatus.RUNNING
    assert state.entries[-1].task_id == "T1"
    sink.begin_phase("Execute — Task T2: Two")
    assert state.tasks[0].status == PhaseStatus.DONE
    assert state.tasks[1].status == PhaseStatus.RUNNING
    assert state.entries[-1].task_id == "T2"


def test_configure_spec_starts_with_classify():
    state = CockpitState()
    state.configure_workflow("spec")
    assert [phase.id for phase in state.phases] == ["classify"]
    assert state.workflow_label == "SPEC"


def test_apply_routed_flow_keeps_logs_and_appends_phases():
    state = CockpitState()
    state.configure_workflow("spec")
    state.begin_phase("Classificar spec")
    state.append_assistant("Escopo pequeno")
    state.apply_routed_flow("quick")
    assert [phase.id for phase in state.phases] == ["classify", "plan", "implement"]
    assert state.phases[0].status == PhaseStatus.DONE
    assert state.phases[1].status == PhaseStatus.PENDING
    assert any(entry.body == "Escopo pequeno" for entry in state.entries)
    state.begin_phase("Fase 1 — Planejando quick task")
    assert state.phases[1].status == PhaseStatus.RUNNING


def test_apply_routed_flow_full_appends_pipeline():
    state = CockpitState()
    state.configure_workflow("spec")
    state.apply_routed_flow("full")
    assert [phase.id for phase in state.phases] == [
        "classify",
        "specify",
        "design",
        "tasks",
        "execute",
    ]
    assert state.phases[0].status == PhaseStatus.DONE


def test_pane_stays_closed_while_artifact_has_no_content():
    """Write anunciado mas ainda sem arquivo em disco não deve abrir a aba."""
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Design")
    state.upsert_artifact(".pulse/specs/features/demo/design.md", ready=False)

    assert state.artifact_pane_open is False
    assert state.phase_has_artifacts() is False
    assert state.displayable_artifacts() == []
    # o artefato existe na coleção — a aba, se aberta à mão, mostra "escrevendo…"
    assert [item.path for item in state.visible_artifacts()] == [
        ".pulse/specs/features/demo/design.md"
    ]


def test_artifact_with_content_is_offered_but_never_opens_alone():
    """Abrir sozinho roubava a tela do stream no meio da spec."""
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Design")
    path = ".pulse/specs/features/demo/design.md"
    state.upsert_artifact(path, ready=False)
    assert state.artifact_pane_open is False

    state.upsert_artifact(path, ready=True, has_content=True)

    assert state.artifact_pane_open is False
    assert state.phase_has_artifacts() is True  # o trilho "ABRIR" aparece

    state.open_artifact_pane()
    assert state.artifact_pane_open is True


def test_write_that_never_lands_never_opens_the_pane():
    """Escrita negada/falha conclui sem arquivo: nada a exibir, nada a abrir."""
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Design")
    path = ".pulse/specs/features/demo/design.md"
    state.upsert_artifact(path, ready=False)
    state.upsert_artifact(path, ready=True)  # concluiu, mas sem conteúdo

    assert state.artifact_pane_open is False
    assert state.phase_has_artifacts() is False


def test_pane_does_not_reopen_after_the_user_closes_it():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Design")
    state.upsert_artifact(".pulse/specs/features/demo/design.md", ready=True, has_content=True)
    state.open_artifact_pane()
    assert state.artifact_pane_open is True

    state.close_artifact_pane()
    state.upsert_artifact(".pulse/specs/features/demo/tasks.md", ready=True, has_content=True)

    assert state.artifact_pane_open is False
    assert state.phase_has_artifacts() is True


def test_reveal_from_prompt_ignores_artifacts_without_content():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase Specify")
    state.upsert_artifact(".pulse/specs/features/demo/spec.md", ready=False)

    opened = state.reveal_artifact_from_prompt(
        "Aprovar Specify (.pulse/specs/features/demo/spec.md) e avançar?"
    )

    assert opened is False
    assert state.artifact_pane_open is False
