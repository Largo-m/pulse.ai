from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from pulse.config.paths import find_project_config_file
from pulse.config.project_config import init_project_config
from pulse.config.resolved import resolve_config


def run_config_command(
    *,
    action: str = "show",
    workflow: str | None = None,
    console: Console | None = None,
    cwd: Path | None = None,
) -> int:
    output = console or Console()
    base = (cwd or Path.cwd()).resolve()
    if action == "init":
        return _init_project(output, base)
    return _show(output, base, workflow)


def _show(output: Console, base: Path, workflow: str | None) -> int:
    resolved = resolve_config(base, workflow=workflow)

    title = "Config efetiva"
    if workflow:
        title += f" · workflow [bold]{workflow}[/bold]"
    output.print(f"[bold cyan]{title}[/bold cyan]")

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Campo")
    table.add_column("Valor")
    table.add_column("Origem", style="dim")
    table.add_row("agent", resolved.agent_name, resolved.sources.get("agent", ""))
    table.add_row("model", resolved.model, resolved.sources.get("model", ""))
    table.add_row(
        "permission_policy",
        resolved.permission_policy,
        resolved.sources.get("permission_policy", ""),
    )
    table.add_row(
        "workspace_dir",
        str(resolved.workspace_dir),
        resolved.sources.get("workspace_dir", ""),
    )
    table.add_row("acp_command", " ".join(resolved.acp_command), resolved.agent_name)
    output.print(table)

    if resolved.agents:
        output.print()
        agents_table = Table(
            show_header=True,
            header_style="bold",
            box=None,
            padding=(0, 1),
            title="Agentes",
            title_justify="left",
        )
        agents_table.add_column("Nome")
        agents_table.add_column("Comando ACP")
        agents_table.add_column("Modelos", style="dim")
        for name, agent in resolved.agents.items():
            agents_table.add_row(
                name,
                " ".join(agent.acp_command),
                ", ".join(agent.models) or "—",
            )
        output.print(agents_table)

    if resolved.project_config is not None:
        output.print(f"\n[dim]Config de projeto: {resolved.project_config.source_file}[/dim]")
    else:
        output.print(
            "\n[dim]Nenhuma config de projeto (.pulse/config.yaml). "
            "Use `pulse config init`.[/dim]"
        )
    return 0


def _init_project(output: Console, base: Path) -> int:
    existing = find_project_config_file(base)
    if existing is not None and existing.parent.parent == base:
        output.print(f"[yellow]Config de projeto já existe em[/yellow] {existing}")
        return 0

    path = init_project_config(base)
    output.print(f"[green]✓[/green] Config de projeto criada em [cyan]{path}[/cyan]")
    output.print("[dim]Edite o arquivo para ajustar agentes, modelos e workflows.[/dim]")
    return 0
