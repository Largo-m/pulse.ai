from __future__ import annotations

from pulse.orchestrator.engine import _release_step
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.store import runs as run_store
from pulse.store.runs import StepRecord, StepStatus
from pulse.tui.state import CockpitState
from tests.conftest import make_workflow, store_step


class _FakeStream:
    """Only the stream surface used when cutting a run."""

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
    step.status = StepStatus.RUNNING
    store_step(record.id, step)
    return record, step


def test_stop_returns_the_cut_step_to_pending(tmp_path):
    """The interrupted step neither finished nor failed: it goes back to pending."""
    control = RunControl()
    control.stop()
    runner = _FakeRunner(control)
    record, step = _run(tmp_path)

    _release_step(runner, run=record, record=step, label="Um")

    assert step.status == StepStatus.PENDING
    reloaded = run_store.load_run(record.id)
    assert reloaded.step("one").status == StepStatus.PENDING
    assert runner._stream.messages == ["Run parada em Um"]


def test_settled_step_is_not_reopened_by_stop(tmp_path):
    control = RunControl()
    control.stop()
    runner = _FakeRunner(control)
    record, step = _run(tmp_path)
    step.status = "done"
    store_step(record.id, step)

    _release_step(runner, run=record, record=step, label="Um")

    assert step.status == "done", "a settled step does not go back to pending"


def test_stop_does_not_mark_failure_in_sidebar():
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
    assert running.elapsed_label() == "", "with no step in progress, the clock stops"


def test_real_failure_still_marks_failure():
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.begin_phase("Um")

    state.mark_finished(1)

    assert state.phases[0].status.value == "failed"
    assert state.stopped is False


def test_every_workflow_can_stop():
    """The ACP session is isolated per step: there is always a place to cut."""
    make_workflow("qualquer", steps=[("only", "Único")])
    state = CockpitState()
    state.configure_workflow("qualquer")

    assert state.can_stop is True
