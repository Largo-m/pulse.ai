from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from pulse.history.models import HistoryItem, HistoryStep, SpecFlow
from pulse.plan.workflow_state import WorkflowState
from pulse.tui.artifacts import is_spec_artifact
from pulse.history.events import ArtifactItem, LogEntry, LogKind, PhaseStatus
from pulse.tui.cursor_store import list_session_events, session_task_id
from pulse.tui.state import CockpitState

_NO_LOGS = "Nenhum log persistido para esta sessão."
_TASK_INFO_RE = re.compile(r"Task\s+(T\d+)", re.IGNORECASE)
_STEP_TO_PHASE = {
    "pending": PhaseStatus.PENDING,
    "running": PhaseStatus.RUNNING,
    "done": PhaseStatus.DONE,
    "skipped": PhaseStatus.SKIPPED,
    "failed": PhaseStatus.FAILED,
}
_ARTIFACT_PHASE = {
    "PRD.md": "prd",
    "context.md": "prd",
    "TECHSPEC.md": "techspec",
    "tasks.md": "tasks",
    "task.md": "plan",
    "summary.md": "implement",
}


def hydrate_history_item(item: HistoryItem, workspace: Path) -> CockpitState:
    state = CockpitState()
    workflow_id = "new-issue" if item.flow == SpecFlow.FULL else "fix-bug"
    state.configure_workflow(workflow_id)
    state.surface_title = item.title.upper()
    state.running = False
    _apply_steps(state, item.steps)
    _apply_tasks(state, item, workspace)
    _stamp_elapsed(state, item, workspace)
    state.entries = _load_entries(item, workspace, state)
    _backfill_task_ids(state.entries)
    _note_tasks_without_logs(state)
    state.artifacts = _scan_artifacts(item, workspace)
    displayable = [artifact for artifact in state.artifacts if artifact.has_content]
    if displayable:
        state.selected_artifact_path = displayable[-1].path
    selected = 0
    logged = {entry.phase_id for entry in state.entries if entry.phase_id}
    for index, phase in enumerate(state.phases):
        if phase.id in logged:
            selected = index
            break
        if phase.status == PhaseStatus.RUNNING:
            selected = index
            break
    state.selected_phase_index = selected
    state.selected_nav_kind = "phase"
    state._follow_live = False
    state._next_entry_id = max((entry.entry_id for entry in state.entries), default=0) + 1
    return state


def _apply_steps(state: CockpitState, steps: list[HistoryStep]) -> None:
    by_id = {step.id: step for step in steps}
    for phase in state.phases:
        step = by_id.get(phase.id)
        if step is None:
            continue
        phase.status = _STEP_TO_PHASE.get(step.status, PhaseStatus.PENDING)


def _stamp_elapsed(state: CockpitState, item: HistoryItem, workspace: Path) -> None:
    workflow = _load_workflow(item, workspace)
    if workflow is None:
        return
    for phase_id, seconds in _phase_durations(workflow).items():
        phase = next((item_phase for item_phase in state.phases if item_phase.id == phase_id), None)
        if phase is not None:
            _set_elapsed(phase, seconds)
    durations = _task_durations(workflow)
    for task in state.tasks:
        seconds = durations.get(task.id)
        if seconds is not None:
            _set_elapsed(task, seconds)


def _phase_durations(workflow: WorkflowState) -> dict[str, float]:
    cursor = _parse_stamp(workflow.created_at)
    ends = {
        "prd": _parse_stamp(workflow.phases["prd"].approved_at),
        "techspec": _parse_stamp(workflow.phases["techspec"].approved_at),
        "tasks": _parse_stamp(workflow.phases["tasks"].approved_at),
        "execute": _parse_stamp(workflow.updated_at),
    }
    durations: dict[str, float] = {}
    for name in ("prd", "techspec", "tasks", "execute"):
        phase = workflow.phases.get(name)
        end = ends.get(name)
        skipped = phase is not None and (
            phase.skip or getattr(phase.status, "value", phase.status) == "skipped"
        )
        if not skipped and cursor is not None and end is not None:
            delta = (end - cursor).total_seconds()
            if delta >= 0:
                durations[name] = delta
        if end is not None:
            cursor = end
    return durations


