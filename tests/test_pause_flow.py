from __future__ import annotations

import threading
import time

from pulse.plan.new_issue_flow import _hold_for_pause
from pulse.plan.workflow_state import PhaseStatus, WorkflowState
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.tui.state import CockpitState


class _FakeStream:
    """Só o que as barreiras usam do stream."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.synced: list[dict] = []

    def info(self, title: str) -> None:
        self.messages.append(title)

    def apply_phase_statuses(self, **kwargs) -> None:
        self.synced.append(kwargs)


class _FakeRunner:
    def __init__(self, control: RunControl) -> None:
        self.control = control
        self._stream = _FakeStream()


def _state(tmp_path) -> WorkflowState:
    state = WorkflowState(feature_slug="minha-feature", user_prompt="fazer algo")
    state.mark_phase_in_progress("prd")
    return state


def test_pausa_devolve_o_step_cortado_para_pendente(tmp_path):
    """O step interrompido não terminou: tem de voltar a pendente e ser refeito."""
    control = RunControl()
    control.pause()
    runner = _FakeRunner(control)
    state = _state(tmp_path)
    assert state.phases["prd"].status == PhaseStatus.IN_PROGRESS

    released: list[bool] = []
    thread = threading.Thread(
        target=lambda: released.append(
            _hold_for_pause(
                runner,
                workspace=tmp_path,
                state=state,
                phase="prd",
                label="fase PRD",
            )
        )
    )
    thread.start()
    time.sleep(0.15)

    assert state.phases["prd"].status == PhaseStatus.PENDING
    assert released == [], "a barreira segura enquanto pausado"

    control.resume()
    thread.join(timeout=2)
    assert released == [True], "ao retomar, o step é refeito do começo"

    # E o que voltou para pendente foi gravado, para sobreviver a um stop depois.
    reloaded = WorkflowState.load(tmp_path / state.workflow_path)
    assert reloaded.phases["prd"].status == PhaseStatus.PENDING


def test_parar_na_barreira_encerra_a_run(tmp_path):
    control = RunControl()
    control.stop()
    runner = _FakeRunner(control)
    state = _state(tmp_path)

    assert (
        _hold_for_pause(
            runner,
            workspace=tmp_path,
            state=state,
            phase="prd",
            label="fase PRD",
        )
        is False
    )
    assert state.phases["prd"].status == PhaseStatus.PENDING


def test_barreira_de_task_nao_mexe_nas_fases(tmp_path):
    """Task cortada já fica pendente sozinha — a fase Execute continua em curso."""
    control = RunControl()
    control.pause()
    runner = _FakeRunner(control)
    state = WorkflowState(feature_slug="f", user_prompt="p")
    state.mark_phase_in_progress("execute")

    threading.Thread(target=control.resume).start()
    assert _hold_for_pause(runner, workspace=tmp_path, state=state, label="Task T2") is True
    assert state.phases["execute"].status == PhaseStatus.IN_PROGRESS


def test_cockpit_congela_o_relogio_ao_pausar():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase PRD")
    running = state.phases[0]
    assert running.status.value == "running"
    assert running.elapsed_label() != ""

    state.mark_paused()

    assert state.paused is True
    assert running.status.value == "pending"
    assert running.elapsed_label() == "", "sem step em curso, o relógio para"


def test_parar_nao_marca_falha_na_sidebar():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase PRD")

    state.mark_finished(RUN_STOPPED)

    assert state.running is False
    assert state.stopped is True
    assert [phase.status.value for phase in state.phases] == ["pending"] * len(state.phases)


def test_falha_de_verdade_continua_marcando_falha():
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Fase PRD")

    state.mark_finished(1)

    assert state.phases[0].status.value == "failed"
    assert state.stopped is False


def test_quick_nao_oferece_pausa_mas_oferece_parada():
    state = CockpitState()
    state.configure_workflow("spec")
    assert state.can_pause is True

    state.apply_routed_flow("quick")

    assert state.can_pause is False, "quick roda num fôlego só: não há onde segurar"
    assert state.can_stop is True
