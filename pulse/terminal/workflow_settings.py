from __future__ import annotations

from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from pulse.config import (
    resolve_config,
    update_global_workflow,
    update_project_workflow,
)
from pulse.plan.spec_types import SPEC_TYPES, get_spec_type
from pulse.terminal.prompts import prompt_agent, prompt_config_scope, prompt_model
from pulse.terminal.styles import MENU_STYLE


def _workflow_choice_label(workflow_id: str, base: Path) -> str:
    spec = get_spec_type(workflow_id)
    title = spec.label if spec else workflow_id
    resolved = resolve_config(base, workflow=workflow_id)
    return f"{title} — {resolved.agent_name} · {resolved.model}"


def _print_workflow_summary(base: Path, console: Console) -> None:
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Workflow")
    table.add_column("Agente")
    table.add_column("Modelo")
    table.add_column("Origem", style="dim")

    for spec in SPEC_TYPES:
        resolved = resolve_config(base, workflow=spec.id)
        table.add_row(
            spec.label,
            resolved.agent_name,
            resolved.model,
            resolved.sources.get("agent", ""),
        )

    console.print(table)
    console.print()


def _save_workflow_agent(
    *,
    scope: str,
    base: Path,
    workflow_id: str,
    agent: str,
) -> Path | None:
    if scope == "global":
        return update_global_workflow(workflow_id, agent=agent)
    return update_project_workflow(base, workflow_id, agent=agent)


def _save_workflow_model(
    *,
    scope: str,
    base: Path,
    workflow_id: str,
    model: str,
) -> Path | None:
    if scope == "global":
        return update_global_workflow(workflow_id, model=model)
    return update_project_workflow(base, workflow_id, model=model)


def _configure_workflow_agent(
    *,
    scope: str,
    base: Path,
    workflow_id: str,
    console: Console,
) -> None:
    resolved = resolve_config(base, workflow=workflow_id)
    agent = prompt_agent(resolved.agents, current=resolved.agent_name)
    if agent is None:
        return

    path = _save_workflow_agent(
        scope=scope,
        base=base,
        workflow_id=workflow_id,
        agent=agent,
    )
    if path is None:
        return

    console.print(
        f"[green]✓[/green] Agente do workflow [cyan]{workflow_id}[/cyan] "
        f"atualizado para [cyan]{agent}[/cyan]"
    )
    console.print(f"[dim]{path}[/dim]")


def _configure_workflow_model(
    *,
    scope: str,
    base: Path,
    workflow_id: str,
    console: Console,
) -> None:
    resolved = resolve_config(base, workflow=workflow_id)
    model = prompt_model(
        base,
        current=resolved.model,
        console=console,
        agent_name=resolved.agent_name,
        label="Modelo do workflow:",
    )
    if model is None:
        return

    path = _save_workflow_model(
        scope=scope,
        base=base,
        workflow_id=workflow_id,
        model=model,
    )
    if path is None:
        return

    console.print(
        f"[green]✓[/green] Modelo do workflow [cyan]{workflow_id}[/cyan] "
        f"atualizado para [cyan]{model}[/cyan]"
    )
    console.print(f"[dim]{path}[/dim]")


def _edit_single_workflow(
    *,
    scope: str,
    base: Path,
    workflow_id: str,
    console: Console,
) -> None:
    spec = get_spec_type(workflow_id)
    title = spec.label if spec else workflow_id

    while True:
        resolved = resolve_config(base, workflow=workflow_id)
        console.print()
        console.print(f"[bold cyan]{title}[/bold cyan] [dim]({workflow_id})[/dim]")
        console.print(
            f"  Agente: [cyan]{resolved.agent_name}[/cyan] "
            f"[dim]({resolved.sources.get('agent', '')})[/dim]"
        )
        console.print(
            f"  Modelo: [cyan]{resolved.model}[/cyan] "
            f"[dim]({resolved.sources.get('model', '')})[/dim]"
        )
        console.print()

        choice = questionary.select(
            "O que deseja alterar?",
            choices=[
                questionary.Choice("Agente", value="agent"),
                questionary.Choice("Modelo", value="model"),
                questionary.Choice("Voltar", value="back"),
            ],
            style=MENU_STYLE,
            use_indicator=True,
            use_shortcuts=True,
        ).ask()

        if choice is None or choice == "back":
            return

        if choice == "agent":
            _configure_workflow_agent(
                scope=scope,
                base=base,
                workflow_id=workflow_id,
                console=console,
            )
            continue

        if choice == "model":
            _configure_workflow_model(
                scope=scope,
                base=base,
                workflow_id=workflow_id,
                console=console,
            )


def run_workflow_settings(
    base: Path,
    console: Console,
    *,
    scope: str,
) -> None:
    while True:
        console.print()
        _print_workflow_summary(base, console)

        workflow_choices = [
            questionary.Choice(_workflow_choice_label(spec.id, base), value=spec.id)
            for spec in SPEC_TYPES
        ]
        workflow_choices.append(questionary.Choice("Voltar", value="back"))

        workflow_id = questionary.select(
            "Selecione o workflow:",
            choices=workflow_choices,
            style=MENU_STYLE,
            use_indicator=True,
            use_shortcuts=len(workflow_choices) <= 9,
        ).ask()

        if workflow_id is None or workflow_id == "back":
            return

        _edit_single_workflow(
            scope=scope,
            base=base,
            workflow_id=workflow_id,
            console=console,
        )


def configure_workflows(base: Path, console: Console) -> None:
    from pulse.config import global_config_exists

    scope = prompt_config_scope(base)
    if scope is None:
        return

    if scope == "global":
        if not global_config_exists():
            questionary.print(
                "Config global não encontrada. Use Configurar Pulse no menu principal.",
                style="fg:yellow",
            )
            console.print()
            return

    run_workflow_settings(base, console, scope=scope)
