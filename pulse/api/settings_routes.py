"""Setup and settings: what the onboarding and settings screens read and change.

The screens are thin clients (AGENTS.md §2.1): every value they show and every
write they make goes through here, so the daemon stays the single owner of
config, runtimes and the doctor.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pulse import vcs
from pulse.api.deps import project_root
from pulse.config.global_config import PERMISSION_POLICIES
from pulse.config.model_catalog import DEFAULT_MODELS, collect_available_models
from pulse.config.onboarding import complete_onboarding, setup_state
from pulse.config.project_settings import (
    AgentField,
    SettingsOrderError,
    agent_fields,
    project_settings,
    set_agent_field,
    set_atomic_commits,
    set_auto_pull_request,
    set_project_default,
    set_worktree,
)
from pulse.config.resolved import resolve_config
from pulse.doctor.checks import CheckResult, run_agent_checks
from pulse.runtimes import DEFAULT_RUNTIME_ID, AgentRuntime, all_runtimes, find_runtime
from pulse.store.db import default_db_path
from pulse.vcs import changes as git_changes

router = APIRouter()


class OnboardingBody(BaseModel):
    runtime: str
    workspace: str
    model: str
    permission_policy: str
    auth_method: str
    acp_test_passed: bool = False


class FieldBody(BaseModel):
    workspace: str
    field: AgentField
    value: str


class WorktreeBody(BaseModel):
    workspace: str
    enabled: bool


class FlagBody(BaseModel):
    workspace: str
    enabled: bool


def _runtime_or_404(runtime_id: str) -> AgentRuntime:
    runtime = find_runtime(runtime_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail=f"unknown runtime: {runtime_id}")
    return runtime


def _check_to_dict(check: CheckResult) -> dict[str, Any]:
    return {
        "name": check.name,
        "status": check.status,
        "message": check.message,
        "detail": check.detail,
    }


def _runtime_to_dict(runtime: AgentRuntime) -> dict[str, Any]:
    return {
        "id": runtime.id,
        "label": runtime.label,
        "binary": runtime.binary,
        "install_hint": runtime.install_hint,
        "login_command": list(runtime.login_command),
        "auth_env_var": runtime.auth_env_var,
        "auth_method_label": runtime.auth_method_label,
        "default_models": list(runtime.default_models),
    }


@router.get("/api/setup")
def get_setup(workspace: str | None = None) -> dict[str, Any]:
    state = setup_state(project_root(workspace))
    return {
        "configured": state.configured,
        "onboarded": state.onboarded,
        "ready": state.ready,
        "workspace_dir": state.workspace_dir,
        "database": str(default_db_path()),
        "permission_policies": list(PERMISSION_POLICIES),
    }


@router.post("/api/setup/onboarding")
def post_onboarding(body: OnboardingBody) -> dict[str, Any]:
    _runtime_or_404(body.runtime)
    if body.permission_policy not in PERMISSION_POLICIES:
        raise HTTPException(status_code=422, detail=f"unknown policy: {body.permission_policy}")
    path = complete_onboarding(
        runtime_id=body.runtime,
        workspace=Path(body.workspace).resolve(),
        model=body.model,
        permission_policy=body.permission_policy,
        auth_method=body.auth_method,
        acp_test_passed=body.acp_test_passed,
    )
    return {"ok": True, "path": str(path)}


@router.get("/api/runtimes")
def get_runtimes() -> dict[str, Any]:
    return {
        "default": DEFAULT_RUNTIME_ID,
        "runtimes": [_runtime_to_dict(runtime) for runtime in all_runtimes()],
    }


@router.get("/api/runtimes/{runtime_id}/checks")
def get_runtime_checks(runtime_id: str) -> dict[str, Any]:
    """CLI checks first, the login check last: onboarding reads them in that order."""
    runtime = _runtime_or_404(runtime_id)
    return {"checks": [_check_to_dict(check) for check in run_agent_checks(runtime.id)]}


@router.get("/api/models")
def get_models(workspace: str | None = None, runtime: str | None = None) -> dict[str, Any]:
    """Models the agent advertises over ACP, else the ones its runtime declares, else Pulse's.

    `runtime` names a configured agent (`resolve_config(...).agents`), which may
    be a custom ACP command rather than a registered runtime.
    """
    selected = find_runtime(runtime)
    models = collect_available_models(project_root(workspace), agent_name=runtime)
    if not models and selected is not None:
        models = list(selected.default_models)
    return {"models": models or list(DEFAULT_MODELS)}


@router.get("/api/settings")
def get_settings(workspace: str | None = None) -> dict[str, Any]:
    root = project_root(workspace)
    settings = project_settings(root)
    return {
        "is_repo": settings.is_repo,
        "use_worktree": settings.use_worktree,
        "atomic_commits": settings.atomic_commits,
        "auto_pull_request": settings.auto_pull_request,
        "defaults": settings.defaults.to_dict(),
        "agents": [
            {"id": agent.id, "label": agent.label, **agent.fields.to_dict()}
            for agent in settings.agents
        ],
        "runtimes": [
            {"id": name, "binary": agent.binary}
            for name, agent in resolve_config(root).agents.items()
        ],
        "permission_policies": list(PERMISSION_POLICIES),
    }


@router.patch("/api/settings/defaults")
def patch_defaults(body: FieldBody) -> dict[str, Any]:
    """A project-wide value; it is written into every agent of the project too."""
    _validate(body)
    root = Path(body.workspace).resolve()
    set_project_default(root, body.field, body.value)
    return {"ok": True}


@router.patch("/api/settings/agents/{agent_id}")
def patch_agent(agent_id: str, body: FieldBody) -> dict[str, Any]:
    _validate(body)
    root = Path(body.workspace).resolve()
    if agent_fields(root, agent_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown agent: {agent_id}")
    set_agent_field(root, agent_id, body.field, body.value)
    return {"ok": True}


@router.put("/api/settings/worktree")
def put_worktree(body: WorktreeBody) -> dict[str, Any]:
    set_worktree(Path(body.workspace).resolve(), enabled=body.enabled)
    return {"ok": True}


@router.put("/api/settings/atomic-commits")
def put_atomic_commits(body: FlagBody) -> dict[str, Any]:
    _save_flag(set_atomic_commits, body)
    return {"ok": True}


@router.put("/api/settings/pull-request")
def put_pull_request(body: FlagBody) -> dict[str, Any]:
    _save_flag(set_auto_pull_request, body)
    return {"ok": True}


@router.get("/api/git/branch")
def get_branch(name: str = "", workspace: str | None = None) -> dict[str, Any]:
    root = project_root(workspace)
    repo = vcs.repo_root(root) or root
    valid = git_changes.branch_name_ok(repo, name)
    return {"valid": valid, "exists": valid and vcs.branch_exists(repo, name)}


def _save_flag(save: Callable[..., None], body: FlagBody) -> None:
    try:
        save(Path(body.workspace).resolve(), enabled=body.enabled)
    except SettingsOrderError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _validate(body: FieldBody) -> None:
    """An empty value or an unknown policy is refused before anything is written."""
    if not body.value.strip():
        raise HTTPException(status_code=422, detail=f"empty {body.field}")
    if body.field == "permission_policy" and body.value not in PERMISSION_POLICIES:
        raise HTTPException(status_code=422, detail=f"unknown policy: {body.value}")
