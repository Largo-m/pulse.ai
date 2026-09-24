from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config import resolve_config
from pulse.doctor.checks import check_agent_in_path, check_auth
from pulse.plan.cli_output import (
    emit_stream_error,
    print_workflow_banner,
    print_workflow_error,
    print_workflow_result,
)
from pulse.plan.legacy_cleanup import cleanup_legacy_pulse_questions
from pulse.plan.quick_prompt import (
    PULSE_SPEC_SKILL,
    build_quick_plan_prompt,
    resolve_quick_skill,
)
from pulse.ports import NullPromptPort, NullStreamSink
from pulse.runtime.tty import is_cockpit_stream, is_interactive


def run_quick(
    *,
    user_prompt: str,
    workspace: Path | None = None,
    stream: Any | None = None,
    prompt_handler: Any | None = None,
    render_header: bool = True,
) -> int:
    cockpit = is_cockpit_stream(stream)
    if not cockpit and not is_interactive():
        print("[pulse] Workflow requer terminal interativo ou cliente Engine.", file=sys.stderr)
        return 1

    agent_check = check_agent_in_path()
    auth_check = check_auth()
    if agent_check.status != "ok" or auth_check.status != "ok":
        message = "Corrija agent e autenticação antes de iniciar."
        if cockpit:
            raise RuntimeError(message)
        print(f"[pulse] {message}", file=sys.stderr)
        return 1

    resolved = resolve_config(workspace=workspace, pulse_agent="quick-plan")
    workspace_root = resolved.workspace_dir
    permission_policy = resolved.permission_policy
    acp_command = resolved.acp_command
    preferred_model = resolved.model

    cleanup_legacy_pulse_questions(workspace=workspace_root, skill_id=PULSE_SPEC_SKILL)

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

    if render_header and not cockpit:
        print_workflow_banner(
            title="Quick mode",
            lines=[
                "Skill: pulse-spec-driven",
                f"Workspace: {workspace_root}",
                f"Tarefa: {user_prompt.strip() or '—'}",
            ],
        )

    active_stream = stream or NullStreamSink()
    active_handler = prompt_handler or NullPromptPort()
    runner = AcpSessionRunner(
        acp_command,
        cwd=str(workspace_root),
        permission_policy=permission_policy,
        stream=active_stream,
        prompt_handler=active_handler,
        pulse_agent=getattr(resolved, "pulse_agent", None),
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
        if cockpit:
            raise
        print_workflow_error(f"Falha na sessão ACP: {error}")
        return 1

    stop_reason = result.get("stopReason", "end_turn")
    ask_count = int(result.get("askQuestionCount", 0))
    approved = bool(result.get("approved", False))
    outcome = str(result.get("outcome", ""))
    if stop_reason == "cancelled" or outcome == "cancelled":
        emit_stream_error(
            active_stream,
            "Questionário cancelado",
            "O questionário foi cancelado ou não pôde ser respondido.",
        )
        if not cockpit:
            print_workflow_result("Quick task cancelada.")
        return 1

    if cockpit:
        return 0

    print()

    if outcome == "cancel":
        print_workflow_result("Operação cancelada pelo usuário.")
        return 0

    if not approved:
        if outcome == "migrate":
            print_workflow_result("Migração para pipeline completo registrada.")
            print_workflow_result("Siga as orientações do agente acima para iniciar Specify.")
        elif outcome in {"reduce_scope", "adjust", "continue"}:
            print_workflow_result("Escolha registrada — aguardando próximo passo do agente.")
            print_workflow_result("Se o plano exigir nova aprovação, responda no terminal.")
        else:
            print_workflow_result("Quick task não aprovada — nenhuma alteração de código aplicada.")
            print_workflow_result("Revise o plano em .pulse/specs/quick/ ou rode novamente com escopo menor.")
        return 0

    print_workflow_result(f"Quick task concluída ({stop_reason})")
    if ask_count:
        print_workflow_result(f"{ask_count} pergunta(s) respondida(s) no terminal")
    print_workflow_result("Artefatos esperados em .pulse/specs/quick/")
    return 0
