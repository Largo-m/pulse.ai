from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pulse.acp.session_runner import AcpSessionRunner
from pulse.runtimes import get_runtime
from pulse.config import resolve_config
from pulse.doctor.checks import check_runtime_ready
from pulse.plan.legacy_cleanup import cleanup_legacy_pulse_questions
from pulse.plan.new_issue_prompt import (
    PULSE_SPEC_SKILL,
    build_design_prompt,
    build_execute_inline_prompt,
    build_execute_task_prompt,
    build_phase_continuation_prompt,
    build_specify_prompt,
    build_tasks_prompt,
    resolve_new_issue_skill,
)
from pulse.plan.specify_state import (
    OPTIONAL_PHASES,
    PHASE_ORDER,
    PhaseStatus,
    WorkflowState,
    find_resumable_workflows,
    list_feature_workflows,
    slugify_feature,
)
from pulse.plan.task_waves import (
    TaskSpec,
    Wave,
    build_waves,
    parse_task_specs,
    run_wave_gates,
)
from pulse.plan.cli_output import print_workflow_banner, print_workflow_error, print_workflow_result
from pulse.ports import NullPromptPort, NullStreamSink
from pulse.prompts.permission import PermissionPolicy
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.runtime.tty import is_cockpit_stream, is_interactive
from pulse.store.spec_sessions import record_spec_session

_SUCCESS_STOPS = frozenset({"end_turn", "end", "stop"})
_PHASE_FILES = {
    "specify": "spec.md",
    "design": "design.md",
    "tasks": "tasks.md",
}
_PHASE_AGENTS = {
    "specify": "specify",
    "design": "design",
    "tasks": "tasks",
    "execute": "implement",
}
#: Fallback para runner sem controle (CLI, testes): nunca pausa nem para.
_NEVER_INTERRUPTED = RunControl()


def _control(runner: AcpSessionRunner) -> RunControl:
    return getattr(runner, "control", None) or _NEVER_INTERRUPTED


def run_new_issue(
    *,
    user_prompt: str,
    workspace: Path | None = None,
    stream: Any | None = None,
    prompt_handler: Any | None = None,
    render_header: bool = True,
    classify_session_id: str | None = None,
    spec_slug: str | None = None,
    spec_mode: str | None = None,
    control: RunControl | None = None,
) -> int:
    cockpit = is_cockpit_stream(stream)
    if not cockpit and not is_interactive():
        print("[pulse] Workflow requer terminal interativo ou cliente Engine.", file=sys.stderr)
        return 1

    # Resolve antes de checar: cada workflow pode rodar em um runtime diferente.
    resolved = resolve_config(workspace=workspace, pulse_agent="specify")
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
        skill_dir = resolve_new_issue_skill()
    except FileNotFoundError as error:
        print(f"[pulse] {error}", file=sys.stderr)
        return 1

    active_handler = prompt_handler or NullPromptPort()
    state = _resolve_workflow_state(
        workspace_root,
        user_prompt,
        prompt_handler=active_handler,
        spec_slug=spec_slug,
        spec_mode=spec_mode,
    )
    if state is None:
        return 0

    if render_header and not cockpit:
        _print_header(workspace_root, state, user_prompt)

    active_stream = stream or NullStreamSink()
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
    runner.bind_spec(state.feature_dir.as_posix())
    if classify_session_id:
        record_spec_session(
            workspace_root,
            spec_dir=state.feature_dir.as_posix(),
            phase_id="specify",
            acp_session_id=classify_session_id,
        )

    try:
        return _run_pipeline(
            runner=runner,
            cockpit=cockpit,
            workspace=workspace_root,
            user_prompt=state.user_prompt,
            skill_dir=skill_dir,
            state=state,
            preferred_model=preferred_model,
        )
    except (RuntimeError, TimeoutError, OSError) as error:
        if cockpit:
            raise
        print_workflow_error(f"Falha na sessão ACP: {error}")
        return 1


def _resolve_workflow_state(
    workspace: Path,
    user_prompt: str,
    *,
    prompt_handler: Any | None = None,
    spec_slug: str | None = None,
    spec_mode: str | None = None,
) -> WorkflowState | None:
    # Decisão já tomada (ex.: retomar/refazer escolhido no histórico): não pergunta.
    if spec_slug and spec_mode:
        return _apply_spec_decision(workspace, user_prompt, spec_slug, spec_mode)
    resumable = find_resumable_workflows(workspace)
    if resumable:
        return _pick_resumable(
            workspace,
            resumable,
            user_prompt,
            prompt_handler=prompt_handler,
        )
    slug = slugify_feature(user_prompt)
    state = WorkflowState.create_new(feature_slug=slug, user_prompt=user_prompt)
    state.save(workspace)
    return state


