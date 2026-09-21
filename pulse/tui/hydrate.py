from __future__ import annotations

import re
from pathlib import Path

from pulse.history.models import HistoryItem, HistoryKind, HistoryStep
from pulse.history.runs import load_run_logs
from pulse.plan.specify_state import WorkflowState
from pulse.tui.artifacts import is_spec_artifact
from pulse.history.events import ArtifactItem, LogEntry, LogKind, PhaseStatus
from pulse.tui.state import CockpitState

_NO_LOGS = "Nenhum log persistido para esta sessão."
_TASK_INFO_RE = re.compile(r"Task\s+(T\d+)", re.IGNORECASE)
_STEP_TO_PHASE = {
    "pending": PhaseStatus.PENDING,
    "running": PhaseStatus.RUNNING,
    "done": PhaseStatus.DONE,
    "skipped": PhaseStatus.SKIPPED,
}
_ARTIFACT_PHASE = {
    "spec.md": "specify",
    "context.md": "specify",
    "design.md": "design",
    "tasks.md": "tasks",
    "task.md": "plan",
    "summary.md": "implement",
}


def hydrate_history_item(item: HistoryItem, workspace: Path) -> CockpitState:
    state = CockpitState()
    workflow_id = "new-issue" if item.kind == HistoryKind.ISSUE else "fix-bug"
    state.configure_workflow(workflow_id)
    state.surface_title = item.title.upper()
    state.running = False
    _apply_steps(state, item.steps)
    _apply_tasks(state, item, workspace)
    state.entries = _load_entries(item, workspace, state)
    _backfill_task_ids(state.entries)
    state.artifacts = _scan_artifacts(item, workspace)
    if state.artifacts:
        state.selected_artifact_path = state.artifacts[-1].path
        state.artifact_pane_open = True
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
        if phase.status in {PhaseStatus.DONE, PhaseStatus.SKIPPED, PhaseStatus.RUNNING}:
            phase.started_at = None
            phase.ended_at = None


def _apply_tasks(state: CockpitState, item: HistoryItem, workspace: Path) -> None:
    path = workspace / item.spec_dir / "workflow.yaml"
    if not path.is_file():
        return
    try:
        workflow = WorkflowState.load(path)
    except (OSError, ValueError):
        return
    state.set_tasks(
        [(task.task_id, task.title or task.task_id, task.status) for task in workflow.tasks]
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
    if item.run_id:
        entries = load_run_logs(workspace, item.run_id)
        if entries:
            for entry in entries:
                entry.active = False
                entry.pending = False
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
        artifacts.append(
            ArtifactItem(
                path=relative,
                phase_id=_ARTIFACT_PHASE.get(path.name.lower(), _fallback_phase(item, path.name)),
                ready=True,
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
