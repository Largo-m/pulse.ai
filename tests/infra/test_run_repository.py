"""`RunRepository`: the SQLite adapter and the in-memory fake keep the same promise.

The engine's tests run on the fake; these assertions are what make a green
engine test mean the same thing against the real database.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pulse.domain.ports import RunRepository
from pulse.domain.run import RunStatus, StepRecord, StepStatus
from pulse.store import runs as run_store
from pulse.store.runs import SqliteRunRepository
from tests.fakes import InMemoryRunRepository

AddArtifact = Callable[[RunRepository, str, str], None]


def _sqlite_artifact(_repository: RunRepository, run_id: str, path: str) -> None:
    run_store.record_artifact(run_id, path)


def _memory_artifact(repository: RunRepository, run_id: str, path: str) -> None:
    assert isinstance(repository, InMemoryRunRepository)
    repository.add_artifact(run_id, path)


@pytest.fixture(params=["sqlite", "memory"])
def adapter(request) -> tuple[RunRepository, AddArtifact]:
    if request.param == "sqlite":
        return SqliteRunRepository(), _sqlite_artifact
    return InMemoryRunRepository(), _memory_artifact


def _steps() -> list[StepRecord]:
    return [
        StepRecord(step_id="one", position=1000, label="Um", agent_id="a"),
        StepRecord(step_id="two", position=2000, label="Dois", agent_id="b"),
    ]


def _create(repository: RunRepository, tmp_path: Path):
    return repository.create(
        run_id="run-1",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="fazer algo",
        steps=_steps(),
    )


def test_both_adapters_implement_the_port(adapter):
    repository, _add = adapter

    assert isinstance(repository, RunRepository)


def test_a_created_run_is_running_with_every_step_pending(adapter, tmp_path: Path):
    repository, _add = adapter

    created = _create(repository, tmp_path)
    loaded = repository.load("run-1")

    for run in (created, loaded):
        assert run.status == RunStatus.RUNNING
        assert run.current_step == "one"
        assert run.workspace_root == str(tmp_path.resolve())
        assert [(step.step_id, step.position, step.status) for step in run.steps] == [
            ("one", 1000, StepStatus.PENDING),
            ("two", 2000, StepStatus.PENDING),
        ]


def test_an_unknown_run_does_not_exist(adapter):
    repository, _add = adapter

    assert repository.load("nope") is None


def test_a_change_is_stored_only_when_saved(adapter, tmp_path: Path):
    """The engine saves at each transition; whatever it did not save must not survive a crash."""
    repository, _add = adapter
    run = _create(repository, tmp_path)

    run.start_step("one")
    assert repository.load("run-1").step("one").status == StepStatus.PENDING

    repository.save(run)
    assert repository.load("run-1").step("one").status == StepStatus.RUNNING


def test_a_loaded_run_is_a_copy(adapter, tmp_path: Path):
    repository, _add = adapter
    _create(repository, tmp_path)

    repository.load("run-1").start_step("one")

    assert repository.load("run-1").step("one").status == StepStatus.PENDING


def test_steps_the_run_dropped_are_deleted_on_save(adapter, tmp_path: Path):
    """Fan-out replaces its base step; a stale base row would run again on resume."""
    repository, _add = adapter
    run = _create(repository, tmp_path)

    run.expand_step(
        "two",
        [
            StepRecord(step_id="two.T1", position=2001, label="T1", agent_id="b"),
            StepRecord(step_id="two.T2", position=2002, label="T2", agent_id="b"),
        ],
    )
    repository.save(run)

    assert [step.step_id for step in repository.load("run-1").steps] == [
        "one",
        "two.T1",
        "two.T2",
    ]
    assert run.removed_step_ids() == frozenset()


def test_artifacts_are_listed_in_the_order_they_were_written(adapter, tmp_path: Path):
    repository, add = adapter
    _create(repository, tmp_path)

    add(repository, "run-1", "docs/plan.md")
    add(repository, "run-1", "src/app.py")

    assert repository.artifacts("run-1") == ["docs/plan.md", "src/app.py"]
    assert repository.artifacts("other") == []
