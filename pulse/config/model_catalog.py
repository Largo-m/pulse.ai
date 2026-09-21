from __future__ import annotations

from pathlib import Path

from pulse.acp.client import fetch_acp_available_models
from pulse.config.global_config import PERMISSION_POLICIES
from pulse.config.resolved import resolve_config

DEFAULT_MODELS = [
    "Auto",
    "claude-sonnet-4-6",
    "gpt-5.5",
    "composer-2.5",
]

PERMISSION_LABELS = {
    "ask": "Perguntar antes de cada permissão",
    "auto_approve": "Aprovar automaticamente",
    "deny_writes": "Permitir leitura, bloquear escrita",
}


def _merge_unique_models(models: list[str], items: list[str]) -> None:
    for item in items:
        if item and item not in models:
            models.append(item)


def collect_available_models(
    cwd: Path | None = None,
    *,
    agent_name: str | None = None,
) -> list[str]:
    base = (cwd or Path.cwd()).resolve()
    resolved = resolve_config(base)
    models: list[str] = []
    workspace = str(resolved.workspace_dir)
    seen_commands: set[tuple[str, ...]] = set()

    agents_to_query = list(resolved.agents.values())
    if agent_name and agent_name in resolved.agents:
        agents_to_query = [resolved.agents[agent_name]]

    for agent in agents_to_query:
        command_key = tuple(agent.acp_command)
        if command_key in seen_commands:
            continue
        seen_commands.add(command_key)
        acp_models = fetch_acp_available_models(
            command=list(agent.acp_command),
            cwd=workspace,
        )
        _merge_unique_models(models, acp_models)

    if resolved.model:
        _merge_unique_models(models, [resolved.model])

    for agent in agents_to_query:
        _merge_unique_models(models, agent.models)

    if models:
        return models
    return list(DEFAULT_MODELS)


def permission_choices() -> list[tuple[str, str]]:
    return [(key, PERMISSION_LABELS[key]) for key in PERMISSION_POLICIES]
