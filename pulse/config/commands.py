from __future__ import annotations

from pathlib import Path

from pulse.config.paths import find_project_config_file, safe_cwd
from pulse.config.project_config import init_project_config
from pulse.config.resolved import resolve_config


def run_config_command(
    *,
    action: str = "show",
    workflow: str | None = None,
    cwd: Path | None = None,
) -> int:
    base = (cwd or safe_cwd()).resolve()
    if action == "init":
        return _init_project(base)
    return _show(base, workflow)


def _show(base: Path, workflow: str | None) -> int:
    resolved = resolve_config(base, workflow=workflow)
    title = "Config efetiva"
    if workflow:
        title += f" · workflow {workflow}"
    print(title)
    print(f"  agent              {resolved.agent_name}  ({resolved.sources.get('agent', '')})")
    print(f"  model              {resolved.model}  ({resolved.sources.get('model', '')})")
    print(
        f"  permission_policy  {resolved.permission_policy}  "
        f"({resolved.sources.get('permission_policy', '')})"
    )
    print(
        f"  workspace_dir      {resolved.workspace_dir}  "
        f"({resolved.sources.get('workspace_dir', '')})"
    )
    print(f"  worktree           {'ligado' if resolved.use_worktree else 'desligado'}  (project)")
    project = find_project_config_file(base)
    if project is not None:
        print(f"  project_config     {project}")
    return 0


def _init_project(base: Path) -> int:
    path = init_project_config(base)
    print(f"Projeto registrado no SQLite: {path}")
    return 0
