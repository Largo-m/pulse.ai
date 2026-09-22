from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pulse.config.agents import DEFAULT_AGENT_NAME, AgentConfig
from pulse.config.global_config import GlobalConfig, load_global_config
from pulse.config.project_config import ProjectConfig, load_project_config

DEFAULT_ACP_COMMAND = ["agent", "acp"]
DEFAULT_MODEL = "auto"
DEFAULT_PERMISSION_POLICY = "ask"
DEFAULT_AGENT_BINARY = "agent"
DEFAULT_AUTH_METHOD = "cursor_login"


@dataclass(frozen=True)
class ResolvedConfig:
    agent_name: str
    agent_binary: str
    acp_command: list[str]
    auth_method: str
    model: str
    permission_policy: str
    workspace_dir: Path
    workflow: str | None = None
    pulse_agent: str | None = None
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    global_config: GlobalConfig | None = None
    project_config: ProjectConfig | None = None


def _merge_agents(
    global_cfg: GlobalConfig | None,
    project_cfg: ProjectConfig | None,
) -> dict[str, AgentConfig]:
    agents: dict[str, AgentConfig] = {}
    if global_cfg:
        agents.update(global_cfg.agents)
    if project_cfg:
        agents.update(project_cfg.agents)
    if DEFAULT_AGENT_NAME not in agents:
        if global_cfg:
            agents[DEFAULT_AGENT_NAME] = AgentConfig(
                name=DEFAULT_AGENT_NAME,
                binary=global_cfg.agent_binary,
                acp_command=list(global_cfg.acp_command),
                models=[],
            )
        else:
            agents[DEFAULT_AGENT_NAME] = AgentConfig(
                name=DEFAULT_AGENT_NAME,
                binary=DEFAULT_AGENT_BINARY,
                acp_command=list(DEFAULT_ACP_COMMAND),
                models=[],
            )
    return agents


def _resolve_agent_name(
    global_cfg: GlobalConfig | None,
    project_cfg: ProjectConfig | None,
    workflow: str | None,
) -> tuple[str, str]:
    if project_cfg and workflow and workflow in project_cfg.workflows:
        agent = project_cfg.workflows[workflow].agent
        if agent:
            return agent, "project.workflow"
    if global_cfg and workflow and workflow in global_cfg.workflows:
        agent = global_cfg.workflows[workflow].agent
        if agent:
            return agent, "global.workflow"
    if project_cfg and project_cfg.default_agent:
        return project_cfg.default_agent, "project.default"
    if global_cfg:
        return global_cfg.default_agent, "global.default"
    return DEFAULT_AGENT_NAME, "default"


def _resolve_model(
    global_cfg: GlobalConfig | None,
    project_cfg: ProjectConfig | None,
    workflow: str | None,
) -> tuple[str, str]:
    if project_cfg and workflow and workflow in project_cfg.workflows:
        model = project_cfg.workflows[workflow].model
        if model:
            return model, "project.workflow"
    if global_cfg and workflow and workflow in global_cfg.workflows:
        model = global_cfg.workflows[workflow].model
        if model:
            return model, "global.workflow"
    if project_cfg and project_cfg.model:
        return project_cfg.model, "project.default"
    if global_cfg:
        return global_cfg.model, "global.default"
    return DEFAULT_MODEL, "default"


def _resolve_permission_policy(
    global_cfg: GlobalConfig | None,
    project_cfg: ProjectConfig | None,
) -> tuple[str, str]:
    if project_cfg and project_cfg.permission_policy:
        return project_cfg.permission_policy, "project"
    if global_cfg:
        return global_cfg.permission_policy, "global"
    return DEFAULT_PERMISSION_POLICY, "default"


def _resolve_workspace(
    base_cwd: Path,
    project_cfg: ProjectConfig | None,
    workspace: Path | None,
) -> tuple[Path, str]:
    if workspace is not None:
        return workspace.resolve(), "argument"
    if project_cfg and project_cfg.workspace is not None:
        return project_cfg.workspace, "project"
    if project_cfg is not None:
        return project_cfg.project_root, "project_root"
    return base_cwd, "cwd"


def resolve_config(
    cwd: Path | None = None,
    *,
    workspace: Path | None = None,
    workflow: str | None = None,
    pulse_agent: str | None = None,
) -> ResolvedConfig:
    base_cwd = (cwd or Path.cwd()).resolve()
    global_cfg = load_global_config()
    project_cfg = load_project_config(base_cwd)

    agents = _merge_agents(global_cfg, project_cfg)
    workspace_dir, workspace_source = _resolve_workspace(base_cwd, project_cfg, workspace)

    if pulse_agent:
        agent_name, agent_source, model, model_source, permission_policy, policy_source = (
            _resolve_pulse_agent(
                pulse_agent,
                workspace_dir,
                agents,
                project_cfg,
                global_cfg,
            )
        )
    else:
        agent_name, agent_source = _resolve_agent_name(global_cfg, project_cfg, workflow)
        model, model_source = _resolve_model(global_cfg, project_cfg, workflow)
        permission_policy, policy_source = _resolve_permission_policy(global_cfg, project_cfg)

    agent = agents.get(agent_name) or agents[DEFAULT_AGENT_NAME]

    sources = {
        "agent": agent_source,
        "model": model_source,
        "permission_policy": policy_source,
        "workspace_dir": workspace_source,
    }

    if global_cfg:
        sources["auth_method"] = "global"
        auth_method = global_cfg.auth_method
    else:
        sources["auth_method"] = "default"
        auth_method = DEFAULT_AUTH_METHOD

    return ResolvedConfig(
        agent_name=agent.name,
        agent_binary=agent.binary,
        acp_command=list(agent.acp_command),
        auth_method=auth_method,
        model=model,
        permission_policy=permission_policy,
        workspace_dir=workspace_dir,
        workflow=workflow,
        pulse_agent=pulse_agent,
        agents=agents,
        sources=sources,
        global_config=global_cfg,
        project_config=project_cfg,
    )


def _resolve_pulse_agent(
    pulse_agent: str,
    workspace_dir: Path,
    runtimes: dict[str, AgentConfig],
    project_cfg: ProjectConfig | None,
    global_cfg: GlobalConfig | None,
) -> tuple[str, str, str, str, str, str]:
    from pulse.agents.loader import load_agent
    from pulse.store.agent_settings import load_agent_settings

    loaded = load_agent(pulse_agent, workspace=workspace_dir)
    runtime = loaded.runtime if loaded else "cursor"
    model = loaded.model if loaded else DEFAULT_MODEL
    policy = loaded.permission_policy if loaded else DEFAULT_PERMISSION_POLICY
    agent_source = "agent.file"
    model_source = "agent.file"
    policy_source = "agent.file"
    if project_cfg is not None:
        stored = load_agent_settings(project_cfg.project_id, pulse_agent)
        if stored.get("runtime"):
            runtime = str(stored["runtime"])
            agent_source = "agent.settings"
        if stored.get("model"):
            model = str(stored["model"])
            model_source = "agent.settings"
        if stored.get("permission_policy"):
            policy = str(stored["permission_policy"])
            policy_source = "agent.settings"
    if runtime not in runtimes and global_cfg and runtime in global_cfg.agents:
        runtime = runtime
    if runtime not in runtimes:
        runtime = DEFAULT_AGENT_NAME
        agent_source = "default"
    return runtime, agent_source, model, model_source, policy, policy_source
