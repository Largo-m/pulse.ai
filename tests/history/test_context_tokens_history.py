"""A step's context tokens outlive the run: history reopens with the last reading.

The live screen reads `usage_update` from the bus, which dies with the daemon.
The session log keeps the last `used` of each step in `run_steps`, so a past run
shows the same tokens it showed while running.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pulse.domain.run import StepRecord, StepStatus
from pulse.history.events import ContextUsage
from pulse.history.models import HistoryItem, HistoryStatus, HistoryStep
from pulse.history.session_log import RecordedSessionLog
from pulse.store import runs as run_store
from pulse.tui.hydrate import hydrate_history_item
from tests.conftest import make_workflow, served_log

pytestmark = pytest.mark.usefixtures("in_process_daemon")

STEPS = [("plan", "Planejar"), ("build", "Construir")]


def _run(workspace: Path) -> str:
    make_workflow("demo", steps=STEPS)
    record = run_store.create_run(
        run_id="run-1",
        workflow_id="demo",
        workspace=workspace,
        user_prompt="fazer algo",
        steps=[
            StepRecord(step_id=step_id, position=index, label=label)
            for index, (step_id, label) in enumerate(STEPS, start=1)
        ],
    )
    return record.id


def _log(workspace: Path, run_id: str, step_id: str) -> RecordedSessionLog:
    log = RecordedSessionLog(project_root=workspace)
    log.bind_run(run_id)
    log.enter_step(step_id)
    return log


def _usage(used: object) -> dict:
    return {"update": {"sessionUpdate": "usage_update", "used": used, "size": 200_000}}


def _stored_tokens(run_id: str) -> dict[str, int]:
    record = run_store.load_run(run_id)
    assert record is not None
    return {step.step_id: step.context_tokens for step in record.steps}


def test_the_last_reading_of_each_step_is_stored(tmp_path: Path):
    run_id = _run(tmp_path)
    plan = _log(tmp_path, run_id, "plan")

    plan.update(_usage(80_000))
    plan.update(_usage(30_000))
    _log(tmp_path, run_id, "build").update(_usage(12_000))

    assert _stored_tokens(run_id) == {"plan": 30_000, "build": 12_000}


def test_a_malformed_reading_keeps_the_stored_one(tmp_path: Path):
    run_id = _run(tmp_path)
    plan = _log(tmp_path, run_id, "plan")
    plan.update(_usage(42_000))

    plan.update(_usage("lots"))
    plan.update(_usage(-1))

    assert _stored_tokens(run_id)["plan"] == 42_000


def test_saving_the_run_does_not_erase_the_tokens(tmp_path: Path):
    """The engine saves its in-memory steps, which never read the column back."""
    run_id = _run(tmp_path)
    _log(tmp_path, run_id, "plan").update(_usage(42_000))
    record = run_store.load_run(run_id)
    assert record is not None
    record.steps[0].status = StepStatus.DONE
    record.steps[0].context_tokens = 0

    run_store.save(record)

    assert _stored_tokens(run_id)["plan"] == 42_000


def test_a_failing_database_does_not_break_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The tokens are incidental to the run: losing them must not end the agent's turn."""
    run_id = _run(tmp_path)

    def broken(*_args: object, **_kwargs: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(run_store, "record_context_tokens", broken)

    _log(tmp_path, run_id, "plan").update(_usage(42_000))

    assert _stored_tokens(run_id)["plan"] == 0


def test_history_reopens_with_the_tokens_of_each_step(tmp_path: Path):
    run_id = _run(tmp_path)
    _log(tmp_path, run_id, "plan").update(_usage(30_000))
    _log(tmp_path, run_id, "build").update(_usage(12_000))
    item = HistoryItem(
        run_id=run_id,
        workflow_id="demo",
        workflow_label="Demo",
        title="demo",
        prompt="fazer algo",
        status=HistoryStatus.DONE,
        updated_at="2026-10-09T10:00:00+00:00",
        steps=[
            HistoryStep(id=step_id, label=label, status=StepStatus.DONE) for step_id, label in STEPS
        ],
    )

    state = hydrate_history_item(item, tmp_path, served_log(run_id))

    assert [phase.context for phase in state.phases] == [
        ContextUsage(used=30_000),
        ContextUsage(used=12_000),
    ]
    assert state.run_context_label() == "42k tokens"


def test_a_step_without_readings_reopens_without_tokens(tmp_path: Path):
    run_id = _run(tmp_path)
    item = HistoryItem(
        run_id=run_id,
        workflow_id="demo",
        workflow_label="Demo",
        title="demo",
        prompt="fazer algo",
        status=HistoryStatus.DONE,
        updated_at="2026-10-09T10:00:00+00:00",
        steps=[HistoryStep(id="plan", label="Planejar", status=StepStatus.DONE)],
    )

    state = hydrate_history_item(item, tmp_path, served_log(run_id))

    assert state.phases[0].context is None
