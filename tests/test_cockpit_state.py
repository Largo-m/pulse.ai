from __future__ import annotations

from tests.conftest import make_workflow

from pulse.tui.state import CockpitState, LogKind, PhaseStatus, progress_bar

#: Os testes semeiam o workflow que vão usar: o Pulse não conhece nenhum.
FOUR = [("one", "Um"), ("two", "Dois"), ("three", "Três"), ("four", "Quatro")]
PAIR = [("plan", "Planejar"), ("build", "Construir")]


def _state(workflow_id: str = "demo", steps: list[tuple[str, str]] | None = None) -> CockpitState:
    make_workflow(workflow_id, steps=steps or FOUR, label=workflow_id.upper())
    state = CockpitState()
    state.configure_workflow(workflow_id)
    return state


def test_configure_workflow_sets_phases():
    state = _state()
    assert [phase.id for phase in state.phases] == ["one", "two", "three", "four"]
    assert state.workflow_label == "DEMO"
    assert state.done_count() == 0
    assert state.total_count() == 4


def test_begin_phase_marks_running_and_completes_previous():
    state = _state("pair", PAIR)
    state.begin_phase("Planejar")
    assert state.phases[0].status == PhaseStatus.RUNNING
    assert state.phases[0].started_at is not None
    assert state.running is True

    state.begin_phase("Construir")
    assert state.phases[0].status == PhaseStatus.DONE
    assert state.phases[1].status == PhaseStatus.RUNNING
    assert state.done_count() == 1


def test_begin_phase_marks_prior_pending_when_resuming_mid_flow():
    state = _state()
    state.begin_phase("Quatro")
    assert [phase.status for phase in state.phases] == [
        PhaseStatus.PENDING,
        PhaseStatus.PENDING,
        PhaseStatus.PENDING,
        PhaseStatus.RUNNING,
    ]
    assert state.done_count() == 0


def test_begin_phase_preserves_timer_across_same_phase_tasks():
    state = _state()
    state.begin_phase("Um")
    prd_started = state.phases[0].started_at
    assert prd_started is not None

    state.begin_phase("Um — continuação (2)")
    assert state.phases[0].status == PhaseStatus.RUNNING
    assert state.phases[0].started_at == prd_started

    state.begin_phase("Quatro")
    last_started = state.phases[3].started_at
    assert last_started is not None
    assert last_started != prd_started
    assert state.phases[0].status == PhaseStatus.DONE

    state.begin_phase("Quatro — continuação (2)")
    assert state.phases[3].status == PhaseStatus.RUNNING
    assert state.phases[3].started_at == last_started


def test_a_new_round_of_the_loop_keeps_counting_from_the_previous_one(monkeypatch):
    """O laço devolve `Review` a rodar: o cronômetro soma, não recomeça do zero."""
    clock = iter([100.0, 130.0, 200.0])
    monkeypatch.setattr("pulse.tui.state.time.monotonic", lambda: next(clock))
    state = _state("pair", PAIR)

    state.begin_phase("Planejar")  # 100
    state.begin_phase("Construir")  # 130: Planejar fecha com 30s
    assert state.phases[0].closed_seconds() == 30.0

    state.begin_phase("Planejar")  # 200: segunda volta, parte dos 30s já gastos
    assert state.phases[0].ended_at is None
    # Aos 250: 30s da primeira volta + 50s da segunda.
    assert state.phases[0].elapsed_label(250.0) == "01:20"


def test_apply_phase_statuses_hydrates_resume_state():
    state = _state()
    state.apply_phase_statuses(done_ids=("one", "three"), skipped_ids=("two",))
    assert state.phases[0].status == PhaseStatus.DONE
    assert state.phases[1].status == PhaseStatus.SKIPPED
    assert state.phases[2].status == PhaseStatus.DONE
    assert state.phases[3].status == PhaseStatus.PENDING
    assert state.done_count() == 3


def test_assistant_and_tool_entries():
    state = _state("pair", PAIR)
    state.begin_phase("Planejar")
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
    state = _state("pair", PAIR)
    state.begin_phase("Planejar")
    state.append_assistant("Vou perguntar")
    state.add_qa("1. O que você está construindo?", "A) Produto / plataforma")
    kinds = [entry.kind for entry in state.visible_entries()]
    assert LogKind.QUESTION in kinds
    assert LogKind.ANSWER in kinds
    question = next(entry for entry in state.entries if entry.kind == LogKind.QUESTION)
    answer = next(entry for entry in state.entries if entry.kind == LogKind.ANSWER)
    assert question.body == "1. O que você está construindo?"
    assert answer.body == "A) Produto / plataforma"
    assert question.phase_id == "plan"
    assert answer.phase_id == "plan"


