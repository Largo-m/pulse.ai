from __future__ import annotations

from pulse.domain.control import RUN_STOPPED, RunControl
from pulse.domain.run import StepStatus
from pulse.tui.state import CockpitState
from tests.conftest import configure_from_db, make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import EngineHarness


def _stopping_at(step_id: str, control: RunControl):
    """The user stops while `step_id` is in flight: the agent's turn comes back cancelled."""

    def turn(current: str) -> dict | None:
        if current != step_id:
            return None
        control.stop()
        return {"stopReason": "cancelled"}

    return turn


def test_stop_returns_the_cut_step_to_pending(tmp_path):
    """The interrupted step neither finished nor failed: it goes back to pending."""
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    control = RunControl()
    session = FakeAgentSession([], control=control, before_turn=_stopping_at("one", control))
    harness = EngineHarness(tmp_path)

    code = harness.run(session, workflow_id="demo", user_prompt="x")

    assert code == RUN_STOPPED
    assert harness.runs.only().step("one").status == StepStatus.PENDING
    assert session.stream.messages == ["Run parada em Um"]


def test_settled_step_is_not_reopened_by_stop(tmp_path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    control = RunControl()
    done = {"stopReason": "end_turn", "phaseSummary": "```pulse:outcome\nstatus: done\n```"}
    session = FakeAgentSession([done], control=control, before_turn=_stopping_at("two", control))
    harness = EngineHarness(tmp_path)

    harness.run(session, workflow_id="demo", user_prompt="x")

    record = harness.runs.only()
    assert record.step("one").status == StepStatus.DONE, "a settled step does not go back"
    assert record.step("two").status == StepStatus.PENDING


def test_stop_does_not_mark_failure_in_sidebar():
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    state = CockpitState()
    configure_from_db(state, "demo")
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
    configure_from_db(state, "demo")
    state.begin_phase("Um")

    state.mark_finished(1)

    assert state.phases[0].status.value == "failed"
    assert state.stopped is False


def test_every_workflow_can_stop():
    """The ACP session is isolated per step: there is always a place to cut."""
    make_workflow("qualquer", steps=[("only", "Único")])
    state = CockpitState()
    configure_from_db(state, "qualquer")

    assert state.can_stop is True
