"""Past runs of a project, as the history screen lists them and the cockpit reopens them."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from pulse import vcs
from pulse.api.deps import Runs, project_root
from pulse.history.catalog import HistoryCatalog
from pulse.history.models import HistoryItem
from pulse.history.run_log import RunLog
from pulse.store import runs as run_store

WORKTREE_IN_USE = 409

router = APIRouter()


def _known_item(item_id: str, workspace: str | None) -> tuple[HistoryCatalog, HistoryItem]:
    catalog = HistoryCatalog(project_root(workspace))
    item = catalog.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return catalog, item


@router.get("/api/history")
def history(workspace: str | None = None, query: str = "") -> dict[str, Any]:
    catalog = HistoryCatalog(project_root(workspace))
    items = catalog.search(query) if query else catalog.list_items()
    return {"items": [item.to_dict() for item in items]}


@router.get("/api/history/{item_id}")
def history_item(item_id: str, workspace: str | None = None) -> dict[str, Any]:
    return _known_item(item_id, workspace)[1].to_dict()


@router.delete("/api/history/{item_id}")
def delete_history_item(item_id: str, workspace: str | None = None) -> dict[str, Any]:
    if not HistoryCatalog(project_root(workspace)).delete(item_id):
        raise HTTPException(status_code=404, detail="item not found")
    return {"ok": True}


def _executing(runs: Runs, run_id: str) -> bool:
    """The daemon's memory decides, not the stored status: a crash leaves runs `running`."""
    state = runs.get(run_id)
    return state is not None and state.is_active()


@router.get("/api/history/{item_id}/worktree")
def worktree_state(item_id: str, runs: Runs, workspace: str | None = None) -> dict[str, Any]:
    """What removing the run's worktree would throw away, asked before confirming."""
    item = _known_item(item_id, workspace)[1]
    path = item.worktree_path
    exists = bool(path) and Path(path).exists()
    return {
        "path": path,
        "exists": exists,
        "dirty": exists and vcs.has_changes(path),
        "active": _executing(runs, item.run_id),
    }


@router.delete("/api/history/{item_id}/worktree")
def remove_worktree(item_id: str, runs: Runs, workspace: str | None = None) -> dict[str, Any]:
    """`removed` is false when git refused; a dirty worktree is never forced.

    A run the daemon still executes keeps it: its agent works there.
    """
    catalog, item = _known_item(item_id, workspace)
    if _executing(runs, item.run_id):
        raise HTTPException(status_code=WORKTREE_IN_USE, detail="run is active")
    return {"removed": catalog.remove_worktree(item)}


@router.get("/api/runs/{run_id}/log")
def run_log(run_id: str) -> dict[str, Any]:
    """The persisted run, so a screen can rebuild its steps, log and artifacts."""
    record = run_store.load_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    log = RunLog.of(
        record, events=run_store.list_events(run_id), artifacts=run_store.list_artifacts(run_id)
    )
    return log.to_dict()
