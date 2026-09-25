from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pulse.acp.session_runner import AcpSessionRunner
from pulse.runtimes import get_runtime
from pulse.config import resolve_config
from pulse.doctor.checks import check_runtime_ready
from pulse.plan.legacy_cleanup import cleanup_legacy_pulse_questions
from pulse.plan.new_issue_flow import run_new_issue
from pulse.plan.quick_flow import run_quick
from pulse.plan.spec_prompt import PULSE_SPEC_SKILL, build_classify_prompt, resolve_spec_skill
from pulse.plan.spec_route import load_route, parse_route_text
from pulse.plan.cli_output import print_workflow_banner, print_workflow_error, print_workflow_result
from pulse.ports import NullPromptPort, NullStreamSink
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.runtime.tty import is_cockpit_stream, is_interactive


def run_spec(
    *,
    user_prompt: str,
    workspace: Path | None = None,
    stream: Any | None = None,
    prompt_handler: Any | None = None,
    render_header: bool = True,
    spec_slug: str | None = None,
    spec_mode: str | None = None,
    control: RunControl | None = None,
) -> int:
    cockpit = is_cockpit_stream(stream)
    if spec_slug and spec_mode:
        # Retomar/refazer um spec conhecido: o flow já é `full`, classificar de
        # novo só gastaria uma sessão para chegar na mesma conclusão.
        return _run_known_spec(
            user_prompt=user_prompt,
            workspace=workspace,
            stream=stream,
            prompt_handler=prompt_handler,
            render_header=render_header,
            spec_slug=spec_slug,
            spec_mode=spec_mode,
            control=control,
        )
    if not cockpit and not is_interactive():
        print("[pulse] Workflow requer terminal interativo ou cliente Engine.", file=sys.stderr)
        return 1

    # Resolve antes de checar: cada workflow pode rodar em um runtime diferente.
    resolved = resolve_config(workspace=workspace, pulse_agent="classify")
    runtime = get_runtime(getattr(resolved, "agent_name", None))
    blocking = check_runtime_ready(runtime.id)
    if blocking is not None:
        message = (
            f"Runtime `{runtime.id}` indisponível: {blocking.message}. "
            f"{blocking.detail or ''}".strip()
        )
        if cockpit:
            raise RuntimeError(message)
        print(f"[pulse] {message}", file=sys.stderr)
        return 1
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
        runtime=get_runtime(getattr(resolved, "agent_name", None)),
        control=control,
    )

    result: dict[str, Any] = {}
    try:
        runner.start()
        runner.initialize()
        runner.authenticate()
        while True:
            result = runner.run_isolated_prompt(
                workflow="spec",
                phase_label="Classificar spec",
                prompt_text=classify_prompt,
                preferred_model=preferred_model,
            )
            if result.get("stopReason") != "cancelled":
                break
            # Classificar é um step só: pausar aqui significa refazê-lo inteiro
            # ao retomar, como em qualquer outro step.
            if not runner.control.interrupted:
                break
            if not runner.control.wait_while_paused():
                return RUN_STOPPED
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
        return run_quick(**kwargs, control=control)
    classify_session_id = getattr(runner, "last_session_id", "") or None
    return run_new_issue(
        **kwargs,
        classify_session_id=classify_session_id,
        control=control,
    )


def _run_known_spec(
    *,
    user_prompt: str,
    workspace: Path | None,
    stream: Any | None,
    prompt_handler: Any | None,
    render_header: bool,
    spec_slug: str,
    spec_mode: str,
    control: RunControl | None = None,
) -> int:
    active_stream = stream or NullStreamSink()
    _apply_route(active_stream, "full", "retomando" if spec_mode == "resume" else "refazendo")
    return run_new_issue(
        user_prompt=user_prompt,
        workspace=workspace,
        stream=active_stream,
        prompt_handler=prompt_handler or NullPromptPort(),
        render_header=render_header,
        spec_slug=spec_slug,
        spec_mode=spec_mode,
        control=control,
    )


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
