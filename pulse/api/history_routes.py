"""Past runs of a project, as the history screen lists them."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from pulse.api.deps import project_root
from pulse.history.catalog import HistoryCatalog
from pulse.history.models import HistoryItem

router = APIRouter()


def _history_to_dict(item: HistoryItem) -> dict[str, Any]:
    return {
        "id": item.item_id,
        "run_id": item.run_id,
        "workflow_id": item.workflow_id,
        "workflow_label": item.workflow_label,
        "title": item.title,
        "prompt": item.prompt,
        "status": item.status.value,
        "updated_at": item.updated_at,
        "artifacts": list(item.artifacts),
        "branch": item.branch,
        "worktree_path": item.worktree_path,
        "steps": [
            {"id": step.id, "label": step.label, "status": step.status} for step in item.steps
        ],
    }


@router.get("/api/history")
def history(workspace: str | None = None, query: str = "") -> dict[str, Any]:
    catalog = HistoryCatalog(project_root(workspace))
    items = catalog.search(query) if query else catalog.list_items()
    return {"items": [_history_to_dict(item) for item in items]}


@router.get("/api/history/{item_id}")
def history_item(item_id: str, workspace: str | None = None) -> dict[str, Any]:
    item = HistoryCatalog(project_root(workspace)).get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return _history_to_dict(item)


@router.delete("/api/history/{item_id}")
def delete_history_item(item_id: str, workspace: str | None = None) -> dict[str, Any]:
    if not HistoryCatalog(project_root(workspace)).delete(item_id):
        raise HTTPException(status_code=404, detail="item not found")
    return {"ok": True}
