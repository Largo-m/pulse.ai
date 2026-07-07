from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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


def parse_agents(raw: Any) -> dict[str, AgentConfig]:
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
            command = [binary, "acp"]
        models_raw = spec.get("models")
        models = [str(model) for model in models_raw] if isinstance(models_raw, list) else []
        agents[str(name)] = AgentConfig(
            name=str(name),
            binary=binary,
            acp_command=command,
            models=models,
        )
    return agents


def parse_workflows(raw: Any) -> dict[str, WorkflowConfig]:
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
    return {
        "cursor": AgentConfig(
            name="cursor",
            binary="agent",
            acp_command=["agent", "acp"],
            models=["Auto", "gpt-5.5"],
        ),
        "claude": AgentConfig(
            name="claude",
            binary="claude-code",
            acp_command=["claude-code", "acp"],
            models=["claude-opus-4.8"],
        ),
    }


def default_global_workflows() -> dict[str, WorkflowConfig]:
    return {
        "setup-project": WorkflowConfig(agent="claude", model="claude-opus-4.8"),
        "analyze-codebase": WorkflowConfig(agent="cursor", model="gpt-5.5"),
        "fix-bug": WorkflowConfig(agent="cursor", model="gpt-5.5"),
    }
