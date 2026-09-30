"""Estado de execução no SQLite — o que permite retomar uma run."""

from __future__ import annotations

from pathlib import Path

from pulse.store import runs as run_store
from pulse.store.runs import DONE, PENDING, RUNNING, SKIPPED, StepRecord


def _create(tmp_path: Path, run_id: str = "run-1") -> run_store.RunRecord:
    return run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="fazer algo",
        steps=[
            StepRecord(step_id="one", position=1, label="Um", agent_id="tester"),
            StepRecord(step_id="two", position=2, label="Dois", agent_id="tester"),
        ],
    )


def test_a_new_run_starts_with_every_step_pending(tmp_path: Path):
    record = _create(tmp_path)

    loaded = run_store.load_run(record.id)
    assert loaded is not None
    assert loaded.status == RUNNING
    assert loaded.current_step == "one"
    assert [step.status for step in loaded.steps] == [PENDING, PENDING]


def test_steps_keep_the_label_they_had_when_the_run_started(tmp_path: Path):
    """Editar o workflow depois não pode reescrever o que já aconteceu."""
    record = _create(tmp_path)

    loaded = run_store.load_run(record.id)
    assert loaded is not None
    assert [step.label for step in loaded.steps] == ["Um", "Dois"]


def test_next_pending_skips_what_is_already_settled(tmp_path: Path):
    record = _create(tmp_path)
    first = record.steps[0]
    first.status = SKIPPED
    run_store.save_step(record.id, first)

    loaded = run_store.load_run(record.id)
    assert loaded is not None
    assert loaded.next_pending().step_id == "two"


def test_a_finished_run_is_not_resumable(tmp_path: Path):
    record = _create(tmp_path)
    for step in record.steps:
        step.status = DONE
        run_store.save_step(record.id, step)
    run_store.update_run(record.id, status="completed")

    assert run_store.find_resumable(tmp_path) == []


def test_a_run_cut_in_the_middle_is_resumable(tmp_path: Path):
    record = _create(tmp_path)
    first = record.steps[0]
    first.status = DONE
    run_store.save_step(record.id, first)
    run_store.update_run(record.id, status="stopped")

    pending = run_store.find_resumable(tmp_path)
    assert [item.id for item in pending] == [record.id]


def test_runs_are_scoped_to_their_workspace(tmp_path: Path):
    other = tmp_path / "outro"
    other.mkdir()
    _create(tmp_path, "run-here")
    run_store.create_run(
        run_id="run-there",
        workflow_id="demo",
        workspace=other,
        user_prompt="x",
        steps=[StepRecord(step_id="one", position=1, label="Um")],
    )

    assert [item.id for item in run_store.list_runs(tmp_path)] == ["run-here"]
    assert [item.id for item in run_store.list_runs(other)] == ["run-there"]


def test_a_repeated_tool_id_updates_the_log_line(tmp_path: Path):
    """Tool-call em andamento vira uma linha só, não uma por atualização."""
    record = _create(tmp_path)
    run_store.record_event(record.id, kind="Tool", title="Write", tool_id="t-1")
    run_store.record_event(record.id, kind="Tool", title="Write docs/x.md", tool_id="t-1")

    events = run_store.list_events(record.id)
    assert [event["title"] for event in events] == ["Write docs/x.md"]


def test_an_event_without_title_or_detail_is_dropped(tmp_path: Path):
    record = _create(tmp_path)
    run_store.record_event(record.id, kind="Assistant", title="", detail="")

    assert run_store.list_events(record.id) == []


def test_deleting_a_run_takes_its_steps_events_and_artifacts_along(tmp_path: Path):
    record = _create(tmp_path)
    run_store.record_event(record.id, kind="Assistant", title="oi", detail="oi")
    run_store.record_artifact(record.id, path="docs/PRD.md", step_id="one")
    other = _create(tmp_path, run_id="run-2")

    assert run_store.delete_run(record.id) is True

    assert run_store.load_run(record.id) is None
    assert run_store.list_events(record.id) == []
    assert run_store.list_artifacts(record.id) == []
    assert [item.id for item in run_store.list_runs(tmp_path)] == [other.id]


def test_deleting_a_run_that_is_not_there_says_so(tmp_path: Path):
    assert run_store.delete_run("run-que-nunca-existiu") is False


def test_a_run_that_failed_is_still_resumable(tmp_path: Path):
    """Falha é o caso em que mais se quer voltar: o que já fechou está gravado."""
    record = _create(tmp_path)
    first = record.steps[0]
    first.status = DONE
    run_store.save_step(record.id, first)
    run_store.update_run(record.id, status="failed")

    pending = run_store.find_resumable(tmp_path)
    assert [item.id for item in pending] == [record.id]


def test_the_step_position_comes_from_the_record(tmp_path: Path):
    """O motor espaça as posições para o fan-out caber entre dois steps."""
    record = run_store.create_run(
        run_id="run-spaced",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[
            StepRecord(step_id="one", position=1000, label="Um"),
            StepRecord(step_id="two", position=2000, label="Dois"),
        ],
    )
    loaded = run_store.load_run(record.id)
    assert loaded is not None
    assert [step.position for step in loaded.steps] == [1000, 2000]
