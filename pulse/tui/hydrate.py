"""Rebuild the cockpit from a persisted run.

Everything comes from the database: `run_steps` feeds the sidebar, `run_events`
the stream and `run_artifacts` the pane, so a run from any agent reopens the same.
[hydrate_history_item] builds the static history view; [restore_run] restores
the past into a cockpit that will keep running.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from pulse.domain.run import StepStatus
from pulse.history.events import ArtifactItem, LogEntry, LogKind, PhaseItem, PhaseStatus
from pulse.history.models import HistoryItem
from pulse.store import runs as run_store
from pulse.tui import strings
from pulse.tui.artifacts import artifact_has_content, artifact_key
from pulse.tui.state import CockpitState

_STEP_TO_PHASE = {
    StepStatus.PENDING: PhaseStatus.PENDING,
    StepStatus.RUNNING: PhaseStatus.RUNNING,
    StepStatus.DONE: PhaseStatus.DONE,
    StepStatus.SKIPPED: PhaseStatus.SKIPPED,
    StepStatus.FAILED: PhaseStatus.FAILED,
    StepStatus.BLOCKED: PhaseStatus.BLOCKED,
}


def hydrate_history_item(item: HistoryItem, workspace: Path) -> CockpitState:
    state = CockpitState()
    state.workflow_id = item.workflow_id
    state.workflow_label = item.workflow_label.upper()
    state.phases = [
        PhaseItem(
            id=step.id,
            label=step.label,
            status=_STEP_TO_PHASE.get(step.status, PhaseStatus.PENDING),
        )
        for step in item.steps
    ]
    state.surface_title = item.title.upper()
    state.branch_label = item.branch
    state.running = False
    state.acp_sessions = [
        {"phase_id": step.id, "label": step.label, "acp_session_id": step.acp_session_id}
        for step in item.steps
        if step.acp_session_id
    ]
    if state.acp_sessions:
        state.acp_session_id = state.acp_sessions[-1]["acp_session_id"]

    _stamp_elapsed(state, item.run_id)
    state.entries = _load_entries(item.run_id, state.phases)
    state.artifacts = _load_artifacts(item.run_id, Path(item.worktree_path or workspace))
    displayable = [artifact for artifact in state.artifacts if artifact.has_content]
    if displayable:
        state.selected_artifact_path = displayable[-1].path

    logged = {entry.phase_id for entry in state.entries if entry.phase_id}
    selected = 0
    for index, phase in enumerate(state.phases):
        if phase.id in logged or phase.status == PhaseStatus.RUNNING:
            selected = index
            break
    state.selected_phase_index = selected
    state._follow_live = False
    state._next_entry_id = max((entry.entry_id for entry in state.entries), default=0) + 1
    return state


def restore_run(state: CockpitState, run_id: str, workspace: Path) -> str:
    """Load the run's existing history into the cockpit before it resumes.

    `sync_phases` preserves phases by id, so this survives the engine's later
    `phases.sync`. Returns the run's working directory (its worktree, if any) so
    the pane reads artifacts from the right root before `run.context` arrives.
    """
    record = run_store.load_run(run_id)
    if record is None:
        return ""

    state.sync_phases([{"id": step.step_id, "label": step.label} for step in record.steps])
    status = {step.step_id: _STEP_TO_PHASE[step.status] for step in record.steps}
    for phase in state.phases:
        phase.status = status.get(phase.id, PhaseStatus.PENDING)
        if phase.status == PhaseStatus.RUNNING:
            phase.status = PhaseStatus.PENDING
    _stamp_elapsed(state, run_id)

    state.entries = _load_entries(run_id, state.phases, placeholder=False)
    state.artifacts = _load_artifacts(run_id, Path(record.exec_root or workspace))
    state.branch_label = record.branch
    state._next_entry_id = max((entry.entry_id for entry in state.entries), default=0) + 1
    state.notify()
    return record.exec_root


def restore_settled_steps(state: CockpitState, run_id: str, workspace: Path) -> None:
    """After replaying an attached run, load from the DB what the replay lacks.

    A resume keeps the `run_id` but opens a new daemon bus, so the replay only
    covers events since the resume. Only settled phases with no replayed entries
    are filled in, so a never-resumed run is unchanged.
    """
    record = run_store.load_run(run_id)
    if record is None:
        return
    ended = {step.step_id for step in record.steps if step.has_ended}
    logged = {entry.phase_id for entry in state.entries if entry.phase_id}
    missing = ended - logged
    if not missing:
        return
    restored = [
        entry
        for entry in _load_entries(run_id, state.phases, placeholder=False)
        if entry.phase_id in missing
    ]
    for entry in restored:
        entry.entry_id = state._next_entry_id
        state._next_entry_id += 1
    state.entries = restored + state.entries
    known = {artifact.path for artifact in state.artifacts}
    state.artifacts = [
        artifact
        for artifact in _load_artifacts(run_id, Path(record.exec_root or workspace))
        if artifact.phase_id in missing and artifact.path not in known
    ] + state.artifacts
    state.notify()


def stamp_live_elapsed(state: CockpitState, run_id: str) -> None:
    """Fix timers after rebuilding a run that is **still running**.

    Replay re-applies `phase.begin` instantly, so durations would count from
    reattach time. Settled steps use `run_steps`; the running step has its
    `started_at` shifted back by the time already spent so the timer continues.
    """
    record = run_store.load_run(run_id)
    if record is None:
        return
    _stamp_elapsed(state, run_id)
    started = {step.step_id: step.started_at for step in record.steps}
    waiting = {step.step_id: step.waiting_seconds for step in record.steps}
    carried = {step.step_id: step.carried_seconds for step in record.steps}
    now_wall = datetime.now(UTC)
    now_mono = time.monotonic()
    for phase in state.phases:
        if phase.status != PhaseStatus.RUNNING:
            continue
        begin = started.get(phase.id)
        if begin is None:
            continue
        spent = (now_wall - begin).total_seconds()
        if spent < 0:
            continue
        phase.started_at = now_mono - spent - max(0.0, carried.get(phase.id, 0.0))
        phase.ended_at = None
        phase.waiting_total = max(0.0, waiting.get(phase.id, 0.0))
    state.notify()


def _stamp_elapsed(state: CockpitState, run_id: str) -> None:
    """Set each step's duration from what was persisted in `run_steps`.

    The screen measures time with `time.monotonic()`, which does not survive the
    process; the (0, duration) pair shows the right duration without ticking.
    """
    record = run_store.load_run(run_id)
    if record is None:
        return
    durations = {step.step_id: step.elapsed_seconds() for step in record.steps}
    for phase in state.phases:
        seconds = durations.get(phase.id)
        if seconds is not None:
            phase.started_at = 0.0
            phase.ended_at = seconds
            phase.waiting_total = 0.0


_BODY_KINDS = frozenset({LogKind.ASSISTANT, LogKind.QUESTION, LogKind.ANSWER})
_KIND_BY_NAME = {kind.value.lower(): kind for kind in LogKind}


def _entry_kind(raw: str) -> LogKind:
    """Map a persisted kind label back to the screen's `LogKind`.

    The DB stores the label the live session showed (`Read`, `Shell`, `Write`,
    `Info`); unknown labels (or from old runs) fall back to the generic `Tool`.
    """
    return _KIND_BY_NAME.get(str(raw or "").strip().lower(), LogKind.TOOL)


def _load_entries(
    run_id: str, phases: list[PhaseItem], *, placeholder: bool = True
) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for row in run_store.list_events(run_id):
        title = row.get("title", "").strip()
        detail = row.get("detail", "").strip()
        if not title and not detail:
            continue
        kind = _entry_kind(row.get("kind", ""))
        entries.append(
            LogEntry(
                kind=kind,
                title=title[:160] or detail[:160],
                detail=detail,
                body=detail if kind in _BODY_KINDS else "",
                entry_id=len(entries) + 1,
                tool_id=row.get("tool_id", ""),
                phase_id=row.get("step_id", ""),
            )
        )
    if entries or not placeholder:
        return entries
    return [
        LogEntry(
            kind=LogKind.INFO,
            title=strings.NO_PERSISTED_LOGS,
            detail=strings.NO_PERSISTED_LOGS,
            entry_id=index + 1,
            phase_id=phase.id,
        )
        for index, phase in enumerate(phases)
    ]


def _load_artifacts(run_id: str, workspace: Path) -> list[ArtifactItem]:
    by_step = {entry["path"]: entry["step_id"] for entry in run_store.list_artifacts(run_id)}
    artifacts: list[ArtifactItem] = []
    for path, step_id in by_step.items():
        key = artifact_key(path)
        artifacts.append(
            ArtifactItem(
                path=key,
                phase_id=step_id,
                ready=True,
                has_content=artifact_has_content(key, str(workspace)),
            )
        )
    return artifacts
