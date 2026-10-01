from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pulse.config.agents import DEFAULT_AGENT_NAME, AgentConfig
from pulse.config.global_config import GlobalConfig, load_global_config
from pulse.config.project_config import ProjectConfig, load_project_config

from pulse.runtimes import DEFAULT_RUNTIME_ID, all_runtimes, find_runtime, get_runtime

_DEFAULT_RUNTIME = get_runtime(DEFAULT_RUNTIME_ID)

DEFAULT_ACP_COMMAND = _DEFAULT_RUNTIME.acp_command
DEFAULT_MODEL = "auto"
DEFAULT_PERMISSION_POLICY = "ask"
DEFAULT_AGENT_BINARY = _DEFAULT_RUNTIME.binary
DEFAULT_AUTH_METHOD = _DEFAULT_RUNTIME.auth_method_label


@dataclass(frozen=True)
class ResolvedConfig:
    agent_name: str
    agent_binary: str
    acp_command: list[str]
    auth_method: str
    model: str
    permission_policy: str
    workspace_dir: Path
    #: Cada run abre o próprio `git worktree`. Não tem cascata: vem do projeto
    #: ou não vem — a máquina não decide isolar o repositório de ninguém.
    use_worktree: bool = False
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
    project_cfg = load_project_config(workspace.resolve() if workspace is not None else base_cwd)
    if project_cfg is None and workspace is not None:
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
        # Só um runtime do registry pode ser julgado indisponível: um agente
        # declarado à mão no config tem binário próprio, e `get_runtime` devolve
        # o default para nome desconhecido — checar a disponibilidade dele seria
        # checar a do Cursor.
        if find_runtime(agent_name) is not None:
            fallback = _available_runtime_fallback(agent_name, project_cfg, global_cfg)
            if fallback is not None and fallback in agents:
                agent_name, agent_source = fallback, "runtime.fallback"

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
        use_worktree=bool(project_cfg.use_worktree) if project_cfg else False,
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
    """Runtime, model e policy de um agente do banco.

    Campo vazio na definição significa "use o padrão" — e não o default do
    código, mas o que a máquina/projeto já resolveram. Gravar um runtime
    concreto na semente congelaria a escolha feita no `pulse init`.
    """
    from pulse.store.agent_settings import load_agent_settings
    from pulse.store.workflow_defs import get_agent

    definition = get_agent(pulse_agent)
    default_runtime, default_runtime_source = _resolve_agent_name(global_cfg, project_cfg, None)
    default_model, default_model_source = _resolve_model(global_cfg, project_cfg, None)
    default_policy, default_policy_source = _resolve_permission_policy(global_cfg, project_cfg)

    runtime = (definition.runtime if definition else "") or default_runtime
    model = (definition.model if definition else "") or default_model
    policy = (definition.permission_policy if definition else "") or default_policy
    agent_source = "agent" if definition and definition.runtime else default_runtime_source
    model_source = "agent" if definition and definition.model else default_model_source
    policy_source = (
        "agent" if definition and definition.permission_policy else default_policy_source
    )
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
    if runtime not in runtimes:
        runtime = DEFAULT_AGENT_NAME
        agent_source = "default"

    fallback = _available_runtime_fallback(runtime, project_cfg, global_cfg)
    if fallback is not None:
        runtime, agent_source = fallback, "runtime.fallback"
    return runtime, agent_source, model, model_source, policy, policy_source


def _available_runtime_fallback(
    runtime: str,
    project_cfg: ProjectConfig | None,
    global_cfg: GlobalConfig | None,
) -> str | None:
    """Runtime alternativo quando o declarado não existe nesta máquina.

    O runtime escolhido — no agente, no projeto ou na máquina — é preferência,
    não requisito: quem só tem o Claude instalado não deve ficar travado porque
    a preferência diz `cursor`. Vale para os dois caminhos de resolução; se só o
    do agente caísse aqui, o pré-voo do orquestrador reprovaria a run inteira
    por um runtime que nenhum step ia usar. O modelo é preservado — se o id não
    existir no runtime novo, o próprio agente cai no default dele.
    """
    if get_runtime(runtime).is_available():
        return None

    preferred = None
    if project_cfg and project_cfg.default_agent:
        preferred = project_cfg.default_agent
    elif global_cfg and global_cfg.default_agent:
        preferred = global_cfg.default_agent

    candidates = [preferred, *(item.id for item in all_runtimes())]
    for candidate in candidates:
        if not candidate or candidate == runtime:
            continue
        if get_runtime(candidate).is_available():
            return candidate
    return None
