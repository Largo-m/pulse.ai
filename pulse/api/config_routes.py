"""Global and project config, and what they resolve to for a workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from pulse.api.deps import workspace_path
from pulse.config.global_config import GlobalConfig, load_global_config, update_global_defaults
from pulse.config.project_config import ProjectConfig, init_project_config, load_project_config
from pulse.config.resolved import resolve_config

router = APIRouter()


class ConfigPatchBody(BaseModel):
    model: str | None = None
    permission_policy: str | None = None
    default_agent: str | None = None


class ProjectConfigBody(BaseModel):
    workspace: str


def _global_to_dict(config: GlobalConfig | None) -> dict[str, Any] | None:
    if config is None:
        return None
    return {
        "version": config.version,
        "agent_binary": config.agent_binary,
        "acp_command": list(config.acp_command),
        "auth_method": config.auth_method,
        "workspace_dir": str(config.workspace_dir),
        "model": config.model,
        "permission_policy": config.permission_policy,
        "completed_at": config.completed_at,
        "acp_test_passed": config.acp_test_passed,
        "default_agent": config.default_agent,
    }


def _project_to_dict(config: ProjectConfig | None) -> dict[str, Any] | None:
    if config is None:
        return None
    return {
        "source_file": str(config.source_file),
        "model": config.model,
        "permission_policy": config.permission_policy,
        "workspace": str(config.workspace) if config.workspace else None,
        "default_agent": config.default_agent,
        "use_worktree": config.use_worktree,
    }


@router.get("/api/config")
def get_config() -> dict[str, Any]:
    return {
        "global": _global_to_dict(load_global_config()),
        "project": _project_to_dict(load_project_config()),
    }


@router.get("/api/config/resolved")
def get_resolved(workflow: str | None = None, workspace: str | None = None) -> dict[str, Any]:
    resolved = resolve_config(workspace=workspace_path(workspace), workflow=workflow)
    return {
        "agent": resolved.agent_name,
        "model": resolved.model,
        "permission_policy": resolved.permission_policy,
        "workspace": str(resolved.workspace_dir),
        "use_worktree": resolved.use_worktree,
        "acp_command": list(resolved.acp_command),
        "auth_method": resolved.auth_method,
    }


@router.patch("/api/config/global")
def patch_global(body: ConfigPatchBody) -> dict[str, Any]:
    # Fields left out are None, and `update_global_defaults` leaves those untouched.
    update_global_defaults(
        model=body.model,
        permission_policy=body.permission_policy,
        agent=body.default_agent,
    )
    return {"ok": True, "global": _global_to_dict(load_global_config())}


@router.post("/api/config/project")
def post_project(body: ProjectConfigBody) -> dict[str, Any]:
    path = init_project_config(Path(body.workspace))
    return {"ok": True, "path": str(path)}
