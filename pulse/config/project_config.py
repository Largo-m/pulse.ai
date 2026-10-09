from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from pulse.config.agents import AgentConfig, WorkflowConfig
from pulse.config.global_config import PERMISSION_POLICIES
from pulse.store.codec import dump_list, load_list
from pulse.store.db import connect, default_db_path
from pulse.store.paths import safe_cwd

DEFAULT_PROJECT_WORKFLOWS: dict[str, WorkflowConfig] = {}


@dataclass(frozen=True)
class ProjectConfig:
    source_file: Path
    project_id: str
    model: str | None = None
    permission_policy: str | None = None
    workspace: Path | None = None
    default_agent: str | None = None
    use_worktree: bool = False
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    workflows: dict[str, WorkflowConfig] = field(default_factory=dict)

    @property
    def project_root(self) -> Path:
        return self.source_file.resolve()


def _db(path: Path | None = None) -> Path:
    return path or default_db_path()


def find_project_root(start: Path | None = None, *, db_path: Path | None = None) -> Path | None:
    current = (start or safe_cwd()).resolve()
    connection = connect(_db(db_path))
    try:
        rows = connection.execute("SELECT root_path FROM projects").fetchall()
    finally:
        connection.close()
    registered = {Path(row["root_path"]).resolve() for row in rows}
    for directory in (current, *current.parents):
        if directory in registered:
            return directory
    return None


def load_project_config(
    start: Path | None = None,
    *,
    db_path: Path | None = None,
) -> ProjectConfig | None:
    root = find_project_root(start, db_path=db_path)
    if root is None:
        return None
    return _load_project(root, db_path=db_path)


def parse_project_config(root: Path, *, db_path: Path | None = None) -> ProjectConfig:
    loaded = _load_project(root.resolve(), db_path=db_path)
    if loaded is None:
        return ProjectConfig(source_file=root.resolve(), project_id="")
    return loaded


def _load_project(root: Path, *, db_path: Path | None = None) -> ProjectConfig | None:
    connection = connect(_db(db_path))
    try:
        project = connection.execute(
            "SELECT * FROM projects WHERE root_path = ?",
            (str(root.resolve()),),
        ).fetchone()
        if project is None:
            return None
        project_id = project["id"]
        settings = connection.execute(
            "SELECT * FROM project_settings WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        agents: dict[str, AgentConfig] = {}
        for agent_row in connection.execute(
            "SELECT * FROM project_agents WHERE project_id = ?",
            (project_id,),
        ):
            agents[agent_row["name"]] = AgentConfig(
                name=agent_row["name"],
                binary=agent_row["binary"],
                acp_command=load_list(agent_row["acp_command"]),
                models=load_list(agent_row["models"]),
            )
        workflows: dict[str, WorkflowConfig] = {}
        for workflow_row in connection.execute(
            "SELECT * FROM project_workflows WHERE project_id = ?",
            (project_id,),
        ):
            workflows[workflow_row["workflow_id"]] = WorkflowConfig(
                agent=workflow_row["agent"],
                model=workflow_row["model"],
            )
        model = settings["model"] if settings else None
        policy = settings["permission_policy"] if settings else None
        if policy not in PERMISSION_POLICIES:
            policy = None
        default_agent = settings["default_agent"] if settings else None
        workspace_path: Path | None = None
        workspace_value = settings["workspace_root"] if settings else None
        if workspace_value:
            candidate = Path(str(workspace_value)).expanduser()
            if not candidate.is_absolute():
                candidate = root / candidate
            workspace_path = candidate.resolve()
        return ProjectConfig(
            source_file=root,
            project_id=project_id,
            model=str(model) if model else None,
            permission_policy=policy,
            workspace=workspace_path,
            default_agent=str(default_agent) if default_agent else None,
            use_worktree=bool(settings["use_worktree"]) if settings else False,
            agents=agents,
            workflows=workflows,
        )
    finally:
        connection.close()


def project_config_exists(start: Path | None = None, *, db_path: Path | None = None) -> bool:
    return find_project_root(start, db_path=db_path) is not None


def render_project_config() -> str:
    return "sqlite"


def init_project_config(root: Path, *, db_path: Path | None = None) -> Path:
    resolved = root.resolve()
    existing = _load_project(resolved, db_path=db_path)
    if existing is not None:
        return resolved
    project_id = str(uuid.uuid4())
    connection = connect(_db(db_path))
    try:
        connection.execute(
            "INSERT INTO projects (id, root_path, created_at) VALUES (?, ?, ?)",
            (project_id, str(resolved), datetime.now(UTC).replace(microsecond=0).isoformat()),
        )
        connection.execute(
            """
            INSERT INTO project_settings (
              project_id, model, permission_policy, workspace_root, default_agent,
              use_worktree
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, None, None, None, None, 0),
        )
        for workflow_id, defaults in DEFAULT_PROJECT_WORKFLOWS.items():
            connection.execute(
                """
                INSERT INTO project_workflows (project_id, workflow_id, agent, model)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, workflow_id, defaults.agent, defaults.model),
            )
        connection.commit()
    finally:
        connection.close()
    return resolved