def _task_durations(workflow: WorkflowState) -> dict[str, float]:
    cursor = _parse_stamp(workflow.phases["tasks"].approved_at) or _parse_stamp(workflow.created_at)
    durations: dict[str, float] = {}
    for task in workflow.tasks:
        end = _parse_stamp(task.completed_at)
        if cursor is not None and end is not None:
            delta = (end - cursor).total_seconds()
            if delta >= 0:
                durations[task.task_id] = delta
        if end is not None:
            cursor = end
    return durations


def _set_elapsed(item: object, seconds: float) -> None:
    setattr(item, "started_at", 0.0)
    setattr(item, "ended_at", seconds)


def _load_workflow(item: HistoryItem, workspace: Path) -> WorkflowState | None:
    path = workspace / item.spec_dir / "workflow.yaml"
    if not path.is_file():
        return None
    try:
        return WorkflowState.load(path)
    except (OSError, ValueError):
        return None


def _apply_tasks(state: CockpitState, item: HistoryItem, workspace: Path) -> None:
    path = workspace / item.spec_dir / "workflow.yaml"
    if not path.is_file():
        return
    try:
        workflow = WorkflowState.load(path)
    except (OSError, ValueError):
        return
    tasks_md = path.parent / "tasks.md"
    if tasks_md.is_file():
        workflow.sync_tasks_from_markdown(tasks_md)
    state.set_tasks(
        [(task.task_id, task.title or task.task_id, task.status) for task in workflow.tasks]
    )


def _note_tasks_without_logs(state: CockpitState) -> None:
    if not state.entries or all(entry.title == _NO_LOGS for entry in state.entries):
        return
    seen = {entry.task_id for entry in state.entries if entry.task_id}
    next_id = max(entry.entry_id for entry in state.entries)
    for task in state.tasks:
        if task.status != PhaseStatus.DONE or task.id in seen:
            continue
        next_id += 1
        state.entries.append(
            LogEntry(
                kind=LogKind.INFO,
                title="O Cursor não gravou as mensagens desta task.",
                detail="O Cursor não gravou as mensagens desta task.",
                entry_id=next_id,
                phase_id="execute",
                task_id=task.id,
            )
        )


def _backfill_task_ids(entries: list[LogEntry]) -> None:
    current = ""
    for entry in entries:
        if entry.task_id:
            current = entry.task_id
            continue
        if entry.kind == LogKind.INFO:
            match = _TASK_INFO_RE.search(entry.title or "")
            if match is not None:
                current = match.group(1)
                entry.task_id = current
                continue
        if current and entry.phase_id == "execute":
            entry.task_id = current


def _load_entries(item: HistoryItem, workspace: Path, state: CockpitState) -> list[LogEntry]:
    entries = _entries_from_store(item, workspace)
    if entries:
        return entries
    # Specs antigas: o log só existe no store do Cursor.
    sessions = _sessions_for_item(item, workspace)
    entries = _entries_from_sessions(sessions)
    if entries:
        return entries
    return [
        LogEntry(
            kind=LogKind.INFO,
            title=_NO_LOGS,
            detail=_NO_LOGS,
            entry_id=index + 1,
            phase_id=phase.id,
        )
        for index, phase in enumerate(state.phases)
    ]


def _entries_from_store(item: HistoryItem, workspace: Path) -> list[LogEntry]:
    """Log gravado pelo próprio Pulse — vale para qualquer runtime."""
    try:
        from pulse.store.spec_events import list_spec_events

        rows = list_spec_events(workspace, item.spec_dir)
    except Exception:
        return []
    entries: list[LogEntry] = []
    for row in rows:
        title = row.get("title", "").strip()
        detail = row.get("detail", "").strip()
        if not title and not detail:
            continue
        entries.append(
            LogEntry(
                kind=LogKind.TOOL if row.get("kind") == "Tool" else LogKind.ASSISTANT,
                title=title[:160] or detail[:160],
                detail=detail,
                entry_id=len(entries) + 1,
                tool_id=row.get("tool_id", ""),
                phase_id=row.get("phase_id", ""),
                task_id=row.get("task_id", ""),
            )
        )
    return entries


