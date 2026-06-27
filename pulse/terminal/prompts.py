from __future__ import annotations

from pathlib import Path

import questionary
from rich.console import Console

from pulse.acp.client import fetch_acp_available_models
from pulse.config.global_config import PERMISSION_POLICIES
from pulse.config.paths import find_project_config_file
from pulse.config.resolved import resolve_config
from pulse.terminal.styles import MENU_STYLE

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
    console: Console | None = None,
) -> list[str]:
    base = (cwd or Path.cwd()).resolve()
    resolved = resolve_config(base)
    models: list[str] = []
    workspace = str(resolved.workspace_dir)
    seen_commands: set[tuple[str, ...]] = set()

    def load_from_acp() -> None:
        for agent in resolved.agents.values():
            command_key = tuple(agent.acp_command)
            if command_key in seen_commands:
                continue
            seen_commands.add(command_key)
            acp_models = fetch_acp_available_models(
                command=list(agent.acp_command),
                cwd=workspace,
            )
            _merge_unique_models(models, acp_models)

    if console is not None:
        with console.status("[cyan]Carregando modelos disponíveis…[/cyan]", spinner="dots"):
            load_from_acp()
    else:
        load_from_acp()

    if resolved.model:
        _merge_unique_models(models, [resolved.model])

    for agent in resolved.agents.values():
        _merge_unique_models(models, agent.models)

    if models:
        return models

    return list(DEFAULT_MODELS)


def prompt_config_scope(cwd: Path | None = None) -> str | None:
    base = (cwd or Path.cwd()).resolve()
    project_file = find_project_config_file(base)
    if project_file is not None:
        try:
            project_label = f"Projeto ({project_file.relative_to(base)})"
        except ValueError:
            project_label = f"Projeto ({project_file})"
    else:
        project_label = "Projeto (.pulse/config.yaml)"
    return questionary.select(
        "Aplicar em:",
        choices=[
            questionary.Choice("Global (~/.pulse/config.toml)", value="global"),
            questionary.Choice(project_label, value="project"),
        ],
        style=MENU_STYLE,
        use_indicator=True,
    ).ask()


def prompt_model(
    cwd: Path | None = None,
    *,
    current: str | None = None,
    choices: list[str] | None = None,
    label: str = "Modelo:",
    console: Console | None = None,
) -> str | None:
    options = choices
    if options is None:
        options = collect_available_models(cwd, console=console)
    if current and current not in options:
        options = [current, *options]
    return questionary.select(
        label,
        choices=options,
        default=current if current in options else None,
        style=MENU_STYLE,
        use_indicator=True,
    ).ask()


def prompt_permission_policy(*, current: str | None = None) -> str | None:
    choices = [
        questionary.Choice(PERMISSION_LABELS[key], value=key)
        for key in PERMISSION_POLICIES
    ]
    return questionary.select(
        "Política de permissões:",
        choices=choices,
        default=current if current in PERMISSION_POLICIES else None,
        style=MENU_STYLE,
        use_indicator=True,
    ).ask()


def prompt_workspace_dir(default: Path) -> Path | None:
    while True:
        value = questionary.path(
            "Diretório para testar conexão ACP (pasta do seu projeto):",
            default=str(default),
            style=MENU_STYLE,
        ).ask()
        if value is None:
            return None
        path = Path(value).expanduser()
        if not path.is_dir():
            questionary.print("Diretório inválido. Escolha uma pasta existente.", style="fg:yellow")
            continue
        return path.resolve()
