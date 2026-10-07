"""Attaching to a resumed run: the replay only holds what came after the resume."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import store_step
from pulse.history.events import LogEntry, LogKind
from pulse.store import runs as run_store
from pulse.store.runs import StepRecord
from pulse.tui.hydrate import restore_settled_steps
from pulse.tui.state import CockpitState


def _resumed_run(tmp_path: Path) -> run_store.RunRecord:
    record = run_store.create_run(
        run_id="run-r",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[
            StepRecord(step_id="one", position=1, label="Um", agent_id="tester"),
            StepRecord(step_id="two", position=2, label="Dois", agent_id="tester"),
        ],
    )
    record.steps[0].status = "done"
    store_step(record.id, record.steps[0])
    run_store.record_event(record.id, kind="Assistant", title="fiz o um", detail="fiz o um", step_id="one")
    run_store.record_event(record.id, kind="Assistant", title="fazendo o dois", detail="fazendo o dois", step_id="two")
    return record


def test_steps_closed_before_the_resume_get_their_log_back(tmp_path: Path):
    _resumed_run(tmp_path)
    state = CockpitState()
    state.sync_phases([{"id": "one", "label": "Um"}, {"id": "two", "label": "Dois"}])
    state.entries = [LogEntry(kind=LogKind.ASSISTANT, title="fazendo o dois", entry_id=1, phase_id="two")]
    state._next_entry_id = 2

    restore_settled_steps(state, "run-r", tmp_path)

    assert [(entry.phase_id, entry.title) for entry in state.entries] == [
        ("one", "fiz o um"),
        ("two", "fazendo o dois"),
    ]
    assert len({entry.entry_id for entry in state.entries}) == 2


def test_a_run_the_replay_already_covers_is_left_alone(tmp_path: Path):
    _resumed_run(tmp_path)
    state = CockpitState()
    state.sync_phases([{"id": "one", "label": "Um"}, {"id": "two", "label": "Dois"}])
    state.entries = [
        LogEntry(kind=LogKind.ASSISTANT, title="fiz o um", entry_id=1, phase_id="one"),
        LogEntry(kind=LogKind.ASSISTANT, title="fazendo o dois", entry_id=2, phase_id="two"),
    ]

    restore_settled_steps(state, "run-r", tmp_path)

    assert len(state.entries) == 2