def _apply_spec_decision(
    workspace: Path,
    user_prompt: str,
    spec_slug: str,
    spec_mode: str,
) -> WorkflowState | None:
    """Retoma ou recomeça um spec específico, sem perguntar nada.

    `restart` não apaga artefatos: reseta o workflow.yaml para pendente e deixa
    o pipeline reescrever spec.md/design.md/tasks.md por cima.
    """
    existing = next(
        (item for item in list_feature_workflows(workspace) if item.feature_slug == spec_slug),
        None,
    )
    if spec_mode == "resume":
        if existing is None:
            return None
        tasks_path = workspace / existing.feature_dir / "tasks.md"
        if tasks_path.is_file():
            existing.sync_tasks_from_markdown(tasks_path)
        return existing
    if spec_mode == "restart":
        prompt = user_prompt or (existing.user_prompt if existing else "")
        state = WorkflowState.create_new(feature_slug=spec_slug, user_prompt=prompt)
        state.save(workspace)
        return state
    return None


def _pick_resumable(
    workspace: Path,
    workflows: list[WorkflowState],
    user_prompt: str,
    *,
    prompt_handler: Any | None = None,
) -> WorkflowState | None:
    select_choice = getattr(prompt_handler, "select_choice", None) if prompt_handler else None

    if len(workflows) == 1:
        only = workflows[0]
        choices = [
            ("Continuar workflow existente", "resume"),
            ("Iniciar novo workflow", "new"),
            ("Cancelar", "cancel"),
        ]
        if select_choice is None:
            return None
        choice = select_choice(
            f"Workflow em andamento encontrado: {only.feature_slug}. O que deseja?",
            choices,
            title="Resume",
        )
        if choice is None or choice == "cancel":
            return None
        if choice == "resume":
            return only
        slug = slugify_feature(user_prompt)
        state = WorkflowState.create_new(feature_slug=slug, user_prompt=user_prompt)
        state.save(workspace)
        return state

    choices: list[tuple[str, object]] = [
        (f"Continuar: {wf.feature_slug} (fase: {wf.current_phase})", wf)
        for wf in workflows
    ]
    choices.append(("Iniciar novo workflow", "new"))
    choices.append(("Cancelar", "cancel"))

    if select_choice is None:
        return None
    picked = select_choice(
        "Workflows em andamento encontrados. O que deseja?",
        choices,
        title="Resume",
    )
    if picked is None or picked == "cancel":
        return None
    if picked == "new":
        slug = slugify_feature(user_prompt)
        state = WorkflowState.create_new(feature_slug=slug, user_prompt=user_prompt)
        state.save(workspace)
        return state
    return picked


def _print_header(
    workspace: Path,
    state: WorkflowState,
    user_prompt: str,
) -> None:
    print_workflow_banner(
        title="New issue — Specify pipeline",
        lines=[
            "Skill: pulse-spec-driven",
            f"Workspace: {workspace}",
            f"Feature: {state.feature_slug}",
            f"Fase atual: {state.current_phase}",
            f"Tarefa: {user_prompt.strip() or '—'}",
        ],
    )


def _run_pipeline(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    preferred_model: str | None,
) -> int:
    runner.start()
    try:
        runner.initialize()
        runner.authenticate()
        _sync_stream_phases(runner, state)
        _sync_stream_tasks(runner, state)

        start_index = _phase_start_index(state)
        for phase in PHASE_ORDER[start_index:]:
            # Pausa pedida entre dois steps: segura aqui, sem nada em voo.
            if not _control(runner).checkpoint():
                _notify(runner, "Run parada pelo usuário")
                return RUN_STOPPED

            if phase == "tasks":
                _require_tasks_phase(state)

            if phase == "execute":
                exit_code = _run_execute_phase(
                    runner=runner,
                    cockpit=cockpit,
                    workspace=workspace,
                    user_prompt=user_prompt,
                    skill_dir=skill_dir,
                    state=state,
                    preferred_model=preferred_model,
                )
                if exit_code != 0:
                    return exit_code
                continue

            if not state.should_run_phase(phase):
                reason = state.phases[phase].skip_reason or "Fase opcional não necessária para este escopo"
                state.mark_phase_skipped(phase, reason)
                state.save(workspace)
                _sync_stream_phases(runner, state)
                if not cockpit:
                    print_workflow_result(f"⏭  {phase.capitalize()} pulada: {reason}")
                continue

            if state.phases[phase].status in {PhaseStatus.APPROVED, PhaseStatus.DONE}:
                _sync_stream_phases(runner, state)
                continue

            exit_code = _run_approval_phase(
                runner=runner,
                cockpit=cockpit,
                workspace=workspace,
                user_prompt=user_prompt,
                skill_dir=skill_dir,
                state=state,
                phase=phase,
                preferred_model=preferred_model,
            )
            if exit_code != 0:
                return exit_code

            state = _reload_state(workspace, state)
            _sync_stream_phases(runner, state)
            _sync_stream_tasks(runner, state)
            if phase in OPTIONAL_PHASES and state.phases[phase].skip:
                reason = state.phases[phase].skip_reason or "Marcada como skip pelo agente"
                state.mark_phase_skipped(phase, reason)
                state.save(workspace)
                _sync_stream_phases(runner, state)
                if not cockpit:
                    print_workflow_result(f"⏭  {phase.capitalize()} pulada: {reason}")

        if not cockpit:
            print()
        if not cockpit:
            print_workflow_result("✓ Pipeline Specify concluído")
        if not cockpit:
            print_workflow_result(f"Estado em {state.workflow_path.as_posix()}")
        return 0
    finally:
        runner.close()