def test_add_error_keeps_title_and_reason():
    state = _state("solo", [("only", "Único")])
    state.add_error("Classificação cancelada", "O agente não definiu o flow (quick ou full).")
    assert state.has_error() is True
    entry = state.entries[-1]
    assert entry.kind == LogKind.ERROR
    assert entry.title == "Classificação cancelada"
    assert "flow" in entry.detail


def test_mark_finished():
    state = _state("pair", PAIR)
    state.begin_phase("Planejar")
    state.mark_finished(0)
    assert state.running is False
    assert state.exit_code == 0
    assert state.phases[0].status == PhaseStatus.DONE
    assert state.phases[0].ended_at is not None
    assert state.phases[0].elapsed_label() != ""


def test_mark_finished_on_error_marks_failed():
    state = _state()
    state.begin_phase("Um")
    state.mark_finished(1)
    assert state.running is False
    assert state.exit_code == 1
    assert state.phases[0].status == PhaseStatus.FAILED
    assert state.phases[1].status == PhaseStatus.PENDING
    assert state.done_count() == 0


def test_entries_are_scoped_to_selected_step():
    state = _state()
    state.begin_phase("Um")
    state.append_assistant("spec draft")
    state.add_tool_entry(LogKind.WRITE, "PRD.md", "PRD.md")
    assert {entry.phase_id for entry in state.entries} == {"one"}
    assert [entry.title for entry in state.visible_entries()] == ["Assistant", "PRD.md"]

    state.begin_phase("Dois")
    state.append_assistant("design draft")
    assert state.selected_phase_index == 1
    assert [entry.body for entry in state.visible_entries() if entry.kind == LogKind.ASSISTANT] == [
        "design draft"
    ]
    assert "spec draft" not in [entry.body for entry in state.visible_entries()]

    state.select_phase(0)
    visible = state.visible_entries()
    assert [entry.phase_id for entry in visible] == ["one", "one"]
    assert visible[0].body == "spec draft"
    assert "design draft" not in [entry.body for entry in visible]


def test_browsing_a_past_step_does_not_follow_new_phase():
    state = _state()
    state.begin_phase("Um")
    state.append_assistant("spec")
    state.begin_phase("Dois")
    state.select_phase(0)
    assert state.selected_phase_index == 0

    state.begin_phase("Três")
    assert state.selected_phase_index == 0
    assert state.phases[2].status == PhaseStatus.RUNNING
    assert [entry.phase_id for entry in state.visible_entries()] == ["one"]


def test_following_live_stays_on_running_step():
    state = _state("pair", PAIR)
    state.begin_phase("Planejar")
    state.begin_phase("Construir")
    assert state.selected_phase_index == 1
    state.select_phase(1)
    state.append_assistant("implementando")
    assert state.visible_entries()[-1].phase_id == "build"


def test_upsert_artifact_keeps_collection_and_follow_live():
    state = _state("pair", PAIR)
    state.begin_phase("Construir")
    first = state.upsert_artifact("docs/PROJECT.md", ready=False)
    second = state.upsert_artifact("docs/ROADMAP.md", ready=True, has_content=True)
    third = state.upsert_artifact("docs/STATE.md", ready=True, has_content=True)
    assert first is not None and second is not None and third is not None
    assert [item.path for item in state.artifacts] == [
        "docs/PROJECT.md",
        "docs/ROADMAP.md",
        "docs/STATE.md",
    ]
    assert state.selected_artifact_path == "docs/STATE.md"
    assert state.follow_artifact is True
    assert state.artifact_pane_open is False  # a aba só abre a pedido

    again = state.upsert_artifact("docs/PROJECT.md", ready=True, has_content=True)
    assert again is first
    assert len(state.artifacts) == 3
    assert state.selected_artifact_path == "docs/PROJECT.md"


def test_manual_artifact_select_disables_follow():
    state = _state("pair", PAIR)
    state.begin_phase("Construir")
    state.upsert_artifact("docs/PROJECT.md", ready=True, has_content=True)
    state.upsert_artifact("docs/ROADMAP.md", ready=True, has_content=True)
    state.select_artifact("docs/PROJECT.md")
    assert state.follow_artifact is False
    assert state.selected_artifact_path == "docs/PROJECT.md"
    state.upsert_artifact("docs/STATE.md", ready=True, has_content=True)
    assert state.selected_artifact_path == "docs/PROJECT.md"
    state.move_artifact(1)
    assert state.selected_artifact_path == "docs/ROADMAP.md"


