from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from pulse.config.agents import (
    DEFAULT_AGENT_NAME,
    AgentConfig,
    WorkflowConfig,
    default_global_agents,
    default_global_workflows,
)
from pulse.store.codec import dump_list, load_list
from pulse.store.db import connect, default_db_path

PERMISSION_POLICIES = ("ask", "auto_approve", "deny_writes")


@dataclass(frozen=True)
class GlobalConfig:
    version: int
    agent_binary: str
    acp_command: list[str]
    auth_method: str
    workspace_dir: Path
    model: str
    permission_policy: str
    completed_at: str | None = None
    acp_test_passed: bool = False
    default_agent: str = DEFAULT_AGENT_NAME
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    workflows: dict[str, WorkflowConfig] = field(default_factory=dict)

    @property
    def is_onboarded(self) -> bool:
        return self.completed_at is not None


def global_config_exists(path: Path | None = None) -> bool:
    return load_global_config(path) is not None


def load_global_config(path: Path | None = None) -> GlobalConfig | None:
    connection = connect(path)
    try:
        row = connection.execute("SELECT * FROM machine WHERE id = 1").fetchone()
        if row is None:
            return None
        agents: dict[str, AgentConfig] = {}
        for agent_row in connection.execute("SELECT * FROM machine_agents"):
            agents[agent_row["name"]] = AgentConfig(
                name=agent_row["name"],
                binary=agent_row["binary"],
                acp_command=load_list(agent_row["acp_command"]),
                models=load_list(agent_row["models"]),
            )
        if not agents:
            agents = default_global_agents()
        workflows: dict[str, WorkflowConfig] = {}
        for workflow_row in connection.execute("SELECT * FROM machine_workflows"):
            workflows[workflow_row["workflow_id"]] = WorkflowConfig(
                agent=workflow_row["agent"],
                model=workflow_row["model"],
            )
        if not workflows:
            workflows = default_global_workflows()
        policy = row["permission_policy"]
        if policy not in PERMISSION_POLICIES:
            policy = "ask"
        return GlobalConfig(
            version=int(row["version"]),
            agent_binary=str(row["agent_binary"]),
            acp_command=load_list(row["acp_command"]),
            auth_method=str(row["auth_method"]),
            workspace_dir=Path(str(row["workspace_dir"])).expanduser(),
            model=str(row["model"]),
            permission_policy=policy,
            completed_at=row["completed_at"],
            acp_test_passed=bool(row["acp_test_passed"]),
            default_agent=str(row["default_agent"]),
            agents=agents,
            workflows=workflows,
        )
    finally:
        connection.close()


def save_global_config(config: GlobalConfig, path: Path | None = None) -> Path:
    db_path = path or default_db_path()
    connection = connect(db_path)
    try:
        connection.execute("DELETE FROM machine_workflows")
        connection.execute("DELETE FROM machine_agents")
        connection.execute("DELETE FROM machine")
        connection.execute(
            """
            INSERT INTO machine (
              id, version, agent_binary, acp_command, auth_method, workspace_dir,
              model, permission_policy, completed_at, acp_test_passed, default_agent
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                config.version,
                config.agent_binary,
                dump_list(config.acp_command),
                config.auth_method,
                str(config.workspace_dir.expanduser().resolve()),
                config.model,
                config.permission_policy,
                config.completed_at,
                1 if config.acp_test_passed else 0,
                config.default_agent,
            ),
        )
        for agent in config.agents.values():
            connection.execute(
                """
                INSERT INTO machine_agents (name, binary, acp_command, models)
                VALUES (?, ?, ?, ?)
                """,
                (agent.name, agent.binary, dump_list(agent.acp_command), dump_list(agent.models)),
            )
        for workflow_id, workflow in config.workflows.items():
            connection.execute(
                """
                INSERT INTO machine_workflows (workflow_id, agent, model)
                VALUES (?, ?, ?)
                """,
                (workflow_id, workflow.agent, workflow.model),
            )
        connection.commit()
    finally:
        connection.close()
    return db_path


def update_global_defaults(
    *,
    model: str | None = None,
    permission_policy: str | None = None,
    agent: str | None = None,
    path: Path | None = None,
) -> Path | None:
    config = load_global_config(path)
    if config is None:
        return None
    updates: dict[str, str] = {}
    if model is not None:
        updates["model"] = model
    if permission_policy is not None:
        if permission_policy not in PERMISSION_POLICIES:
            return None
        updates["permission_policy"] = permission_policy
    if agent is not None:
        updates["default_agent"] = agent
    if not updates:
        return path or default_db_path()
    return save_global_config(replace(config, **updates), path)


def update_global_agent(
    agent_name: str,
    *,
    binary: str | None = None,
    models: list[str] | None = None,
    acp_command: list[str] | None = None,
    path: Path | None = None,
) -> Path | None:
    config = load_global_config(path)
    if config is None:
        return None
    agents = dict(config.agents)
    existing = agents.get(agent_name)
    next_binary = binary if binary is not None else (existing.binary if existing else agent_name)
    next_models = list(models) if models is not None else (list(existing.models) if existing else [])
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
    return save_global_config(replace(config, agents=agents), path)


def update_global_workflow(
    workflow_id: str,
    *,
    agent: str | None = None,
    model: str | None = None,
    path: Path | None = None,
) -> Path | None:
    config = load_global_config(path)
    if config is None:
        return None
    workflows = dict(config.workflows)
    existing = workflows.get(workflow_id, WorkflowConfig())
    workflows[workflow_id] = WorkflowConfig(
        agent=agent if agent is not None else existing.agent,
        model=model if model is not None else existing.model,
    )
    return save_global_config(replace(config, workflows=workflows), path)


def mark_onboarding_complete(
    *,
    agent_binary: str,
    acp_command: list[str],
    auth_method: str,
    workspace_dir: Path,
    model: str,
    permission_policy: str,
    acp_test_passed: bool,
    default_agent: str = "cursor",
    path: Path | None = None,
) -> Path:
    config = GlobalConfig(
        version=1,
        agent_binary=agent_binary,
        acp_command=acp_command,
        auth_method=auth_method,
        workspace_dir=workspace_dir.expanduser().resolve(),
        model=model,
        permission_policy=permission_policy,
        completed_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        acp_test_passed=acp_test_passed,
        default_agent=default_agent,
        agents=default_global_agents(),
        workflows=default_global_workflows(),
    )
    return save_global_config(config, path)