def _require_tasks_phase(state: WorkflowState) -> None:
    phase = state.phases["tasks"]
    phase.skip = False
    phase.skip_reason = ""
    if phase.status == PhaseStatus.SKIPPED:
        phase.status = PhaseStatus.PENDING


def _activate_phase_agent(
    runner: AcpSessionRunner,
    workspace: Path,
    phase: str,
    fallback_model: str | None,
) -> str | None:
    agent_id = _PHASE_AGENTS.get(phase, "specify")
    resolved = resolve_config(workspace=workspace, pulse_agent=agent_id)
    policies: dict[str, PermissionPolicy] = {
        "ask": "ask",
        "auto_approve": "auto_approve",
        "deny_writes": "deny_writes",
    }
    use_agent = getattr(runner, "use_agent", None)
    if callable(use_agent):
        use_agent(agent_id, policies.get(resolved.permission_policy, "ask"))
    return resolved.model or fallback_model


def _phase_start_index(state: WorkflowState) -> int:
    current = state.current_phase
    if current in PHASE_ORDER:
        index = PHASE_ORDER.index(current)
        phase_status = state.phases[current].status
        if phase_status in {PhaseStatus.APPROVED, PhaseStatus.DONE, PhaseStatus.SKIPPED}:
            return min(index + 1, len(PHASE_ORDER) - 1)
        return index
    return 0


def _hold_for_pause(
    runner: AcpSessionRunner,
    *,
    workspace: Path,
    state: WorkflowState,
    phase: str | None = None,
    label: str = "",
) -> bool:
    """Segura o fluxo enquanto a run está pausada.

    O step que foi cortado volta para pendente: ele não terminou, então será
    refeito inteiro ao retomar. Devolve `False` quando a run foi parada.
    """
    if phase is not None and state.phases[phase].status == PhaseStatus.IN_PROGRESS:
        state.phases[phase].status = PhaseStatus.PENDING
        state.save(workspace)
        _sync_stream_phases(runner, state)
    if _control(runner).stopped:
        _notify(runner, f"Run parada em {label}" if label else "Run parada pelo usuário")
        return False
    _notify(runner, f"Pausado em {label}" if label else "Run pausada")
    if not _control(runner).wait_while_paused():
        _notify(runner, "Run parada pelo usuário")
        return False
    _notify(runner, f"Retomando {label}" if label else "Retomando a run")
    return True


def _run_approval_phase(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    phase: str,
    preferred_model: str | None,
) -> int:
    guidance = ""
    while True:
        outcome, reason = _attempt_approval_phase(
            runner=runner,
            cockpit=cockpit,
            workspace=workspace,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            state=state,
            phase=phase,
            preferred_model=preferred_model,
            guidance=guidance,
        )
        if outcome == "approved":
            return 0
        if outcome == "skip" and phase in OPTIONAL_PHASES:
            skip_reason = state.phases[phase].skip_reason or reason or "Fase opcional não necessária"
            state.mark_phase_skipped(phase, skip_reason)
            state.save(workspace)
            _sync_stream_phases(runner, state)
            return 0
        # A fase não terminou porque o usuário cortou, não porque falhou: não
        # faz sentido perguntar "quer tentar de novo?" — é só segurar e refazer.
        if _control(runner).interrupted:
            if not _hold_for_pause(
                runner,
                workspace=workspace,
                state=state,
                phase=phase,
                label=f"fase {phase.capitalize()}",
            ):
                return RUN_STOPPED
            continue
        choice, guidance = _offer_retry(runner, f"Fase {phase.capitalize()} falhou", reason)
        if choice != "retry":
            state.mark_phase_failed(phase)
            state.save(workspace)
            _sync_stream_phases(runner, state)
            return 1
        if guidance:
            _notify(runner, f"Refazendo fase {phase} com orientação do usuário")
        else:
            _notify(runner, f"Refazendo fase {phase}")


