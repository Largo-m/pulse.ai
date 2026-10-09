from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_AGENT_NAME = "default"


@dataclass(frozen=True)
class AgentConfig:
    name: str
    binary: str
    acp_command: list[str]
    models: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowConfig:
    agent: str | None = None
    model: str | None = None


def default_acp_command(name: str, binary: str) -> list[str]:
    """ACP command used when the config has no explicit `acp_command`."""
    from pulse.runtimes import find_runtime

    runtime = find_runtime(name) or find_runtime(binary)
    if runtime is not None:
        return list(runtime.acp_command)
    return [binary, "acp"]


def parse_agents(raw: object) -> dict[str, AgentConfig]:
    if not isinstance(raw, dict):
        return {}
    agents: dict[str, AgentConfig] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        binary = str(spec.get("binary", name))
        acp_command = spec.get("acp_command")
        if isinstance(acp_command, list) and acp_command:
            command = [str(part) for part in acp_command]
        else:
            command = default_acp_command(str(name), binary)
        models_raw = spec.get("models")
        models = [str(model) for model in models_raw] if isinstance(models_raw, list) else []
        agents[str(name)] = AgentConfig(
            name=str(name),
            binary=binary,
            acp_command=command,
            models=models,
        )
    return agents


def parse_workflows(raw: object) -> dict[str, WorkflowConfig]:
    if not isinstance(raw, dict):
        return {}
    workflows: dict[str, WorkflowConfig] = {}
    for workflow_id, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        agent = spec.get("agent")
        model = spec.get("model")
        workflows[str(workflow_id)] = WorkflowConfig(
            agent=str(agent) if agent else None,
            model=str(model) if model else None,
        )
    return workflows


def default_global_agents() -> dict[str, AgentConfig]:
    """One AgentConfig per registered runtime."""
    from pulse.runtimes import all_runtimes

    return {
        runtime.id: AgentConfig(
            name=runtime.id,
            binary=runtime.binary,
            acp_command=list(runtime.acp_command),
            models=list(runtime.default_models),
        )
        for runtime in all_runtimes()
    }


def default_global_workflows() -> dict[str, WorkflowConfig]:
    """None. A workflow only exists if it is in the `workflow_defs` DB table.

    This mapping overrides agent/model per workflow id; seeding an id here would
    make Pulse claim to know a pipeline it does not define.
    """
    return {}
