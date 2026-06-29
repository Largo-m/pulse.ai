from __future__ import annotations

from pathlib import Path

import questionary
from rich.console import Console

from pulse.config import (
    global_config_exists,
    load_global_config,
    load_project_config,
    resolve_config,
    update_global_defaults,
    update_project_defaults,
)
from pulse.doctor import run_doctor
from pulse.terminal.prompts import prompt_config_scope, prompt_model, prompt_permission_policy
from pulse.terminal.styles import MENU_STYLE
from pulse.terminal.workflow_settings import configure_workflows


def _ensure_global_config(console: Console) -> bool:
    if global_config_exists():
        return True
    questionary.print(
        "Config global não encontrada. Use Configurar Pulse no menu principal.",
        style="fg:yellow",
    )
    console.print()
    return False


def _configure_model(base: Path, console: Console) -> None:
    scope = prompt_config_scope(base)
    if scope is None:
        return

    if scope == "global":
        if not _ensure_global_config(console):
            return
        global_cfg = load_global_config()
        current = global_cfg.model if global_cfg else None
        model = prompt_model(base, current=current, console=console)
        if model is None:
            return
        path = update_global_defaults(model=model)
        if path is None:
            return
        console.print(f"[green]✓[/green] Modelo global atualizado para [cyan]{model}[/cyan]")
        console.print(f"[dim]{path}[/dim]")
        return

    project_cfg = load_project_config(base)
    current = project_cfg.model if project_cfg else None
    if project_cfg is None:
        resolved = resolve_config(base)
        current = resolved.model
    model = prompt_model(base, current=current, console=console)
    if model is None:
        return
    path = update_project_defaults(base, model=model)
    console.print(f"[green]✓[/green] Modelo do projeto atualizado para [cyan]{model}[/cyan]")
    console.print(f"[dim]{path}[/dim]")


def _configure_permissions(base: Path, console: Console) -> None:
    scope = prompt_config_scope(base)
    if scope is None:
        return

    if scope == "global":
        if not _ensure_global_config(console):
            return
        global_cfg = load_global_config()
        current = global_cfg.permission_policy if global_cfg else None
        policy = prompt_permission_policy(current=current)
        if policy is None:
            return
        path = update_global_defaults(permission_policy=policy)
        if path is None:
            return
        console.print(
            f"[green]✓[/green] Permissões globais atualizadas para [cyan]{policy}[/cyan]"
        )
        console.print(f"[dim]{path}[/dim]")
        return

    project_cfg = load_project_config(base)
    current = project_cfg.permission_policy if project_cfg else None
    if project_cfg is None:
        resolved = resolve_config(base)
        current = resolved.permission_policy
    policy = prompt_permission_policy(current=current)
    if policy is None:
        return
    path = update_project_defaults(base, permission_policy=policy)
    console.print(
        f"[green]✓[/green] Permissões do projeto atualizadas para [cyan]{policy}[/cyan]"
    )
    console.print(f"[dim]{path}[/dim]")


def run_settings_menu(*, cwd: Path | None = None, console: Console | None = None) -> int:
    output = console or Console()
    base = (cwd or Path.cwd()).resolve()

    while True:
        output.print()
        choice = questionary.select(
            "Configurações:",
            choices=[
                questionary.Choice("Modelo", value="model"),
                questionary.Choice("Permissões", value="permissions"),
                questionary.Choice("Workflows", value="workflows"),
                questionary.Choice("Verificar ambiente", value="doctor"),
                questionary.Choice("Voltar", value="back"),
            ],
            style=MENU_STYLE,
            use_indicator=True,
            use_shortcuts=True,
        ).ask()

        if choice is None or choice == "back":
            return 0

        if choice == "model":
            _configure_model(base, output)
            continue

        if choice == "permissions":
            _configure_permissions(base, output)
            continue

        if choice == "workflows":
            configure_workflows(base, output)
            continue

        if choice == "doctor":
            output.print()
            run_doctor(test_acp=False, console=output)
            output.print()

    return 0