def _attempt_approval_phase(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    phase: str,
    preferred_model: str | None,
    guidance: str = "",
) -> tuple[str, str]:
    prompt_builder = _phase_prompt_builder(phase)
    state.mark_phase_in_progress(phase)
    state.save(workspace)

    def build_continuation(
        *,
        phase_summary: str,
        questionnaire_answers: str,
        outcome: str,
        **_: object,
    ) -> str:
        return build_phase_continuation_prompt(
            workspace=workspace,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            state=state,
            phase=phase,
            phase_summary=phase_summary,
            questionnaire_answers=questionnaire_answers,
            outcome=outcome,
            prompt_builder=prompt_builder,
        )

    preferred_model = _activate_phase_agent(runner, workspace, phase, preferred_model)
    result = runner.run_isolated_phase(
        workflow="spec",
        phase_label=f"Fase {phase.capitalize()}",
        initial_prompt=prompt_builder(
            workspace=workspace,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            state=state,
        )
        + _guidance_block(guidance),
        preferred_model=preferred_model,
        build_continuation=build_continuation,
        continuation_kwargs={},
        phase_id=phase,
    )

    outcome = str(result.get("outcome", ""))
    if outcome in {"cancel", "cancelled"}:
        if not cockpit:
            print_workflow_result(f"{phase.capitalize()} cancelada.")
        return "failed", "fase cancelada"

    if outcome == "skip":
        return "skip", state.phases[phase].skip_reason or "fase marcada para pular"

    if phase == "tasks" and bool(result.get("approved")):
        tasks_path = workspace / state.feature_dir / "tasks.md"
        state.sync_tasks_from_markdown(tasks_path)
        if not state.tasks:
            _notify(runner, "tasks.md sem tasks — fase não aprovada")
            if not cockpit:
                print_workflow_result("tasks.md sem tasks — fase não aprovada.")
            return "failed", "tasks.md sem tasks"

    artifact_name = _PHASE_FILES.get(phase)
    if artifact_name and phase != "tasks" and bool(result.get("approved")):
        artifact_path = workspace / state.feature_dir / artifact_name
        if not artifact_path.is_file():
            message = f"{artifact_name} não foi criado — fase não aprovada"
            _notify(runner, message)
            if not cockpit:
                print_workflow_result(message)
            return "failed", message

    if not bool(result.get("approved")):
        if not cockpit:
            print_workflow_result(f"{phase.capitalize()} não aprovada.")
        return "failed", "fase não aprovada"

    state.approve_phase(phase)
    state.save(workspace)
    if not cockpit:
        print_workflow_result(f"✓ {phase.capitalize()} aprovada")

    reloaded = _reload_state(workspace, state)
    if phase == "tasks":
        tasks_path = workspace / reloaded.feature_dir / "tasks.md"
        reloaded.sync_tasks_from_markdown(tasks_path)
        reloaded.save(workspace)
        state.tasks = reloaded.tasks
        _sync_stream_tasks(runner, state)

    return "approved", ""


