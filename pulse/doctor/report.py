from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from pulse.acp.client import probe_acp_connection
from pulse.config import (
    GLOBAL_CONFIG_FILE,
    global_config_exists,
    load_global_config,
    load_project_config,
)
from pulse.doctor.checks import CheckResult, run_environment_checks


def _status_style(status: str) -> str:
    if status == "ok":
        return "green"
    if status == "warn":
        return "yellow"
    return "red"


def _status_icon(status: str) -> str:
    if status == "ok":
        return "✓"
    if status == "warn":
        return "!"
    return "✗"


def print_doctor_report(
    checks: list[CheckResult],
    *,
    console: Console | None = None,
    acp_probe_message: str | None = None,
) -> None:
    output = console or Console()
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Status", width=6)
    table.add_column("Verificação")
    table.add_column("Detalhe", style="dim")

    for check in checks:
        table.add_row(
            f"[{_status_style(check.status)}]{_status_icon(check.status)}[/]",
            check.message,
            check.detail or "",
        )

    if acp_probe_message:
        table.add_row("", "Teste ACP", acp_probe_message)

    output.print(table)


def run_doctor(*, test_acp: bool = False, console: Console | None = None) -> int:
    output = console or Console()
    checks = run_environment_checks()
    acp_message: str | None = None

    if global_config_exists():
        config = load_global_config()
        if config:
            global_detail = f"modelo={config.model}, permissões={config.permission_policy}"
            if config.agents:
                global_detail += f", agentes={len(config.agents)}"
            if config.workflows:
                global_detail += f", workflows={len(config.workflows)}"
            checks.append(
                CheckResult(
                    name="Config global",
                    status="ok",
                    message=f"Config em {GLOBAL_CONFIG_FILE}",
                    detail=global_detail,
                )
            )

    project = load_project_config()
    if project is not None:
        overrides = []
        if project.default_agent:
            overrides.append(f"agent={project.default_agent}")
        if project.model:
            overrides.append(f"modelo={project.model}")
        if project.permission_policy:
            overrides.append(f"permissões={project.permission_policy}")
        if project.workspace:
            overrides.append(f"workspace={project.workspace}")
        if project.agents:
            overrides.append(f"agentes={len(project.agents)}")
        if project.workflows:
            overrides.append(f"workflows={len(project.workflows)}")
        checks.append(
            CheckResult(
                name="Config projeto",
                status="ok",
                message=f"Config em {project.source_file}",
                detail=", ".join(overrides) or "sem overrides",
            )
        )

    if test_acp:
        agent_ok = any(check.name == "Agent CLI" and check.status == "ok" for check in checks)
        auth_ok = any(check.name == "Autenticação" and check.status == "ok" for check in checks)
        if agent_ok and auth_ok:
            output.print("[dim]Testando conexão ACP…[/dim]")
            cwd = str(Path.cwd())
            probe = probe_acp_connection(cwd=cwd)
            acp_message = probe.message if probe.success else probe.error or probe.message
            checks.append(
                CheckResult(
                    name="ACP",
                    status="ok" if probe.success else "fail",
                    message=probe.message,
                    detail=probe.response_text[:120] if probe.response_text else None,
                )
            )
        else:
            checks.append(
                CheckResult(
                    name="ACP",
                    status="warn",
                    message="Teste ACP ignorado",
                    detail="Corrija agent e autenticação antes",
                )
            )

    print_doctor_report(checks, console=output, acp_probe_message=acp_message)
    failed = any(check.status == "fail" for check in checks)
    return 1 if failed else 0


def run_agent_login() -> int:
    binary = "agent"
    try:
        completed = subprocess.run([binary, "login"], check=False)
    except OSError as error:
        print(f"[pulse] Não foi possível executar `agent login`: {error}", file=sys.stderr)
        return 1
    return completed.returncode
