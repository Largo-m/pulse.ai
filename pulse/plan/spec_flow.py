from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config import resolve_config
from pulse.doctor.checks import check_agent_in_path, check_auth
from pulse.plan.legacy_cleanup import cleanup_legacy_pulse_questions
from pulse.plan.new_issue_flow import run_new_issue
from pulse.plan.quick_flow import run_quick
from pulse.plan.spec_prompt import PULSE_SPEC_SKILL, build_classify_prompt, resolve_spec_skill
from pulse.plan.spec_route import load_route, parse_route_text
from pulse.plan.cli_output import print_workflow_banner, print_workflow_error, print_workflow_result
from pulse.ports import NullPromptPort, NullStreamSink
from pulse.runtime.tty import is_cockpit_stream, is_interactive


def run_spec(
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

    resolved = resolve_config(workspace=workspace, pulse_agent="classify")
    workspace_root = resolved.workspace_dir
    permission_policy = resolved.permission_policy
    acp_command = resolved.acp_command
    preferred_model = resolved.model

    cleanup_legacy_pulse_questions(workspace=workspace_root, skill_id=PULSE_SPEC_SKILL)

    try:
        skill_dir = resolve_spec_skill()
    except FileNotFoundError as error:
        print(f"[pulse] {error}", file=sys.stderr)
        return 1

    if render_header and not cockpit:
        print_workflow_banner(
            title="Nova spec",
            lines=[
                "Skill: pulse-spec-driven",
                f"Workspace: {workspace_root}",
                f"Spec: {user_prompt.strip() or '—'}",
            ],
        )

    active_stream = stream or NullStreamSink()
    active_handler = prompt_handler or NullPromptPort()
    classify_prompt = build_classify_prompt(
        workspace=workspace_root,
        user_prompt=user_prompt,
        skill_dir=skill_dir,
    )
    runner = AcpSessionRunner(
        acp_command,
        cwd=str(workspace_root),
        permission_policy=permission_policy,
        stream=active_stream,
        prompt_handler=active_handler,
        pulse_agent=getattr(resolved, "pulse_agent", None),
    )

    result: dict[str, Any] = {}
    try:
        runner.start()
        runner.initialize()
        runner.authenticate()
        result = runner.run_isolated_prompt(
            workflow="spec",
            phase_label="Classificar spec",
            prompt_text=classify_prompt,
            preferred_model=preferred_model,
        )
    except (RuntimeError, TimeoutError, OSError) as error:
        if cockpit:
            raise
        print_workflow_error(f"Falha na sessão ACP: {error}")
        return 1
    finally:
        runner.close()

    if result.get("stopReason") == "cancelled":
        return 1

    route = load_route(workspace_root)
    if route is None:
        route = parse_route_text(str(result.get("phaseSummary") or ""))
    if route is None:
        route = _ask_flow(active_handler)
    if route is None:
        reason = "O agente não definiu o flow (quick ou full)."
        emit_error = getattr(active_stream, "error", None)
        if callable(emit_error):
            emit_error("Classificação cancelada", reason)
        elif not cockpit:
            print_workflow_error(f"Classificação cancelada. {reason}")
        return 1

    flow, reason = route
    from pulse.agents.compose import expand_spec_flow

    roster = expand_spec_flow(flow)
    _apply_route(active_stream, flow, reason)
    info = getattr(active_stream, "info", None)
    if callable(info):
        info("Agents: " + ", ".join(roster))
    if not cockpit:
        label = "Quick mode" if flow == "quick" else "Pipeline completo"
        extra = f" — {reason}" if reason else ""
        print_workflow_result(f"Flow: {label}{extra}")

    kwargs = {
        "user_prompt": user_prompt,
        "workspace": workspace_root,
        "stream": active_stream,
        "prompt_handler": active_handler,
        "render_header": False,
    }
    if flow == "quick":
        return run_quick(**kwargs)
    return run_new_issue(**kwargs)


def _apply_route(stream: Any, flow: str, reason: str) -> None:
    apply = getattr(stream, "apply_routed_flow", None)
    if callable(apply):
        apply(flow)
    info = getattr(stream, "info", None)
    if callable(info):
        label = "quick" if flow == "quick" else "full"
        message = f"Flow: {label}"
        if reason:
            message = f"{message} — {reason}"
        info(message)


def _ask_flow(prompt_handler: Any) -> tuple[str, str] | None:
    select_choice = getattr(prompt_handler, "select_choice", None)
    if not callable(select_choice):
        return None
    picked = select_choice(
        "Não foi possível classificar a spec automaticamente. Qual flow seguir?",
        [
            ("Pipeline completo (feature)", "full"),
            ("Quick mode", "quick"),
            ("Cancelar", "cancel"),
        ],
        title="Classificar spec",
    )
    if picked is None or picked == "cancel":
        return None
    if picked in {"full", "quick"}:
        return str(picked), "Escolha do usuário"
    return None
