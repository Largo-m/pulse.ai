"""[pulse.domain.ports.AgentProfiles] from the user's config and the agent definitions."""

from __future__ import annotations

from pathlib import Path

from pulse.config.resolved import resolve_config
from pulse.domain.ports import AgentProfile
from pulse.store.workflow_defs import get_agent


class ConfiguredAgentProfiles:
    """Resolves each step's agent in the project the run belongs to.

    `fallback_model` is the run's model, used when neither the agent nor the
    config names one.
    """

    def __init__(self, workspace: Path, *, fallback_model: str | None) -> None:
        self._workspace = workspace
        self._fallback_model = fallback_model

    def profile(self, agent_id: str) -> AgentProfile:
        resolved = resolve_config(workspace=self._workspace, pulse_agent=agent_id)
        definition = get_agent(agent_id)
        return AgentProfile(
            agent_id=agent_id,
            model=resolved.model or self._fallback_model,
            permission_policy=resolved.permission_policy,
            instructions=definition.instructions.strip() if definition is not None else "",
            runtime_id=resolved.runtime.id,
            acp_command=tuple(resolved.acp_command),
            dialect=resolved.runtime,
        )
