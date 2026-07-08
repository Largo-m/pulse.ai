from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config import resolve_config
from pulse.doctor.checks import check_agent_in_path, check_auth
from pulse.plan.legacy_cleanup import cleanup_legacy_pulse_questions
from pulse.plan.quick_prompt import (
    TLC_SPEC_SKILL,
    build_quick_plan_prompt,
    resolve_quick_skill,
)
from pulse.presentation.prompt.handler import PromptHandler
from pulse.presentation.stream_renderer import StreamRenderer
from pulse.terminal.tty import is_interactive


def run_quick(*, user_prompt: str, workspace: Path | None = None) -> int:
    if not is_interactive():
        print("[pulse] Quick mode requer terminal interativo.", file=sys.stderr)
        return 1

    agent_check = check_agent_in_path()
    auth_check = check_auth()
    if agent_check.status != "ok" or auth_check.status != "ok":
        print("[pulse] Corrija agent e autenticação antes de iniciar.", file=sys.stderr)
        return 1

    resolved = resolve_config(workspace=workspace, workflow="fix-bug")
    workspace_root = resolved.workspace_dir
    permission_policy = resolved.permission_policy
    acp_command = resolved.acp_command
    preferred_model = resolved.model

    cleanup_legacy_pulse_questions(workspace=workspace_root, skill_id=TLC_SPEC_SKILL)

    try:
        skill_dir = resolve_quick_skill()
    except FileNotFoundError as error:
        print(f"[pulse] {error}", file=sys.stderr)
        return 1

    plan_prompt = build_quick_plan_prompt(
        workspace=workspace_root,
        user_prompt=user_prompt,
        skill_dir=skill_dir,
    )

    console = Console(highlight=False, soft_wrap=True)
    console.print()
    console.print(
        Panel(
            f"Skill: tlc-spec-driven\nWorkspace: {workspace_root}\nTarefa: {user_prompt.strip() or '—'}",
            title="[bold cyan]Quick mode[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    runner = AcpSessionRunner(
        acp_command,
        cwd=str(workspace_root),
        permission_policy=permission_policy,
        stream=StreamRenderer(console),
        prompt_handler=PromptHandler(console=console),
    )

    try:
        result = runner.run_quick(
            plan_prompt=plan_prompt,
            workspace=workspace_root,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            preferred_model=preferred_model,
        )
    except (RuntimeError, TimeoutError, OSError) as error:
        console.print(f"[red]Falha na sessão ACP:[/red] {error}")
        return 1

    stop_reason = result.get("stopReason", "end_turn")
    ask_count = int(result.get("askQuestionCount", 0))
    approved = bool(result.get("approved", False))
    outcome = str(result.get("outcome", ""))
    console.print()
    if stop_reason == "cancelled" or outcome == "cancelled":
        console.print("[yellow]Quick task cancelada.[/yellow]")
        return 1

    if outcome == "cancel":
        console.print("[yellow]Operação cancelada pelo usuário.[/yellow]")
        return 0

    if not approved:
        if outcome == "migrate":
            console.print("[cyan]Migração para pipeline completo registrada.[/cyan]")
            console.print("[dim]Siga as orientações do agente acima para iniciar Specify.[/dim]")
        elif outcome in {"reduce_scope", "adjust", "continue"}:
            console.print("[yellow]Escolha registrada — aguardando próximo passo do agente.[/yellow]")
            console.print("[dim]Se o plano exigir nova aprovação, responda no terminal.[/dim]")
        else:
            console.print("[yellow]Quick task não aprovada — nenhuma alteração de código aplicada.[/yellow]")
            console.print("[dim]Revise o plano em .pulse/specs/quick/ ou rode novamente com escopo menor.[/dim]")
        return 0

    console.print(f"[green]✓[/green] Quick task concluída ({stop_reason})")
    if ask_count:
        console.print(f"[dim]{ask_count} pergunta(s) respondida(s) no terminal[/dim]")
    console.print("[dim]Artefatos esperados em .pulse/specs/quick/[/dim]")
    return 0
