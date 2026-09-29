"""Histórico: as runs deste workspace, lidas do banco.

Antes o histórico era montado varrendo `.pulse/specs/` atrás de `PRD.md` e
`TASK.md` — o que só funcionava para um pipeline específico. Agora a lista é
`runs` + `run_steps`, então qualquer workflow aparece sem o Pulse saber o que
ele faz.
"""

from __future__ import annotations

from pathlib import Path

from pulse.history.models import HistoryItem, HistoryStatus, HistoryStep
from pulse.store import runs as run_store
from pulse.store.workflow_defs import get_workflow

_RUN_TO_HISTORY = {
    "pending": HistoryStatus.PENDING,
    "running": HistoryStatus.IN_PROGRESS,
    "paused": HistoryStatus.IN_PROGRESS,
    "completed": HistoryStatus.DONE,
    "failed": HistoryStatus.FAILED,
    "stopped": HistoryStatus.STOPPED,
}


class HistoryCatalog:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def list_items(self) -> list[HistoryItem]:
        return [_item(record) for record in run_store.list_runs(self.workspace)]

    def search(self, query: str = "") -> list[HistoryItem]:
        items = self.list_items()
        needle = query.strip().lower()
        if not needle:
            return items
        return [item for item in items if _matches(item, needle)]

    def get(self, item_id: str) -> HistoryItem | None:
        record = run_store.load_run(item_id)
        if record is None or record.workspace_root != str(self.workspace.resolve()):
            return None
        return _item(record)

    def delete(self, item_id: str) -> bool:
        """Remove a run do histórico. `False` = não é deste workspace.

        A checagem de workspace é a mesma do `get`: o histórico só mostra as
        runs daqui, então só essas ele pode apagar.
        """
        if self.get(item_id) is None:
            return False
        return run_store.delete_run(item_id)


def search_history(workspace: Path, query: str = "") -> list[HistoryItem]:
    return HistoryCatalog(workspace).search(query)


def _item(record: run_store.RunRecord) -> HistoryItem:
    definition = get_workflow(record.workflow_id)
    return HistoryItem(
        run_id=record.id,
        workflow_id=record.workflow_id,
        workflow_label=definition.label if definition else record.workflow_id,
        title=record.user_prompt.strip() or record.workflow_id,
        prompt=record.user_prompt,
        status=_RUN_TO_HISTORY.get(record.status, HistoryStatus.PENDING),
        updated_at=record.updated_at or record.created_at,
        steps=[
            HistoryStep(
                id=step.step_id,
                label=step.label or step.step_id,
                status=step.status,
                acp_session_id=step.acp_session_id,
            )
            for step in record.steps
        ],
        artifacts=[entry["path"] for entry in run_store.list_artifacts(record.id)],
    )


def _matches(item: HistoryItem, needle: str) -> bool:
    haystack = " ".join(
        [
            item.title,
            item.prompt,
            item.workflow_id,
            item.workflow_label,
            item.status.value,
            item.status_label,
        ]
    ).lower()
    return needle in haystack
