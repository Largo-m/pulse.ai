from __future__ import annotations

from pathlib import Path

from pulse.acp.client import fetch_acp_available_models
from pulse.config.global_config import PERMISSION_POLICIES
from pulse.config.resolved import resolve_config
from pulse.store.paths import safe_cwd


def _default_models() -> list[str]:
    """Union of the models declared by each registered runtime."""
    from pulse.runtimes import all_runtimes

    models: list[str] = []
    for runtime in all_runtimes():
        for model in runtime.default_models:
            if model not in models:
                models.append(model)
    return models


DEFAULT_MODELS = _default_models()

PERMISSION_LABELS = {
    "ask": "Perguntar antes de cada permissão",
    "auto_approve": "Aprovar automaticamente",
    "deny_writes": "Permitir leitura e artefatos Pulse, bloquear escrita de código",
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
    base = (cwd or safe_cwd()).resolve()
    resolved = resolve_config(base)
    models: list[str] = []
    workspace = str(resolved.workspace_dir)
    seen_commands: set[tuple[str, ...]] = set()

    agents_to_query = list(resolved.agents.values())
    if agent_name:
        selected = resolved.agents.get(agent_name)
        agents_to_query = [selected] if selected is not None else []

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

    if not agent_name and resolved.model:
        _merge_unique_models(models, [resolved.model])

    for agent in agents_to_query:
        _merge_unique_models(models, agent.models)

    if models:
        return models
    if agent_name:
        return []
    return list(DEFAULT_MODELS)


def permission_choices() -> list[tuple[str, str]]:
    return [(key, PERMISSION_LABELS[key]) for key in PERMISSION_POLICIES]
