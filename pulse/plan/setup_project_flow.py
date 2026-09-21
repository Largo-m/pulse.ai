from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config import resolve_config
from pulse.doctor.checks import check_agent_in_path, check_auth
from pulse.plan.cli_output import print_workflow_banner, print_workflow_error, print_workflow_result
from pulse.plan.legacy_cleanup import cleanup_legacy_pulse_questions
from pulse.plan.setup_project_prompt import (
    TLC_SPEC_SKILL,
    build_setup_project_prompt,
    resolve_tlc_spec_skill,
)
from pulse.ports import NullPromptPort, NullStreamSink
from pulse.runtime.tty import is_cockpit_stream, is_interactive


def run_setup_project(
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

    resolved = resolve_config(workspace=workspace, workflow="setup-project")
    workspace_root = resolved.workspace_dir
    permission_policy = resolved.permission_policy
    acp_command = resolved.acp_command
    preferred_model = resolved.model

    cleanup_legacy_pulse_questions(workspace=workspace_root, skill_id=TLC_SPEC_SKILL)

    try:
        skill_dir = resolve_tlc_spec_skill()
    except FileNotFoundError as error:
        print(f"[pulse] {error}", file=sys.stderr)
        return 1

    interview_prompt = build_setup_project_prompt(
        workspace=workspace_root,
        user_prompt=user_prompt,
        skill_dir=skill_dir,
    )

    if render_header and not cockpit:
        print_workflow_banner(
            title="Setup project",
            lines=[f"Skill: tlc-spec-driven", f"Workspace: {workspace_root}"],
        )

    active_stream = stream or NullStreamSink()
    active_handler = prompt_handler or NullPromptPort()
    runner = AcpSessionRunner(
        acp_command,
        cwd=str(workspace_root),
        permission_policy=permission_policy,
        stream=active_stream,
        prompt_handler=active_handler,
    )

    try:
        result = runner.run_setup_project(
            interview_prompt=interview_prompt,
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
    if cockpit:
        return 1 if stop_reason == "cancelled" else 0

    print()
    if stop_reason == "cancelled":
        print_workflow_result("Questionário cancelado.")
        return 1

    print_workflow_result(f"Sessão concluída ({stop_reason})")
    if ask_count:
        print_workflow_result(f"{ask_count} pergunta(s) respondida(s) no terminal")
    else:
        print_workflow_result("Nenhum questionário necessário — contexto inferido do workspace")
    print_workflow_result("Artefatos esperados em .pulse/specs/project/")
    return 0