def ensure_project_workflows(root: Path, *, db_path: Path | None = None) -> Path:
    init_project_config(root, db_path=db_path)
    config = _load_project(root.resolve(), db_path=db_path)
    if config is None:
        return root.resolve()
    workflows = dict(config.workflows)
    changed = False
    for workflow_id, defaults in DEFAULT_PROJECT_WORKFLOWS.items():
        if workflow_id in workflows:
            continue
        workflows[workflow_id] = defaults
        changed = True
    if changed:
        _save_project(replace(config, workflows=workflows), db_path=db_path)
    return root.resolve()


def update_project_defaults(
    root: Path,
    *,
    model: str | None = None,
    permission_policy: str | None = None,
    agent: str | None = None,
    use_worktree: bool | None = None,
    db_path: Path | None = None,
) -> Path:
    init_project_config(root, db_path=db_path)
    config = _load_project(root.resolve(), db_path=db_path)
    if config is None:
        return root.resolve()
    if permission_policy is not None and permission_policy not in PERMISSION_POLICIES:
        raise ValueError(f"Invalid permission policy: {permission_policy}")
    if (model, permission_policy, agent, use_worktree) == (None, None, None, None):
        return root.resolve()
    updated = replace(
        config,
        model=config.model if model is None else model,
        permission_policy=config.permission_policy
        if permission_policy is None
        else permission_policy,
        default_agent=config.default_agent if agent is None else agent,
        use_worktree=config.use_worktree if use_worktree is None else bool(use_worktree),
    )
    _save_project(updated, db_path=db_path)
    return root.resolve()


def update_project_workflow(
    root: Path,
    workflow_id: str,
    *,
    agent: str | None = None,
    model: str | None = None,
    db_path: Path | None = None,
) -> Path:
    ensure_project_workflows(root, db_path=db_path)
    config = _load_project(root.resolve(), db_path=db_path)
    if config is None:
        return root.resolve()
    workflows = dict(config.workflows)
    existing = workflows.get(workflow_id, WorkflowConfig())
    workflows[workflow_id] = WorkflowConfig(
        agent=agent if agent is not None else existing.agent,
        model=model if model is not None else existing.model,
    )
    _save_project(replace(config, workflows=workflows), db_path=db_path)
    return root.resolve()


def update_project_agent(
    root: Path,
    agent_name: str,
    *,
    binary: str | None = None,
    models: list[str] | None = None,
    acp_command: list[str] | None = None,
    db_path: Path | None = None,
) -> Path:
    init_project_config(root, db_path=db_path)
    config = _load_project(root.resolve(), db_path=db_path)
    if config is None:
        return root.resolve()
    agents = dict(config.agents)
    existing = agents.get(agent_name)
    next_binary = binary if binary is not None else (existing.binary if existing else agent_name)
    next_models = (
        list(models) if models is not None else (list(existing.models) if existing else [])
    )
    if acp_command is not None:
        next_command = list(acp_command)
    elif existing is not None:
        next_command = list(existing.acp_command)
    else:
        next_command = [next_binary, "acp"]
    agents[agent_name] = AgentConfig(
        name=agent_name,
        binary=next_binary,
        acp_command=next_command,
        models=next_models,
    )
    _save_project(replace(config, agents=agents), db_path=db_path)
    return root.resolve()


def _save_project(config: ProjectConfig, *, db_path: Path | None = None) -> None:
    connection = connect(_db(db_path))
    try:
        workspace_root = None
        if config.workspace is not None:
            workspace_root = str(config.workspace)
        connection.execute(
            """
            INSERT INTO project_settings (
              project_id, model, permission_policy, workspace_root, default_agent,
              use_worktree
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
              model = excluded.model,
              permission_policy = excluded.permission_policy,
              workspace_root = excluded.workspace_root,
              default_agent = excluded.default_agent,
              use_worktree = excluded.use_worktree
            """,
            (
                config.project_id,
                config.model,
                config.permission_policy,
                workspace_root,
                config.default_agent,
                int(config.use_worktree),
            ),
        )
        connection.execute("DELETE FROM project_agents WHERE project_id = ?", (config.project_id,))
        for agent in config.agents.values():
            connection.execute(
                """
                INSERT INTO project_agents (project_id, name, binary, acp_command, models)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    config.project_id,
                    agent.name,
                    agent.binary,
                    dump_list(agent.acp_command),
                    dump_list(agent.models),
                ),
            )
        connection.execute(
            "DELETE FROM project_workflows WHERE project_id = ?", (config.project_id,)
        )
        for workflow_id, workflow in config.workflows.items():
            connection.execute(
                """
                INSERT INTO project_workflows (project_id, workflow_id, agent, model)
                VALUES (?, ?, ?, ?)
                """,
                (config.project_id, workflow_id, workflow.agent, workflow.model),
            )
        connection.commit()
    finally:
        connection.close()
