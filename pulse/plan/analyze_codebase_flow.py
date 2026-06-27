from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config import resolve_config
from pulse.doctor.checks import check_agent_in_path, check_auth
from pulse.plan.analyze_codebase_prompt import (
    TLC_SPEC_SKILL,
    build_analyze_codebase_prompt,
    resolve_analyze_codebase_skill,
)
from pulse.plan.legacy_cleanup import cleanup_legacy_pulse_questions
from pulse.presentation.prompt.handler import PromptHandler
from pulse.presentation.stream_renderer import StreamRenderer
from pulse.terminal.tty import is_interactive


def run_analyze_codebase(*, user_prompt: str, workspace: Path | None = None) -> int:
    if not is_interactive():
        print("[pulse] Analyze codebase requer terminal interativo.", file=sys.stderr)
        return 1

    agent_check = check_agent_in_path()
    auth_check = check_auth()
    if agent_check.status != "ok" or auth_check.status != "ok":
        print("[pulse] Corrija agent e autenticação antes de iniciar.", file=sys.stderr)
        return 1

    resolved = resolve_config(workspace=workspace, workflow="analyze-codebase")
    workspace_root = resolved.workspace_dir
    permission_policy = resolved.permission_policy
    acp_command = resolved.acp_command
    preferred_model = resolved.model

    cleanup_legacy_pulse_questions(workspace=workspace_root, skill_id=TLC_SPEC_SKILL)

    try:
        _, documents = resolve_analyze_codebase_skill()
    except FileNotFoundError as error:
        print(f"[pulse] {error}", file=sys.stderr)
        return 1

    explore_prompt = build_analyze_codebase_prompt(
        workspace=workspace_root,
        user_prompt=user_prompt,
        documents=documents,
    )

    console = Console(highlight=False, soft_wrap=True)
    console.print()
    console.print(
        Panel(
            f"Skill: tlc-spec-driven\nWorkspace: {workspace_root}",
            title="[bold cyan]Analyze codebase[/bold cyan]",
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
        result = runner.run_analyze_codebase(
            explore_prompt=explore_prompt,
            workspace=workspace_root,
            user_prompt=user_prompt,
            documents=documents,
            preferred_model=preferred_model,
        )
    except (RuntimeError, TimeoutError, OSError) as error:
        console.print(f"[red]Falha na sessão ACP:[/red] {error}")
        return 1

    stop_reason = result.get("stopReason", "end_turn")
    ask_count = int(result.get("askQuestionCount", 0))
    console.print()
    if stop_reason == "cancelled":
        console.print("[yellow]Análise cancelada.[/yellow]")
        return 1

    console.print(f"[green]✓[/green] Sessão concluída ({stop_reason})")
    if ask_count:
        console.print(f"[dim]{ask_count} pergunta(s) respondida(s) no terminal[/dim]")
    console.print("[dim]Artefatos esperados em .specs/codebase/[/dim]")
    return 0