def _run_execute_phase(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    preferred_model: str | None,
) -> int:
    preferred_model = _activate_phase_agent(runner, workspace, "execute", preferred_model)
    state.mark_phase_in_progress("execute")
    state.save(workspace)

    tasks_skipped = not state.should_run_phase("tasks") or state.phases["tasks"].skip
    tasks_path = workspace / state.feature_dir / "tasks.md"
    if tasks_skipped or not state.tasks:
        state.sync_tasks_from_markdown(tasks_path)
        state.save(workspace)

    if state.tasks:
        tasks_skipped = False

    if not state.tasks:
        if not cockpit:
            print_workflow_result("Execute — implementação inline (Tasks pulada)")
        execute_guidance = ""
        while True:
            result = runner.run_isolated_prompt(
                workflow="spec",
                phase_label="Fase Execute — implementação",
                prompt_text=build_execute_inline_prompt(
                    workspace=workspace,
                    user_prompt=user_prompt,
                    skill_dir=skill_dir,
                    state=state,
                )
                + _guidance_block(execute_guidance),
                preferred_model=preferred_model,
                phase_id="execute",
            )
            if result.get("stopReason") == "cancelled" or not _prompt_succeeded(result):
                reason = (
                    "fase cancelada"
                    if result.get("stopReason") == "cancelled"
                    else str(result.get("stopReason") or "o agente não concluiu a fase")
                )
                if _control(runner).interrupted:
                    if not _hold_for_pause(
                        runner,
                        workspace=workspace,
                        state=state,
                        phase="execute",
                        label="fase Execute",
                    ):
                        return RUN_STOPPED
                    continue
                if not cockpit:
                    print_workflow_result(f"Execute falhou: {reason}")
                execute_choice, execute_guidance = _offer_retry(
                    runner, "Fase Execute falhou", reason
                )
                if execute_choice != "retry":
                    state.mark_phase_failed("execute")
                    state.save(workspace)
                    _sync_stream_phases(runner, state)
                    return 1
                if execute_guidance:
                    _notify(runner, "Refazendo fase Execute com orientação do usuário")
                else:
                    _notify(runner, "Refazendo fase Execute")
                continue
            state.sync_tasks_from_markdown(tasks_path)
            state.save(workspace)
            if not state.tasks:
                state.mark_phase_done("execute")
                state.save(workspace)
                if not cockpit:
                    print_workflow_result("✓ Execute concluída")
                return 0
            _notify(runner, f"tasks.md encontrado — executando {len(state.tasks)} task(s)")
            break

    tasks_path = workspace / state.feature_dir / "tasks.md"
    specs = _load_task_specs(tasks_path, state)
    done_ids = {task.task_id for task in state.tasks if task.status == "done"}
    ordered = [
        spec
        for wave in build_waves(specs, done_ids=done_ids)
        for spec in wave.tasks
    ]
    _sync_stream_tasks(runner, state)

    if not cockpit:
        print_workflow_result(f"Execute — {len(state.tasks)} task(s)")
    _notify(runner, f"Execute — {len(state.tasks)} task(s)")

    pending = list(ordered)
    while True:
        outcome, stuck = _run_task_round(
            runner=runner,
            cockpit=cockpit,
            workspace=workspace,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            state=state,
            preferred_model=preferred_model,
            tasks_skipped=tasks_skipped,
            pending=pending,
        )
        if outcome == "stopped":
            # Parar não é falhar: o que já foi salvo continua retomável.
            state.save(workspace)
            _sync_stream_phases(runner, state)
            _sync_stream_tasks(runner, state)
            return RUN_STOPPED
        if outcome == "aborted":
            state.mark_phase_failed("execute")
            state.save(workspace)
            _sync_stream_phases(runner, state)
            return 1
        if not stuck:
            break
        # A rodada acabou com tasks falhas/bloqueadas, mas a run continua viva:
        # dá para consertar o ambiente e tentar de novo sem sair do workflow.
        if _offer_failed_round(runner, stuck) != "retry":
            state.mark_phase_failed("execute")
            state.save(workspace)
            _sync_stream_phases(runner, state)
            return 1
        pending = [
            spec for spec in ordered if _task_status(state, spec.task_id) != "done"
        ]
        if not pending:
            break
        _notify(runner, f"Tentando novamente {len(pending)} task(s)")

    if not state.all_tasks_done():
        state.mark_phase_failed("execute")
        state.save(workspace)
        _sync_stream_phases(runner, state)
        return 1

    state.mark_phase_done("execute")
    state.save(workspace)
    if not cockpit:
        print_workflow_result("✓ Execute concluída — todas as tasks finalizadas")
    _notify(runner, "Execute concluída — todas as tasks finalizadas")
    return 0


def _load_task_specs(tasks_path: Path, state: WorkflowState):
    if tasks_path.is_file():
        return parse_task_specs(tasks_path.read_text(encoding="utf-8"))
    return [
        TaskSpec(task_id=task.task_id, title=task.title)
        for task in state.tasks
    ]


#: Resultados de uma task. "Pular" não encerra a Execute — só tira a task da
#: rodada; "Parar" é a única saída que abandona a fase.
TASK_DONE = 0
TASK_SKIPPED = 1
TASK_ABORTED = 2
#: Run parada pelo usuário: a fase não falhou, só não continuou.
TASK_STOPPED = 3


def _run_task_round(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    preferred_model: str | None,
    tasks_skipped: bool,
    pending: list[TaskSpec],
) -> tuple[str, list[tuple[str, str]]]:
    """Roda uma passada pelas tasks pendentes.

    Uma task pulada não derruba a fase: as tasks seguintes que não dependem
    dela continuam. Só as dependentes ficam bloqueadas. Devolve
    `(desfecho, [(task_id, motivo)])` com o que sobrou por resolver.
    """
    failed: set[str] = set()
    stuck: list[tuple[str, str]] = []
    for spec in pending:
        # Pausa pedida entre duas tasks: segura antes de abrir a próxima sessão.
        if not _control(runner).checkpoint():
            return "stopped", stuck

        blocking = [dep for dep in spec.depends_on if dep in failed]
        if blocking:
            reason = "depende de " + ", ".join(blocking)
            stuck.append((spec.task_id, reason))
            failed.add(spec.task_id)
            if not cockpit:
                print_workflow_result(f"  Task {spec.task_id} bloqueada — {reason}")
            _notify(runner, f"Task {spec.task_id} bloqueada — {reason}")
            continue
        result = _run_execute_task(
            runner=runner,
            cockpit=cockpit,
            workspace=workspace,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            state=state,
            preferred_model=preferred_model,
            tasks_skipped=tasks_skipped,
            spec=spec,
        )
        if result == TASK_STOPPED:
            return "stopped", stuck
        if result == TASK_ABORTED:
            remaining = len(pending) - pending.index(spec) - 1
            if remaining > 0:
                _notify(
                    runner,
                    f"Execute parada em Task {spec.task_id} — {remaining} task(s) pendente(s)",
                )
            return "aborted", stuck
        if result == TASK_SKIPPED:
            failed.add(spec.task_id)
            stuck.append((spec.task_id, "falhou"))
    return "finished", stuck


