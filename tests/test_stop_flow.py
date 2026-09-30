from __future__ import annotations

from tests.conftest import make_workflow

from pulse.orchestrator.engine import _release_step
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.store import runs as run_store
from pulse.store.runs import PENDING, RUNNING, StepRecord
from pulse.tui.state import CockpitState


class _FakeStream:
    """Só o que o corte da run usa do stream."""

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


def test_parar_devolve_o_step_cortado_para_pendente(tmp_path):
    """O step interrompido não terminou nem falhou: volta a pendente."""
    control = RunControl()
    control.stop()
    runner = _FakeRunner(control)
    record, step = _run(tmp_path)

    _release_step(runner, run=record, record=step, label="Um")

    assert step.status == PENDING
    # E foi gravado: é isso que faz `resume_run_id` recomeçar por este step.
    reloaded = run_store.load_run(record.id)
    assert reloaded.step("one").status == PENDING
    assert runner._stream.messages == ["Run parada em Um"]


def test_step_ja_fechado_nao_e_reaberto_pela_parada(tmp_path):
    control = RunControl()
    control.stop()
    runner = _FakeRunner(control)
    record, step = _run(tmp_path)
    step.status = "done"
    run_store.save_step(record.id, step)

    _release_step(runner, run=record, record=step, label="Um")

    assert step.status == "done", "o que já fechou não volta para pendente"


def test_parar_nao_marca_falha_na_sidebar():
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.begin_phase("Um")
    running = state.phases[0]
    assert running.status.value == "running"
    assert running.elapsed_label() != ""

    state.mark_finished(RUN_STOPPED)

    assert state.running is False
    assert state.stopped is True
    assert [phase.status.value for phase in state.phases] == ["pending"] * len(state.phases)
    assert running.elapsed_label() == "", "sem step em curso, o relógio para"


def test_falha_de_verdade_continua_marcando_falha():
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.begin_phase("Um")

    state.mark_finished(1)

    assert state.phases[0].status.value == "failed"
    assert state.stopped is False


def test_todo_workflow_pode_parar():
    """A sessão ACP é isolada por step: sempre há onde cortar."""
    make_workflow("qualquer", steps=[("only", "Único")])
    state = CockpitState()
    state.configure_workflow("qualquer")

    assert state.can_stop is True
