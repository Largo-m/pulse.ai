"""Rebuild the cockpit from a persisted run.

Everything comes from the run's `RunLog`, which the daemon reads from the
database: its steps feed the sidebar, its events the stream and its artifacts
the pane, so a run from any agent reopens the same. [hydrate_history_item]
builds the static history view; [restore_run] restores the past into a cockpit
that will keep running.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from pulse.history.events import (
    ArtifactItem,
    ContextUsage,
    LogEntry,
    LogKind,
    PhaseItem,
    PhaseStatus,
)
from pulse.history.models import HistoryItem
from pulse.history.run_log import RunLog
from pulse.tui import strings
from pulse.tui.artifacts import artifact_has_content, artifact_key, is_displayable_artifact
from pulse.tui.history_rows import run_title
from pulse.tui.state import CockpitState


def hydrate_history_item(item: HistoryItem, workspace: Path, log: RunLog | None) -> CockpitState:
    state = CockpitState()
    state.workflow_id = item.workflow_id
    # The header is the only place a reopened run names itself; phase titles take the stream's.
    state.workflow_label = f"{item.workflow_label.upper()} · {run_title(item)}"
    state.phases = [
        PhaseItem(
            id=step.id,
            label=step.label,
            status=step.status,
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

    if log is not None:
        _stamp_persisted(state, log)
    state.entries = _load_entries(log, state.phases)
    state.artifacts = _load_artifacts(log, Path(item.worktree_path or workspace))
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


def restore_run(state: CockpitState, log: RunLog, workspace: Path) -> str:
    """Load the run's existing history into the cockpit before it resumes.

    `sync_phases` preserves phases by id, so this survives the engine's later
    `phases.sync`. Returns the run's working directory (its worktree, if any) so
    the pane reads artifacts from the right root before `run.context` arrives.
    """
    state.sync_phases([{"id": step.step_id, "label": step.label} for step in log.steps])
    status = {step.step_id: step.status for step in log.steps}
    for phase in state.phases:
        phase.status = status.get(phase.id, PhaseStatus.PENDING)
        if phase.status == PhaseStatus.RUNNING:
            phase.status = PhaseStatus.PENDING
    _stamp_persisted(state, log)

    state.entries = _load_entries(log, state.phases, placeholder=False)
    state.artifacts = _load_artifacts(log, Path(log.exec_root or workspace))
    state.branch_label = log.branch
    state._next_entry_id = max((entry.entry_id for entry in state.entries), default=0) + 1
    state.notify()
    return log.exec_root


def restore_settled_steps(state: CockpitState, log: RunLog, workspace: Path) -> None:
    """After replaying an attached run, load from the DB what the replay lacks.

    A resume keeps the `run_id` but opens a new daemon bus, so the replay only
    covers events since the resume. Only settled phases with no replayed entries
    are filled in, so a never-resumed run is unchanged.
    """
    ended = {step.step_id for step in log.steps if step.has_ended}
    logged = {entry.phase_id for entry in state.entries if entry.phase_id}
    missing = ended - logged
    if not missing:
        return
    restored = [
        entry
        for entry in _load_entries(log, state.phases, placeholder=False)
        if entry.phase_id in missing
    ]
    for entry in restored:
        entry.entry_id = state._next_entry_id
        state._next_entry_id += 1
    state.entries = restored + state.entries
    known = {(artifact.path, artifact.phase_id) for artifact in state.artifacts}
    state.artifacts = [
        artifact
        for artifact in _load_artifacts(log, Path(log.exec_root or workspace))
        if artifact.phase_id in missing and (artifact.path, artifact.phase_id) not in known
    ] + state.artifacts
    state.notify()


def stamp_live_elapsed(state: CockpitState, log: RunLog) -> None:
    """Fix timers after rebuilding a run that is **still running**.

    Replay re-applies `phase.begin` instantly, so durations would count from
    reattach time. Settled steps use `run_steps`; the running step has its
    `started_at` shifted back by the time already spent so the timer continues.
    """
    _stamp_persisted(state, log)
    started = {step.step_id: step.started_at for step in log.steps}
    waiting = {step.step_id: step.waiting_seconds for step in log.steps}
    carried = {step.step_id: step.carried_seconds for step in log.steps}
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
        started_at = now_mono - spent - max(0.0, carried.get(phase.id, 0.0))
        phase.resume_clock(started_at, waiting.get(phase.id, 0.0))
    state.notify()


def _stamp_persisted(state: CockpitState, log: RunLog) -> None:
    """Set each step's duration and context tokens from what `run_steps` kept.

    The screen measures time with `time.monotonic()`, which does not survive the
    process; the (0, duration) pair shows the right duration without ticking.
    A step with no stored reading keeps whatever the live stream gave it.
    """
    durations = {step.step_id: step.elapsed_seconds for step in log.steps}
    tokens = {step.step_id: step.context_tokens for step in log.steps}
    for phase in state.phases:
        seconds = durations.get(phase.id)
        if seconds is not None:
            phase.show_closed(seconds)
        if tokens.get(phase.id):
            phase.context = ContextUsage(used=tokens[phase.id])


_BODY_KINDS = frozenset({LogKind.ASSISTANT, LogKind.QUESTION, LogKind.ANSWER})
_KIND_BY_NAME = {kind.value.lower(): kind for kind in LogKind}


def _entry_kind(raw: str) -> LogKind:
    """Map a persisted kind label back to the screen's `LogKind`.

    The DB stores the label the live session showed (`Read`, `Shell`, `Write`,
    `Info`); unknown labels (or from old runs) fall back to the generic `Tool`.
    """
    return _KIND_BY_NAME.get(str(raw or "").strip().lower(), LogKind.TOOL)


def _load_entries(
    log: RunLog | None, phases: list[PhaseItem], *, placeholder: bool = True
) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for event in log.events if log is not None else ():
        title = event.title.strip()
        detail = event.detail.strip()
        if not title and not detail:
            continue
        kind = _entry_kind(event.kind)
        entries.append(
            LogEntry(
                kind=kind,
                title=title[:160] or detail[:160],
                detail=detail,
                body=detail if kind in _BODY_KINDS else "",
                entry_id=len(entries) + 1,
                tool_id=event.tool_id,
                phase_id=event.step_id,
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


def _load_artifacts(log: RunLog | None, workspace: Path) -> list[ArtifactItem]:
    root = str(workspace)
    written = {
        (artifact_key(item.path), item.step_id): None
        for item in (log.artifacts if log is not None else ())
        if is_displayable_artifact(item.path, root)
    }
    return [
        ArtifactItem(
            path=path,
            phase_id=step_id,
            ready=True,
            has_content=artifact_has_content(path, root),
        )
        for path, step_id in written
    ]