def test_visible_artifacts_are_scoped_to_selected_phase():
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("docs/PRD.md", ready=True, has_content=True)
    state.begin_phase("Dois")
    state.upsert_artifact("docs/TECHSPEC.md", ready=True, has_content=True)
    assert [item.path for item in state.visible_artifacts()] == [
        "docs/TECHSPEC.md"
    ]
    state.select_phase(0)
    assert [item.path for item in state.visible_artifacts()] == [
        "docs/PRD.md"
    ]


def test_select_artifact_from_prompt_points_at_matching_file_without_opening():
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("docs/PRD.md", ready=True, has_content=True)
    state.upsert_artifact("docs/context.md", ready=True, has_content=True)
    assert state.artifact_pane_open is False
    selected = state.select_artifact_from_prompt(
        "Aprovar PRD (docs/PRD.md) e avançar?"
    )
    assert selected is True
    assert state.selected_artifact_path == "docs/PRD.md"
    assert state.follow_artifact is False
    # A aba fica apontada, mas quem abre é o usuário com `a`.
    assert state.artifact_pane_open is False


def test_prompt_without_artifact_leaves_the_selection_alone():
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("docs/PRD.md", ready=True, has_content=True)

    selected = state.select_artifact_from_prompt("Qual banco usar para a fila?")

    assert selected is False
    assert state.artifact_pane_open is False
    assert state.follow_artifact is True


def test_toggle_focus_cycles_artifact_when_pane_open():
    state = _state("pair", PAIR)
    assert state.focus_target == "phases"
    state.toggle_focus()
    assert state.focus_target == "stream"
    state.toggle_focus()
    assert state.focus_target == "phases"
    state.begin_phase("Planejar")
    state.upsert_artifact("docs/TASK.md", ready=True, has_content=True)
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
    state = _state("pair", PAIR)
    state.begin_phase("Construir")
    state.upsert_artifact("docs/PROJECT.md", ready=True, has_content=True)
    state.open_artifact_pane()
    state.focus_target = "artifact"
    assert state.artifact_pane_open is True
    state.close_artifact_pane()
    assert state.artifact_pane_open is False
    assert state.focus_target == "stream"
    state.close_artifact_pane()
    assert state.artifact_pane_open is False


def test_open_artifact_pane_shows_again():
    state = _state("pair", PAIR)
    state.begin_phase("Construir")
    state.upsert_artifact("docs/PROJECT.md", ready=True, has_content=True)
    state.close_artifact_pane()
    assert state.artifact_pane_open is False
    state.open_artifact_pane()
    assert state.artifact_pane_open is True
    state.open_artifact_pane()
    assert state.artifact_pane_open is True


def test_phase_has_artifacts_follows_selected_phase():
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("docs/PRD.md", ready=True, has_content=True)
    assert state.phase_has_artifacts() is True
    state.begin_phase("Dois")
    assert state.phase_has_artifacts() is False
    state.select_phase(0)
    assert state.phase_has_artifacts() is True


def test_configure_single_step_workflow():
    state = _state("solo", [("only", "Único")])
    assert [phase.id for phase in state.phases] == ["only"]
    assert state.workflow_label == "SOLO"


def test_pane_stays_closed_while_artifact_has_no_content():
    """Write anunciado mas ainda sem arquivo em disco não deve abrir a aba."""
    state = _state()
    state.begin_phase("Dois")
    state.upsert_artifact("docs/TECHSPEC.md", ready=False)

    assert state.artifact_pane_open is False
    assert state.phase_has_artifacts() is False
    assert state.displayable_artifacts() == []
    # o artefato existe na coleção — a aba, se aberta à mão, mostra "escrevendo…"
    assert [item.path for item in state.visible_artifacts()] == [
        "docs/TECHSPEC.md"
    ]


def test_artifact_with_content_is_offered_but_never_opens_alone():
    """Abrir sozinho roubava a tela do stream no meio da spec."""
    state = _state()
    state.begin_phase("Dois")
    path = "docs/TECHSPEC.md"
    state.upsert_artifact(path, ready=False)
    assert state.artifact_pane_open is False

    state.upsert_artifact(path, ready=True, has_content=True)

    assert state.artifact_pane_open is False
    assert state.phase_has_artifacts() is True  # o trilho "ABRIR" aparece

    state.open_artifact_pane()
    assert state.artifact_pane_open is True


def test_write_that_never_lands_never_opens_the_pane():
    """Escrita negada/falha conclui sem arquivo: nada a exibir, nada a abrir."""
    state = _state()
    state.begin_phase("Dois")
    path = "docs/TECHSPEC.md"
    state.upsert_artifact(path, ready=False)
    state.upsert_artifact(path, ready=True)  # concluiu, mas sem conteúdo

    assert state.artifact_pane_open is False
    assert state.phase_has_artifacts() is False


