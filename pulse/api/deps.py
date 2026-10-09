"""What every route group needs from the app: the daemon's single `RunManager`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from pulse.daemon.runs import RunManager
from pulse.store.paths import safe_cwd


def _run_manager(request: Request) -> RunManager:
    manager: RunManager = request.app.state.runs
    return manager


Runs = Annotated[RunManager, Depends(_run_manager)]


def workspace_path(workspace: str | None) -> Path | None:
    return Path(workspace).resolve() if workspace else None


def project_root(workspace: str | None) -> Path:
    """History resolves by the project root; without one, where the daemon was started."""
    return workspace_path(workspace) or safe_cwd()