def _run_execute_task(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    preferred_model: str | None,
    tasks_skipped: bool,
    spec: TaskSpec,
) -> int:
    task = spec
    if _task_status(state, task.task_id) == "done":
        if not cockpit:
            print_workflow_result(f"  Task {task.task_id} — já concluída")
        return TASK_DONE

    label = f"Task {task.task_id}: {task.title}".strip()
    guidance = ""
    while True:
        outcome, reason = _attempt_execute_task(
            runner=runner,
            cockpit=cockpit,
            workspace=workspace,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            state=state,
            preferred_model=preferred_model,
            tasks_skipped=tasks_skipped,
            task=task,
            label=label,
            guidance=guidance,
        )
        if outcome == "done":
            return TASK_DONE
        if outcome == "cancelled":
            # Corte do usuário: a task fica pendente e é refeita ao retomar.
            if _control(runner).interrupted:
                if not _hold_for_pause(
                    runner,
                    workspace=workspace,
                    state=state,
                    label=f"Task {task.task_id}",
                ):
                    return TASK_STOPPED
                continue
            return TASK_ABORTED
        if outcome == "unverified":
            choice, guidance = _offer_unverified(
                runner, f"Task {task.task_id} sem gate", reason
            )
            accepted = "concluída sem verificação"
        elif outcome == "gate_failed":
            choice, guidance = _offer_gate_failure(
                runner, f"Task {task.task_id}: gate falhou", reason
            )
            accepted = "concluída com gate ignorado"
        else:
            choice, guidance = _offer_retry(
                runner, f"Task {task.task_id} falhou", reason, allow_skip=True
            )
            accepted = "concluída mesmo assim"

        if choice == "accept":
            state.mark_task_done(task.task_id)
            state.save(workspace)
            _sync_stream_tasks(runner, state)
            _notify(runner, f"Task {task.task_id} {accepted}")
            return TASK_DONE
        if choice in {"skip", "stop"}:
            state.mark_task_failed(task.task_id)
            state.save(workspace)
            _sync_stream_tasks(runner, state)
            if choice == "skip":
                _notify(
                    runner,
                    f"Task {task.task_id} pulada — seguindo nas tasks que não dependem dela",
                )
                return TASK_SKIPPED
            return TASK_ABORTED
        if guidance:
            _notify(runner, f"Refazendo Task {task.task_id} com orientação do usuário")
        else:
            _notify(runner, f"Refazendo Task {task.task_id}")


def _attempt_execute_task(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    preferred_model: str | None,
    tasks_skipped: bool,
    task: TaskSpec,
    label: str,
    guidance: str = "",
) -> tuple[str, str]:
    if not cockpit:
        print_workflow_result(f"{label}")
    _notify(runner, label)
    result = runner.run_isolated_prompt(
        workflow="spec",
        phase_label=f"Execute — {label}",
        prompt_text=build_execute_task_prompt(
            workspace=workspace,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            state=state,
            task_id=task.task_id,
            task_title=task.title,
            tasks_skipped=tasks_skipped,
        )
        + _guidance_block(guidance),
        preferred_model=preferred_model,
        phase_id="execute",
        task_id=task.task_id,
    )
    if result.get("stopReason") == "cancelled":
        if not cockpit:
            print_workflow_result(f"{label} cancelada.")
        _notify(runner, f"{label} cancelada")
        return "cancelled", "task cancelada"

    if not _prompt_succeeded(result):
        reason = str(result.get("stopReason") or "o agente não concluiu a task")
        if not cockpit:
            print_workflow_result(f"{label} não concluída ({reason}).")
        _notify(runner, f"{label} não concluída ({reason})")
        return "failed", reason

    reloaded = _reload_state(workspace, state)
    _sync_workflow_tasks(state, reloaded)
    _force_task_pending(state, task.task_id)

    if not task.gate_commands:
        # Não é falha da tentativa: `tasks.md` não declarou como verificar. Refazer
        # daria exatamente o mesmo resultado — por isso vira um outcome próprio,
        # com decisões que terminam o laço.
        reason = "sem gate de verificação — a task não foi confirmada"
        if not cockpit:
            print_workflow_result(f"{label} {reason}.")
        _notify(runner, f"{label} {reason}")
        return "unverified", reason

    gate_wave = Wave(wave_id=1, tasks=(task,), parallel=False)
    gate_results = run_wave_gates(workspace=workspace, wave=gate_wave)
    failed = [item for item in gate_results if not item.ok]
    if failed:
        details = []
        for item in failed:
            if not cockpit:
                print_workflow_result(f"Gate falhou: `{item.command}` (exit {item.exit_code})")
            _notify(runner, f"Gate falhou: {item.command} (exit {item.exit_code})")
            if item.output and not cockpit:
                print_workflow_result(f"{item.output[-2000:]}")
            details.append(f"{item.command} (exit {item.exit_code})")
        # Quem roda o gate é o Pulse, não o agente: nenhuma orientação dada ao
        # agente ("pule esse teste") impede o comando de rodar de novo. Por isso
        # a falha de gate tem outcome próprio, com uma saída que ignora o gate.
        return "gate_failed", "gate falhou: " + "; ".join(details)

    state.mark_task_done(task.task_id)
    state.save(workspace)
    _sync_stream_tasks(runner, state)
    if not cockpit:
        print_workflow_result(f"✓ {label} — gates ok")
    _notify(runner, f"{label} — gates ok")
    return "done", ""