def _sessions_for_item(item: HistoryItem, workspace: Path) -> list[dict[str, str]]:
    import pulse.config.project_config  # noqa: F401
    from pulse.store.spec_sessions import list_project_sessions, list_spec_sessions

    recorded = list_spec_sessions(workspace, item.spec_dir)
    if recorded:
        return recorded
    workflow_path = workspace / item.spec_dir / "workflow.yaml"
    if not workflow_path.is_file():
        return []
    try:
        workflow = WorkflowState.load(workflow_path)
    except (OSError, ValueError):
        return []
    start = _parse_stamp(workflow.created_at)
    end = _parse_stamp(workflow.updated_at)
    if start is None or end is None:
        return []
    window_start = start - timedelta(minutes=10)
    window_end = end + timedelta(minutes=10)
    matched = [
        row
        for row in list_project_sessions(workspace)
        if _in_window(row.get("started_at", ""), window_start, window_end)
    ]
    return _assign_phase_ids(matched, item.flow)


def _assign_phase_ids(rows: list[dict[str, str]], flow: SpecFlow) -> list[dict[str, str]]:
    phases = ["plan", "implement"] if flow == SpecFlow.QUICK else ["prd", "techspec", "tasks", "execute"]
    classify = [row for row in rows if row.get("agent_id") == "classify"]
    rest = [row for row in rows if row.get("agent_id") != "classify"]
    assigned: list[dict[str, str]] = []
    for row in classify:
        assigned.append({**row, "phase_id": phases[0]})
    for index, row in enumerate(rest):
        assigned.append({**row, "phase_id": phases[min(index, len(phases) - 1)]})
    return assigned


def _entries_from_sessions(sessions: list[dict[str, str]]) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for session in sessions:
        phase_id = session.get("phase_id", "")
        task_id = session.get("task_id", "")
        session_id = session.get("acp_session_id", "")
        if not task_id and phase_id == "execute":
            task_id = session_task_id(session_id)
        for event in list_session_events(session_id):
            kind_name = str(event.get("kind", ""))
            kind = LogKind.TOOL if kind_name == "Tool" else LogKind.ASSISTANT
            title = str(event.get("title") or "").strip()
            detail = str(event.get("detail") or "").strip()
            if not title and not detail:
                continue
            if len(detail) > 2000:
                detail = detail[:2000].rstrip()
            entries.append(
                LogEntry(
                    kind=kind,
                    title=title[:160] or detail[:160],
                    detail=detail,
                    entry_id=len(entries) + 1,
                    tool_id=str(event.get("tool_id") or ""),
                    phase_id=phase_id,
                    task_id=task_id,
                )
            )
    return entries


def _parse_stamp(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed


def _in_window(value: str, start: datetime, end: datetime) -> bool:
    stamp = _parse_stamp(value)
    if stamp is None:
        return False
    if stamp.tzinfo is None and start.tzinfo is not None:
        stamp = stamp.replace(tzinfo=start.tzinfo)
    if stamp.tzinfo is not None and start.tzinfo is None:
        start = start.replace(tzinfo=stamp.tzinfo)
        end = end.replace(tzinfo=stamp.tzinfo)
    return start <= stamp <= end


def _scan_artifacts(item: HistoryItem, workspace: Path) -> list[ArtifactItem]:
    spec_dir = workspace / item.spec_dir
    if not spec_dir.is_dir():
        return []
    artifacts: list[ArtifactItem] = []
    for path in sorted(spec_dir.glob("*.md")):
        try:
            relative = path.relative_to(workspace).as_posix()
        except ValueError:
            relative = f"{item.spec_dir}/{path.name}"
        if not is_spec_artifact(relative):
            continue
        try:
            has_content = path.stat().st_size > 0
        except OSError:
            has_content = False
        artifacts.append(
            ArtifactItem(
                path=relative,
                phase_id=_ARTIFACT_PHASE.get(path.name.lower(), _fallback_phase(item, path.name)),
                ready=True,
                has_content=has_content,
            )
        )
    return artifacts


def _fallback_phase(item: HistoryItem, name: str) -> str:
    lowered = name.lower()
    for step in item.steps:
        if step.artifact and step.artifact.lower() == lowered:
            return step.id
    if item.steps:
        return item.steps[0].id
    return ""
