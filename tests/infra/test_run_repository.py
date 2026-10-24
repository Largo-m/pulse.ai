"""`RunRepository`: the SQLite adapter and the in-memory fake keep the same promise.

The engine's tests run on the fake; these assertions are what make a green
engine test mean the same thing against the real database.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

from pulse.domain.git_options import GitOptions
from pulse.domain.ports import RunRepository
from pulse.domain.run import RunStatus, StepRecord, StepStatus, utc_now
from pulse.domain.task_brief import TaskBrief
from pulse.store import runs as run_store
from pulse.store.runs import SqliteRunRepository
from tests.fakes import InMemoryRunRepository

AddArtifact = Callable[..., None]


def _sqlite_artifact(
    _repository: RunRepository, run_id: str, path: str, *, step_id: str = ""
) -> None:
    run_store.record_artifact(run_id, path, step_id=step_id)


def _memory_artifact(
    repository: RunRepository, run_id: str, path: str, *, step_id: str = ""
) -> None:
    assert isinstance(repository, InMemoryRunRepository)
    repository.add_artifact(run_id, path, step_id=step_id)


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


def test_step_artifacts_keep_only_what_that_step_wrote(adapter, tmp_path: Path):
    """A retry lists its own step's files, never another step's."""
    repository, add = adapter
    _create(repository, tmp_path)

    add(repository, "run-1", "docs/plan.md", step_id="one")
    add(repository, "run-1", "src/app.py", step_id="two")
    add(repository, "run-1", "docs/notes.md", step_id="one")

    assert repository.step_artifacts("run-1", "one", since=None) == [
        "docs/plan.md",
        "docs/notes.md",
    ]
    assert repository.step_artifacts("run-1", "two", since=None) == ["src/app.py"]
    assert repository.step_artifacts("other", "one", since=None) == []


def test_a_path_belongs_to_the_step_that_wrote_it_first(adapter, tmp_path: Path):
    repository, add = adapter
    _create(repository, tmp_path)

    add(repository, "run-1", "docs/plan.md", step_id="one")
    add(repository, "run-1", "docs/plan.md", step_id="two")

    assert repository.step_artifacts("run-1", "one", since=None) == ["docs/plan.md"]
    assert repository.step_artifacts("run-1", "two", since=None) == []
    assert repository.artifacts("run-1") == ["docs/plan.md"]


def test_step_artifacts_leave_out_files_written_before_since(adapter, tmp_path: Path):
    """Files from an earlier loop round predate the round's start and stay out."""
    repository, add = adapter
    _create(repository, tmp_path)
    add(repository, "run-1", "reviews/round-001.md", step_id="one")
    written = utc_now()

    assert repository.step_artifacts("run-1", "one", since=written) == ["reviews/round-001.md"]
    assert repository.step_artifacts("run-1", "one", since=written + timedelta(seconds=1)) == []


def test_a_run_keeps_the_brief_and_git_options_it_started_with(adapter, tmp_path: Path):
    """A resume reads them back, so a later change to the project settings cannot leak in."""
    repository, _ = adapter
    repository.create(
        run_id="run-1",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="Corrigir login\n\nerro 500",
        steps=_steps(),
        brief=TaskBrief(title="Corrigir login", description="erro 500"),
        git=GitOptions(use_worktree=True, atomic_commits=True, auto_pull_request=False),
    )

    loaded = repository.load("run-1")

    assert loaded is not None
    assert (loaded.title, loaded.description) == ("Corrigir login", "erro 500")
    assert loaded.git == GitOptions(use_worktree=True, atomic_commits=True)


def test_a_run_created_without_options_stores_every_option_off(adapter, tmp_path: Path):
    repository, _ = adapter
    _create(repository, tmp_path)

    loaded = repository.load("run-1")

    assert loaded is not None
    assert loaded.git == GitOptions()
    assert (loaded.title, loaded.description) == ("", "")