def _prompt_succeeded(result: dict[str, Any]) -> bool:
    return str(result.get("stopReason") or "") in _SUCCESS_STOPS


def _skip_choice(allow_skip: bool) -> list[tuple[str, str]]:
    """"Pular" só existe para task: uma fase pulada não tem o que continuar."""
    if not allow_skip:
        return []
    return [("Pular esta task e seguir nas outras", "skip")]


def _offer_retry(
    runner: AcpSessionRunner,
    title: str,
    reason: str,
    *,
    allow_skip: bool = False,
) -> tuple[str, str]:
    """Decide o que fazer com uma etapa que falhou.

    Devolve `(escolha, orientação)`. "Outro" deixa o usuário escrever o que o
    agente deve fazer — nem toda falha se resolve repetindo a mesma tentativa.
    """
    handler = getattr(runner, "_prompt_handler", None)
    select = getattr(handler, "select_choice", None)
    prompt = reason.strip() or "A etapa não foi concluída."
    if not callable(select):
        _notify(runner, f"{title}: {prompt}")
        return "stop", ""
    choice = select(
        prompt,
        [
            ("Refazer", "retry"),
            ("Outro — dizer o que fazer", "guidance"),
            *_skip_choice(allow_skip),
            ("Parar", "stop"),
        ],
        title=title,
    )
    if choice == "retry":
        return "retry", ""
    if choice == "skip" and allow_skip:
        return "skip", ""
    if choice == "guidance":
        guidance = _ask_guidance(runner, title)
        if guidance:
            return "retry", guidance
        # desistiu de escrever: volta a perguntar em vez de parar por engano
        return _offer_retry(runner, title, reason, allow_skip=allow_skip)
    return "stop", ""


def _offer_unverified(runner: AcpSessionRunner, title: str, reason: str) -> tuple[str, str]:
    """Decide o que fazer com uma task que rodou mas não tem como ser verificada.

    Não oferece "Refazer" puro de propósito: a ausência de gate está no
    `tasks.md`, não na execução, então repetir a tentativa cairia no mesmo
    lugar — era o loop infinito. Todas as saídas aqui terminam o laço, e só
    "Outro" repete, agora com instrução nova.
    """
    handler = getattr(runner, "_prompt_handler", None)
    select = getattr(handler, "select_choice", None)
    prompt = reason.strip() or "A task não pôde ser verificada."
    if not callable(select):
        _notify(runner, f"{title}: {prompt}")
        return "stop", ""
    choice = select(
        prompt,
        [
            ("Concluir sem verificação", "accept"),
            ("Outro — dizer o que fazer", "guidance"),
            ("Pular esta task e seguir nas outras", "skip"),
            ("Parar", "stop"),
        ],
        title=title,
    )
    if choice == "accept":
        return "accept", ""
    if choice == "skip":
        return "skip", ""
    if choice == "guidance":
        guidance = _ask_guidance(runner, title)
        if guidance:
            return "retry", guidance
        return _offer_unverified(runner, title, reason)
    return "stop", ""


def _offer_gate_failure(runner: AcpSessionRunner, title: str, reason: str) -> tuple[str, str]:
    """Decide o que fazer quando o gate da task falha.

    Diferente de `_offer_retry`, oferece "Ignorar o gate": o comando é rodado
    pelo Pulse, então pedir ao agente para pular o teste não impede o gate de
    rodar de novo — sem essa saída, ambiente quebrado (emulador fora do ar,
    por exemplo) vira loop infinito.
    """
    handler = getattr(runner, "_prompt_handler", None)
    select = getattr(handler, "select_choice", None)
    prompt = reason.strip() or "O gate da task não passou."
    if not callable(select):
        _notify(runner, f"{title}: {prompt}")
        return "stop", ""
    choice = select(
        prompt,
        [
            ("Refazer", "retry"),
            ("Ignorar o gate e concluir a task", "accept"),
            ("Outro — dizer o que fazer", "guidance"),
            ("Pular esta task e seguir nas outras", "skip"),
            ("Parar", "stop"),
        ],
        title=title,
    )
    if choice == "retry":
        return "retry", ""
    if choice == "accept":
        return "accept", ""
    if choice == "skip":
        return "skip", ""
    if choice == "guidance":
        guidance = _ask_guidance(runner, title)
        if guidance:
            return "retry", guidance
        return _offer_gate_failure(runner, title, reason)
    return "stop", ""


