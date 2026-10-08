from pathlib import Path

import pytest
from hypothesis import settings

from pulse.domain.run import RunStatus, StepRecord
from pulse.domain.workflow import AgentDef, RepeatRule, StepDef, WorkflowDef
from pulse.store import runs as run_store
from pulse.store.workflow_defs import save_agent, save_workflow

# Property tests replay the same examples on every run and every machine
# (AGENTS.md §5.1): a failure seen locally is the one CI sees, and no example
# database is left on disk.
settings.register_profile("pulse", derandomize=True, database=None)
settings.load_profile("pulse")


@pytest.fixture(autouse=True)
def _isolate_pulse_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULSE_DB", str(tmp_path / "pulse.db"))


def make_workflow(
    workflow_id: str = "demo",
    *,
    steps: list[tuple[str, str]] | None = None,
    label: str = "Demo",
    requires_approval: bool = True,
    prompt_template: str = "{{user_prompt}}",
    fan_out: tuple[str, ...] | set[str] = (),
    requires_outcome: bool = True,
    repeat: tuple[str, str, int] | None = None,
) -> WorkflowDef:
    """Persist a test workflow in the database and return its definition.

    Pulse ships only the single-step `default` workflow, so each test seeds its own.
    `repeat=(step_id, back_to, max)` marks a loop: that step may send the run back
    to repeat the span.
    """
    entries = steps or [("one", "Um"), ("two", "Dois")]
    save_agent(AgentDef(id="tester", label="Tester"))
    definition = WorkflowDef(
        id=workflow_id,
        label=label,
        steps=tuple(
            StepDef(
                workflow_id=workflow_id,
                step_id=step_id,
                position=index,
                label=step_label,
                agent_id="tester",
                prompt_template=prompt_template,
                requires_approval=requires_approval,
                fan_out=step_id in fan_out,
                requires_outcome=requires_outcome,
                repeat=RepeatRule(back_to=repeat[1], max_rounds=repeat[2])
                if repeat and repeat[0] == step_id
                else None,
            )
            for index, (step_id, step_label) in enumerate(entries, start=1)
        ),
    )
    save_workflow(definition)
    return definition


@pytest.fixture
def demo_workflow() -> WorkflowDef:
    return make_workflow()


def store_step(run_id: str, step: StepRecord) -> None:
    """Fixture shortcut: write one step of a stored run as a past execution left it."""
    record = run_store.load_run(run_id)
    assert record is not None, run_id
    record.steps = [step if item.step_id == step.step_id else item for item in record.steps]
    run_store.save(record)


def store_run_status(run_id: str, status: str) -> None:
    """Fixture shortcut: leave a stored run in `status`, as the daemon would."""
    record = run_store.load_run(run_id)
    assert record is not None, run_id
    record.status = RunStatus(status)
    run_store.save(record)