def test_pane_does_not_reopen_after_the_user_closes_it():
    state = _state()
    state.begin_phase("Dois")
    state.upsert_artifact("docs/TECHSPEC.md", ready=True, has_content=True)
    state.open_artifact_pane()
    assert state.artifact_pane_open is True

    state.close_artifact_pane()
    state.upsert_artifact("docs/tasks.md", ready=True, has_content=True)

    assert state.artifact_pane_open is False
    assert state.phase_has_artifacts() is True


def test_select_from_prompt_ignores_artifacts_without_content():
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("docs/PRD.md", ready=False)

    selected = state.select_artifact_from_prompt(
        "Aprovar PRD (docs/PRD.md) e avançar?"
    )

    assert selected is False
    assert state.artifact_pane_open is False


def test_fan_out_replaces_one_phase_with_the_items():
    """O painel montou as fases pela definição; o fan-out muda isso na run."""
    make_workflow("demo", steps=[("plan", "Planejar"), ("run", "Implementar")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.apply_phase_statuses(
        steps=[{"id": "plan", "label": "Planejar"}],
        done_ids=["plan"],
    )

    state.apply_phase_statuses(
        steps=[
            {"id": "plan", "label": "Planejar"},
            {"id": "run:T1", "label": "Criar o endpoint"},
            {"id": "run:T2", "label": "Montar o CSV"},
        ],
        done_ids=["plan"],
    )

    assert [phase.id for phase in state.phases] == ["plan", "run:T1", "run:T2"]
    assert [phase.label for phase in state.phases] == [
        "Planejar",
        "Criar o endpoint",
        "Montar o CSV",
    ]
    # O step que já fechou não volta para pendente ao entrar a lista nova.
    assert state.phases[0].status == PhaseStatus.DONE
    assert state.total_count() == 3
    assert state.done_count() == 1


def test_the_fan_out_items_stay_grouped_under_the_step_that_made_them():
    """`Implementar` não some da sidebar: as tasks entram embaixo dele."""
    make_workflow("demo", steps=[("plan", "Planejar"), ("run", "Implementar")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.apply_phase_statuses(
        steps=[
            {"id": "plan", "label": "Planejar"},
            {"id": "run:T1", "label": "Criar o endpoint"},
            {"id": "run:T2", "label": "Montar o CSV"},
        ],
    )

    groups = state.phase_groups()

    assert [key for key, _members in groups] == ["", "run"]
    assert [phase.id for _index, phase in groups[1][1]] == ["run:T1", "run:T2"]
    assert state.base_step_label("run") == "Implementar"
    # Agrupar é desenho: a navegação continua plana, sobre `phases`.
    assert state.nav_items() == [("phase", 0), ("phase", 1), ("phase", 2)]


def test_syncing_the_list_keeps_what_a_phase_already_gathered():
    """Recriar a fase apagaria status, relógio e contadores de quem já rodou."""
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.begin_phase("Um")
    running = state.phases[0]
    running.files = 3

    state.sync_phases([{"id": "one", "label": "Um"}, {"id": "two", "label": "Dois"}])

    assert state.phases[0] is running
    assert state.phases[0].files == 3
    assert state.phases[0].status == PhaseStatus.RUNNING


def test_an_empty_list_leaves_the_phases_alone():
    """Sink antigo (sem `steps`) não pode zerar o painel."""
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    state = CockpitState()
    state.configure_workflow("demo")

    state.apply_phase_statuses(done_ids=["one"])

    assert [phase.id for phase in state.phases] == ["one", "two"]


def test_a_task_whose_title_contains_an_earlier_step_id_lights_itself():
    """`(TaskSearch)` tem `tasks` dentro: casar por trecho acendia o step errado."""
    state = _state("chain", [("tasks", "Tasks"), ("implement", "Implementar")])
    state.apply_phase_statuses(
        steps=[
            {"id": "tasks", "label": "Tasks"},
            {"id": "implement:T1", "label": "Regra de destaque (TaskSearch)"},
            {"id": "implement:T2", "label": "Negrito no título (TaskRow)"},
        ],
        done_ids=["tasks"],
    )

    state.begin_phase("Regra de destaque (TaskSearch)")
    state.add_info("Regra de destaque (TaskSearch)")

    assert [phase.status for phase in state.phases] == [
        PhaseStatus.DONE,
        PhaseStatus.RUNNING,
        PhaseStatus.PENDING,
    ]
    assert state.selected_phase().id == "implement:T1"
    assert [entry.phase_id for entry in state.visible_entries()] == ["implement:T1"]

    state.begin_phase("Regra de destaque (TaskSearch) — continuação (2)")
    assert state.phases[1].status == PhaseStatus.RUNNING
    assert state.phases[0].status == PhaseStatus.DONE