def _offer_failed_round(
    runner: AcpSessionRunner, stuck: list[tuple[str, str]]
) -> str:
    """Pergunta, no fim da rodada, o que fazer com o que ficou por resolver.

    Existe para não obrigar a sair do workflow: com a run ainda viva dá para
    consertar o que travou (destravar um emulador, subir um serviço) e mandar
    tentar de novo daqui mesmo.
    """
    handler = getattr(runner, "_prompt_handler", None)
    select = getattr(handler, "select_choice", None)
    resumo = "; ".join(f"{task_id} ({reason})" for task_id, reason in stuck)
    prompt = f"Ficaram por resolver: {resumo}"
    _notify(runner, prompt)
    if not callable(select):
        return "stop"
    choice = select(
        prompt,
        [
            ("Tentar novamente estas tasks", "retry"),
            ("Encerrar a Execute assim mesmo", "stop"),
        ],
        title="Execute — tasks pendentes",
    )
    return "retry" if choice == "retry" else "stop"


def _ask_guidance(runner: AcpSessionRunner, title: str) -> str:
    handler = getattr(runner, "_prompt_handler", None)
    ask_text = getattr(handler, "ask_text", None)
    if not callable(ask_text):
        return ""
    answer = ask_text(
        "O que o agente deve fazer nesta nova tentativa?",
        title=title,
    )
    return str(answer or "").strip()


def _guidance_block(guidance: str) -> str:
    text = guidance.strip()
    if not text:
        return ""
    return (
        "\n\n## Orientação do usuário para esta tentativa\n\n"
        "A tentativa anterior falhou. Siga a orientação abaixo — ela tem\n"
        "precedência sobre o plano original desta etapa:\n\n"
        f"{text}\n"
    )


def _notify(runner: AcpSessionRunner, message: str) -> None:
    stream = getattr(runner, "_stream", None)
    if stream is None:
        return
    info = getattr(stream, "info", None)
    if callable(info):
        info(message)


def _sync_stream_phases(runner: AcpSessionRunner, state: WorkflowState) -> None:
    stream = getattr(runner, "_stream", None)
    if stream is None:
        return
    apply = getattr(stream, "apply_phase_statuses", None)
    if not callable(apply):
        return
    done_ids: list[str] = []
    skipped_ids: list[str] = []
    failed_ids: list[str] = []
    for phase_name in PHASE_ORDER:
        phase = state.phases[phase_name]
        if phase.status == PhaseStatus.FAILED:
            failed_ids.append(phase_name)
        elif phase.status == PhaseStatus.SKIPPED or phase.skip:
            skipped_ids.append(phase_name)
        elif phase.status in {PhaseStatus.APPROVED, PhaseStatus.DONE}:
            done_ids.append(phase_name)
    apply(done_ids=done_ids, skipped_ids=skipped_ids, failed_ids=failed_ids)


def _sync_stream_tasks(runner: AcpSessionRunner, state: WorkflowState) -> None:
    stream = getattr(runner, "_stream", None)
    if stream is None:
        return
    apply = getattr(stream, "set_tasks", None)
    if not callable(apply):
        return
    apply([(task.task_id, task.title, task.status) for task in state.tasks])


def _task_status(state: WorkflowState, task_id: str) -> str:
    for task in state.tasks:
        if task.task_id == task_id:
            return task.status
    return "pending"


def _force_task_pending(state: WorkflowState, task_id: str) -> None:
    for task in state.tasks:
        if task.task_id == task_id:
            task.status = "pending"
            task.completed_at = ""
            state.touch()
            return


def _sync_workflow_tasks(target: WorkflowState, source: WorkflowState) -> None:
    target.tasks = list(source.tasks)
    target.current_task_id = source.current_task_id
    target.updated_at = source.updated_at
    target.current_phase = source.current_phase
    target.phases = source.phases
    target.touch()


def _phase_prompt_builder(phase: str) -> Callable[..., str]:
    builders = {
        "specify": build_specify_prompt,
        "design": build_design_prompt,
        "tasks": build_tasks_prompt,
    }
    if phase not in builders:
        raise ValueError(f"Fase sem prompt builder: {phase}")
    return builders[phase]


def _reload_state(workspace: Path, state: WorkflowState) -> WorkflowState:
    path = workspace / state.workflow_path
    if path.is_file():
        try:
            return WorkflowState.load(path)
        except (OSError, ValueError):
            pass
    return state
