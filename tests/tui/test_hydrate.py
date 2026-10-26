"""A reopened run shows, in each step, the Markdown files that step wrote."""

from __future__ import annotations

from pathlib import Path

from pulse.domain.run import StepStatus
from pulse.history.models import HistoryItem, HistoryStatus, HistoryStep
from pulse.history.run_log import LoggedArtifact, LoggedStep, RunLog
from pulse.tui.hydrate import hydrate_history_item, restore_settled_steps
from pulse.tui.state import CockpitState

STEPS = [("verify", "Verificar"), ("fix", "Corrigir")]


def _worktree(tmp_path: Path) -> Path:
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "validation.md").write_text("**Round**: 3\n", encoding="utf-8")
    (tmp_path / "Probe.kt").write_text("class Probe\n", encoding="utf-8")
    return tmp_path


def _log(worktree: Path, *rows: tuple[str, str], steps: tuple[LoggedStep, ...] = ()) -> RunLog:
    return RunLog(
        run_id="run-1",
        exec_root=str(worktree),
        branch="",
        steps=steps,
        artifacts=tuple(LoggedArtifact(path=path, step_id=step) for path, step in rows),
    )


def _item(worktree: Path) -> HistoryItem:
    return HistoryItem(
        run_id="run-1",
        workflow_id="demo",
        workflow_label="Demo",
        title="Reordenar",
        prompt="x",
        status=HistoryStatus.DONE,
        updated_at="",
        steps=[HistoryStep(id=sid, label=label, status=StepStatus.DONE) for sid, label in STEPS],
        worktree_path=str(worktree),
    )


def test_a_reopened_loop_step_shows_its_markdown_not_the_last_scratch_file(tmp_path):
    """The verify step wrote `/tmp/…_r3.py` last, and the pane showed it instead of
    `validation.md`: an empty "writing…" placeholder where round 3 should be.
    """
    worktree = _worktree(tmp_path)
    log = _log(
        worktree,
        ("/scratch/reorder_sensor.py", "verify"),
        ("specs/validation.md", "verify"),
        ("Probe.kt", "verify"),
        ("specs/validation.md", "fix"),
        ("/scratch/reorder_sensor_r3.py", "verify"),
    )

    state = hydrate_history_item(_item(worktree), worktree, log)
    state.select_phase(0)

    assert [(item.path, item.phase_id) for item in state.artifacts] == [
        ("specs/validation.md", "verify"),
        ("specs/validation.md", "fix"),
    ]
    assert state.selected_artifact().path == "specs/validation.md"
    state.select_phase(1)
    assert [item.path for item in state.visible_artifacts()] == ["specs/validation.md"]


def test_restoring_settled_steps_adds_a_file_another_phase_already_shows(tmp_path):
    """The replay showed the file under `verify`; the fix step's edit must still be restored."""
    worktree = _worktree(tmp_path)
    fix_ended = LoggedStep(step_id="fix", label="Corrigir", status=StepStatus.DONE, has_ended=True)
    log = _log(
        worktree,
        ("specs/validation.md", "verify"),
        ("specs/validation.md", "fix"),
        steps=(fix_ended,),
    )
    state = CockpitState()
    state.sync_phases([{"id": sid, "label": label} for sid, label in STEPS])
    state.begin_phase("Verificar")
    state.upsert_artifact("specs/validation.md", ready=True, has_content=True)

    restore_settled_steps(state, log, worktree)

    assert [(item.path, item.phase_id) for item in state.artifacts] == [
        ("specs/validation.md", "fix"),
        ("specs/validation.md", "verify"),
    ]
