from __future__ import annotations

import threading
import time

from tests.conftest import make_workflow

from pulse.orchestrator.engine import _hold_for_pause
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.store import runs as run_store
from pulse.store.runs import PENDING, RUNNING, StepRecord
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


def _run(tmp_path) -> tuple[run_store.RunRecord, StepRecord]:
    record = run_store.create_run(
        run_id="run-1",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="fazer algo",
        steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
    )
    step = record.steps[0]
    step.status = RUNNING
    run_store.save_step(record.id, step)
    return record, step


def test_pausa_devolve_o_step_cortado_para_pendente(tmp_path):
    """O step interrompido não terminou: tem de voltar a pendente e ser refeito."""
    control = RunControl()
    control.pause()
    runner = _FakeRunner(control)
    record, step = _run(tmp_path)

    released: list[bool] = []
    thread = threading.Thread(
        target=lambda: released.append(
            _hold_for_pause(runner, run=record, record=step, label="Um")
        )
    )
    thread.start()
    time.sleep(0.15)

    assert step.status == PENDING
    assert released == [], "a barreira segura enquanto pausado"

    control.resume()
    thread.join(timeout=2)
    assert released == [True], "ao retomar, o step é refeito do começo"

    # E o que voltou para pendente foi gravado, para sobreviver a um stop depois.
    reloaded = run_store.load_run(record.id)
    assert reloaded.step("one").status == PENDING


def test_parar_na_barreira_encerra_a_run(tmp_path):
    control = RunControl()
    control.stop()
    runner = _FakeRunner(control)
    record, step = _run(tmp_path)

    assert _hold_for_pause(runner, run=record, record=step, label="Um") is False
    assert step.status == PENDING


def test_cockpit_congela_o_relogio_ao_pausar():
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.begin_phase("Um")
    running = state.phases[0]
    assert running.status.value == "running"
    assert running.elapsed_label() != ""

    state.mark_paused()

    assert state.paused is True
    assert running.status.value == "pending"
    assert running.elapsed_label() == "", "sem step em curso, o relógio para"


def test_parar_nao_marca_falha_na_sidebar():
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.begin_phase("Um")

    state.mark_finished(RUN_STOPPED)

    assert state.running is False
    assert state.stopped is True
    assert [phase.status.value for phase in state.phases] == ["pending"] * len(state.phases)


def test_falha_de_verdade_continua_marcando_falha():
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.begin_phase("Um")

    state.mark_finished(1)

    assert state.phases[0].status.value == "failed"
    assert state.stopped is False


def test_todo_workflow_pode_pausar_e_parar():
    """A sessão ACP é isolada por step: sempre há barreira onde segurar."""
    make_workflow("qualquer", steps=[("only", "Único")])
    state = CockpitState()
    state.configure_workflow("qualquer")

    assert state.can_pause is True
    assert state.can_stop is True
