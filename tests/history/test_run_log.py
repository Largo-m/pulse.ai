"""`RunLog` is the wire format between the daemon and the cockpit's rebuild.

Both sides use the same codec; a field lost on the way would reopen a past run
with a wrong duration, a missing tool or an artifact in the wrong step.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from pulse.api.app import create_app
from pulse.daemon.runs import RunManager
from pulse.domain.run import RunRecord, StepRecord, StepStatus
from pulse.history.run_log import LoggedArtifact, LoggedEvent, LoggedStep, RunLog
from pulse.store import runs as run_store
from tests.conftest import make_workflow, store_step


def _record() -> RunRecord:
    return RunRecord(
        id="run-1",
        workflow_id="demo",
        workspace_root="/repo",
        worktree_path="/wt/run-1",
        branch="pulse/demo-run1",
        steps=[
            StepRecord(
                step_id="plan",
                label="Planejar",
                status=StepStatus.DONE,
                started_at=datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
                ended_at=datetime(2026, 9, 29, 10, 2, 30, tzinfo=UTC),
                waiting_seconds=30.0,
                carried_seconds=12.5,
                context_tokens=42_000,
            ),
            StepRecord(step_id="build", label="Construir"),
        ],
    )


def test_a_run_log_survives_the_wire_unchanged() -> None:
    log = RunLog.of(
        _record(),
        events=[{"step_id": "plan", "kind": "Read", "title": "read a.py", "detail": "1..9"}],
        artifacts=[{"path": "PLANO.md", "step_id": "plan"}],
    )

    assert RunLog.from_dict(log.to_dict()) == log


def test_the_log_carries_what_the_screen_needs_from_the_record() -> None:
    log = RunLog.of(_record(), events=[], artifacts=[])

    assert log.exec_root == "/wt/run-1", "artifacts are read where the agent worked"
    assert log.branch == "pulse/demo-run1"
    plan, build = log.steps
    assert plan.elapsed_seconds == pytest.approx(12.5 + 150.0 - 30.0)
    assert plan.has_ended is True
    assert plan.context_tokens == 42_000
    assert build == LoggedStep(step_id="build", label="Construir", status=StepStatus.PENDING)


def test_unknown_or_missing_fields_read_back_as_safe_defaults() -> None:
    """An older daemon may omit a field; a status it does not know reads as pending."""
    log = RunLog.from_dict(
        {
            "run_id": "r",
            "steps": [{"step_id": "s", "status": "exploded"}],
            "events": [{"title": "t"}],
            "artifacts": [{"path": "a.md"}],
        }
    )

    assert log.steps == (LoggedStep(step_id="s", label="", status=StepStatus.PENDING),)
    assert log.events == (LoggedEvent(step_id="", kind="", title="t", detail=""),)
    assert log.artifacts == (LoggedArtifact(path="a.md"),)
    assert (log.exec_root, log.branch) == ("", "")


def test_the_route_serves_the_stored_run_and_404s_an_unknown_one(tmp_path) -> None:
    make_workflow("demo", steps=[("plan", "Planejar")])
    record = run_store.create_run(
        run_id="run-9",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[StepRecord(step_id="plan", position=1, label="Planejar", agent_id="tester")],
    )
    plan = record.steps[0]
    plan.status = StepStatus.DONE
    store_step(record.id, plan)
    run_store.record_event(record.id, step_id="plan", kind="Info", title="ok", detail="ok")
    run_store.record_artifact(record.id, "PLANO.md", step_id="plan")
    client = TestClient(create_app(RunManager()), base_url="http://127.0.0.1")

    served = RunLog.from_dict(client.get("/api/runs/run-9/log").json())

    assert [(step.step_id, step.status) for step in served.steps] == [("plan", StepStatus.DONE)]
    assert [(event.step_id, event.title) for event in served.events] == [("plan", "ok")]
    assert served.artifacts == (LoggedArtifact(path="PLANO.md", step_id="plan"),)
    assert client.get("/api/runs/nope/log").status_code == 404
