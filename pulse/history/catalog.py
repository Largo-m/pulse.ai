from __future__ import annotations

from pathlib import Path

from pulse.history.models import HistoryItem, HistoryKind, HistoryStatus, HistoryStep
from pulse.history.quick_index import list_quick_tasks
from pulse.history.runs import latest_run_for, list_runs
from pulse.plan.specify_state import (
    PHASE_ORDER,
    PhaseStatus,
    WorkflowState,
    _is_workflow_incomplete,
    list_feature_workflows,
)

_ISSUE_STEPS = (
    ("specify", "Specify"),
    ("design", "Design"),
    ("tasks", "Tasks"),
    ("execute", "Execute"),
)
_WORKFLOW_TO_UI = {
    PhaseStatus.PENDING: "pending",
    PhaseStatus.IN_PROGRESS: "running",
    PhaseStatus.AWAITING_APPROVAL: "running",
    PhaseStatus.APPROVED: "done",
    PhaseStatus.DONE: "done",
    PhaseStatus.SKIPPED: "skipped",
}


class HistoryCatalog:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def list_items(self) -> list[HistoryItem]:
        runs = list_runs(self.workspace)
        items = [_item_from_workflow(state, runs) for state in list_feature_workflows(self.workspace)]
        items.extend(_item_from_quick(task, runs) for task in list_quick_tasks(self.workspace))
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items

    def search(
        self,
        query: str = "",
        *,
        kind: HistoryKind | None = None,
    ) -> list[HistoryItem]:
        items = self.list_items()
        if kind is not None:
            items = [item for item in items if item.kind == kind]
        needle = query.strip().lower()
        if not needle:
            return items
        return [item for item in items if _matches(item, needle)]

    def get(self, item_id: str) -> HistoryItem | None:
        for item in self.list_items():
            if item.item_id == item_id:
                return item
        return None


def search_history(
    workspace: Path,
    query: str = "",
    *,
    kind: HistoryKind | None = None,
) -> list[HistoryItem]:
    return HistoryCatalog(workspace).search(query, kind=kind)


def _item_from_workflow(state: WorkflowState, runs: list) -> HistoryItem:
    spec_dir = state.feature_dir.as_posix()
    run = latest_run_for(runs, spec_dir=spec_dir, slug=state.feature_slug, kind=HistoryKind.ISSUE)
    title = state.user_prompt.strip() or state.feature_slug
    return HistoryItem(
        kind=HistoryKind.ISSUE,
        slug=state.feature_slug,
        title=title,
        prompt=state.user_prompt,
        status=_issue_status(state),
        updated_at=state.updated_at or state.created_at,
        spec_dir=spec_dir,
        steps=_issue_steps(state),
        run_id=run.id if run is not None else None,
    )


def _item_from_quick(task, runs: list) -> HistoryItem:
    run = latest_run_for(
        runs,
        spec_dir=task.spec_dir,
        slug=task.slug,
        kind=HistoryKind.FIX,
    )
    return HistoryItem(
        kind=HistoryKind.FIX,
        slug=task.slug,
        title=task.title,
        prompt=task.title,
        status=task.status,
        updated_at=task.updated_at,
        spec_dir=task.spec_dir,
        steps=_fix_steps(task.status),
        run_id=run.id if run is not None else None,
    )


def _issue_status(state: WorkflowState) -> HistoryStatus:
    if not _is_workflow_incomplete(state):
        return HistoryStatus.DONE
    for phase_name in PHASE_ORDER:
        if state.phases[phase_name].status == PhaseStatus.AWAITING_APPROVAL:
            return HistoryStatus.AWAITING_APPROVAL
    return HistoryStatus.IN_PROGRESS


def _issue_steps(state: WorkflowState) -> list[HistoryStep]:
    steps: list[HistoryStep] = []
    for phase_id, label in _ISSUE_STEPS:
        phase = state.phases.get(phase_id)
        if phase is None:
            status = "pending"
            artifact = ""
        else:
            status = _WORKFLOW_TO_UI.get(phase.status, "pending")
            artifact = phase.artifact
        steps.append(HistoryStep(id=phase_id, label=label, status=status, artifact=artifact))
    return steps


def _fix_steps(status: HistoryStatus) -> list[HistoryStep]:
    if status == HistoryStatus.DONE:
        plan_status, implement_status = "done", "done"
    elif status == HistoryStatus.IN_PROGRESS:
        plan_status, implement_status = "done", "running"
    elif status in {HistoryStatus.AWAITING_APPROVAL, HistoryStatus.BLOCKED}:
        plan_status, implement_status = "done", "pending"
    else:
        plan_status, implement_status = "pending", "pending"
    return [
        HistoryStep(id="plan", label="Planejar", status=plan_status, artifact="TASK.md"),
        HistoryStep(id="implement", label="Implementar", status=implement_status, artifact="SUMMARY.md"),
    ]


def _matches(item: HistoryItem, needle: str) -> bool:
    haystack = " ".join(
        [
            item.title,
            item.slug,
            item.prompt,
            item.status.value,
            item.status_label,
            item.kind.value,
            item.kind_label,
            item.spec_dir,
        ]
    ).lower()
    return needle in haystack
