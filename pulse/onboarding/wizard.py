from __future__ import annotations

from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

from pulse.acp.client import AcpProbeResult, probe_acp_connection
from pulse.config import (
    GLOBAL_CONFIG_FILE,
    global_config_exists,
    init_project_config,
    load_global_config,
    mark_onboarding_complete,
    project_config_file,
)
from pulse.config.global_config import PERMISSION_POLICIES
from pulse.doctor.checks import CheckResult, check_agent_in_path, check_auth, find_agent_binary
from pulse.doctor.report import print_doctor_report, run_agent_login
from pulse.terminal.styles import MENU_STYLE
from pulse.terminal.tty import is_interactive

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


def _print_intro(console: Console) -> None:
    console.print()
    console.print(
        Panel(
            "Configure o Pulse para orquestrar workflows com o Cursor Agent via ACP.",
            title="[bold cyan]pulse init[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()


def _print_checks(checks: list[CheckResult], console: Console) -> None:
    print_doctor_report(checks, console=console)
    console.print()


def _resolve_auth_method(auth_check: CheckResult) -> str:
    if auth_check.detail == "api_key":
        return "api_key"
    return "cursor_login"


def _ensure_auth(console: Console, auth_check: CheckResult) -> CheckResult:
    if auth_check.status == "ok":
        return auth_check

    if not is_interactive():
        return auth_check

    choice = questionary.select(
        "Autenticação necessária. Como deseja continuar?",
        choices=[
            questionary.Choice("Executar `agent login`", value="login"),
            questionary.Choice("Informar CURSOR_API_KEY manualmente depois", value="skip"),
            questionary.Choice("Cancelar", value="cancel"),
        ],
        style=MENU_STYLE,
    ).ask()

    if choice == "cancel" or choice is None:
        return auth_check

    if choice == "login":
        console.print("[dim]Abrindo fluxo de login do Cursor…[/dim]")
        code = run_agent_login()
        if code != 0:
            questionary.print("Login não concluído.", style="fg:red")
            return auth_check
        return check_auth()

    questionary.print(
        "Exporte CURSOR_API_KEY e execute `pulse init` novamente.",
        style="fg:yellow",
    )
    return auth_check


def _run_acp_probe(console: Console, cwd: Path) -> AcpProbeResult:
    if not is_interactive():
        return probe_acp_connection(cwd=str(cwd))

    with console.status("[cyan]Testando conexão ACP…[/cyan]", spinner="dots"):
        return probe_acp_connection(
            cwd=str(cwd),
            on_status=lambda message: console.log(f"[dim]{message}[/dim]"),
        )


def _prompt_workspace_dir(default: Path) -> Path | None:
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


def _prompt_model(available: list[str]) -> str | None:
    choices = available or DEFAULT_MODELS
    unique: list[str] = []
    for item in choices:
        if item not in unique:
            unique.append(item)

    return questionary.select(
        "Modelo preferido:",
        choices=unique,
        style=MENU_STYLE,
    ).ask()


def _prompt_permission_policy() -> str | None:
    return questionary.select(
        "Política de permissões:",
        choices=[
            questionary.Choice(PERMISSION_LABELS[key], value=key)
            for key in PERMISSION_POLICIES
        ],
        style=MENU_STYLE,
    ).ask()


def run_onboarding_wizard(*, force: bool = False, console: Console | None = None) -> int:
    output = console or Console()

    if global_config_exists() and not force:
        existing = load_global_config()
        if existing and existing.is_onboarded:
            if not is_interactive():
                output.print(f"Config já existe em {GLOBAL_CONFIG_FILE}")
                return 0
            overwrite = questionary.confirm(
                f"Config já existe em {GLOBAL_CONFIG_FILE}. Reconfigurar?",
                default=False,
                style=MENU_STYLE,
            ).ask()
            if not overwrite:
                output.print("[dim]Onboarding cancelado.[/dim]")
                return 0

    if not is_interactive():
        output.print(
            "[pulse] Onboarding interativo requer um terminal TTY. "
            "Use variáveis de ambiente e crie o config manualmente.",
            style="red",
        )
        return 1

    _print_intro(output)

    agent_check = check_agent_in_path()
    auth_check = check_auth()
    _print_checks([agent_check, auth_check], output)

    if agent_check.status != "ok":
        questionary.print(
            "Instale o Cursor CLI e garanta que `agent` esteja no PATH.",
            style="fg:red",
        )
        return 1

    auth_check = _ensure_auth(output, auth_check)
    if auth_check.status != "ok":
        return 1

    default_workspace = Path.cwd()
    existing = load_global_config()
    if existing:
        default_workspace = existing.workspace_dir

    workspace = _prompt_workspace_dir(default_workspace)
    if workspace is None:
        output.print("[dim]Onboarding cancelado.[/dim]")
        return 130

    probe = _run_acp_probe(output, workspace)
    if probe.success:
        output.print(f"[green]✓[/green] {probe.message}")
        if probe.response_text:
            output.print(Panel(probe.response_text, title="Resposta do agente", border_style="green"))
    else:
        output.print(f"[red]✗[/red] {probe.error or probe.message}")
        continue_anyway = questionary.confirm(
            "Continuar sem teste ACP bem-sucedido?",
            default=False,
            style=MENU_STYLE,
        ).ask()
        if not continue_anyway:
            return 1

    model = _prompt_model(probe.available_models)
    if model is None:
        output.print("[dim]Onboarding cancelado.[/dim]")
        return 130

    policy = _prompt_permission_policy()
    if policy is None:
        output.print("[dim]Onboarding cancelado.[/dim]")
        return 130

    agent_binary = find_agent_binary() or "agent"
    config_path = mark_onboarding_complete(
        agent_binary=agent_binary,
        acp_command=[agent_binary, "acp"],
        auth_method=_resolve_auth_method(auth_check),
        workspace_dir=workspace,
        model=model,
        permission_policy=policy,
        acp_test_passed=probe.success,
    )

    output.print()
    output.print(f"[green]✓[/green] Config salvo em [cyan]{config_path}[/cyan]")

    project_path = project_config_file(workspace)
    if project_path.is_file():
        output.print(f"[dim]Config de projeto já existe em {project_path}[/dim]")
    else:
        created = init_project_config(workspace)
        output.print(f"[green]✓[/green] Config de projeto criada em [cyan]{created}[/cyan]")

    output.print()
    output.print("[bold]Próximos passos[/bold]")
    output.print("  pulse doctor          Verificar ambiente")
    output.print("  pulse config          Ver config efetiva")
    output.print('  pulse plan "..."      Iniciar pipeline')
    output.print()
    return 0
