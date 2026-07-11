from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config import resolve_config
from pulse.doctor.checks import check_agent_in_path, check_auth
from pulse.plan.legacy_cleanup import cleanup_legacy_pulse_questions
from pulse.plan.new_issue_prompt import (
    TLC_SPEC_SKILL,
    build_design_prompt,
    build_execute_inline_prompt,
    build_execute_wave_prompt,
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
    slugify_feature,
)
from pulse.plan.task_waves import (
    Wave,
    build_waves,
    parse_task_specs,
    run_wave_gates,
)
from pulse.presentation.prompt.handler import PromptHandler
from pulse.presentation.stream_renderer import StreamRenderer
from pulse.terminal.tty import is_interactive


def run_new_issue(*, user_prompt: str, workspace: Path | None = None) -> int:
    if not is_interactive():
        print("[pulse] New issue requer terminal interativo.", file=sys.stderr)
        return 1

    agent_check = check_agent_in_path()
    auth_check = check_auth()
    if agent_check.status != "ok" or auth_check.status != "ok":
        print("[pulse] Corrija agent e autenticação antes de iniciar.", file=sys.stderr)
        return 1

    resolved = resolve_config(workspace=workspace, workflow="new-issue")
    workspace_root = resolved.workspace_dir
    permission_policy = resolved.permission_policy
    acp_command = resolved.acp_command
    preferred_model = resolved.model

    cleanup_legacy_pulse_questions(workspace=workspace_root, skill_id=TLC_SPEC_SKILL)

    try:
        skill_dir = resolve_new_issue_skill()
    except FileNotFoundError as error:
        print(f"[pulse] {error}", file=sys.stderr)
        return 1

    state = _resolve_workflow_state(workspace_root, user_prompt)
    if state is None:
        return 0

    console = Console(highlight=False, soft_wrap=True)
    _print_header(console, workspace_root, state, user_prompt)

    runner = AcpSessionRunner(
        acp_command,
        cwd=str(workspace_root),
        permission_policy=permission_policy,
        stream=StreamRenderer(console),
        prompt_handler=PromptHandler(console=console),
    )

    try:
        return _run_pipeline(
            runner=runner,
            console=console,
            workspace=workspace_root,
            user_prompt=state.user_prompt,
            skill_dir=skill_dir,
            state=state,
            preferred_model=preferred_model,
        )
    except (RuntimeError, TimeoutError, OSError) as error:
        console.print(f"[red]Falha na sessão ACP:[/red] {error}")
        return 1


def _resolve_workflow_state(workspace: Path, user_prompt: str) -> WorkflowState | None:
    resumable = find_resumable_workflows(workspace)
    if resumable:
        return _pick_resumable(workspace, resumable, user_prompt)
    slug = slugify_feature(user_prompt)
    state = WorkflowState.create_new(feature_slug=slug, user_prompt=user_prompt)
    state.save(workspace)
    return state


def _pick_resumable(
    workspace: Path,
    workflows: list[WorkflowState],
    user_prompt: str,
) -> WorkflowState | None:
    import questionary

    from pulse.terminal.styles import MENU_STYLE

    if len(workflows) == 1:
        only = workflows[0]
        choice = questionary.select(
            f"Workflow em andamento encontrado: {only.feature_slug}. O que deseja?",
            choices=[
                questionary.Choice("Continuar workflow existente", value="resume"),
                questionary.Choice("Iniciar novo workflow", value="new"),
                questionary.Choice("Cancelar", value="cancel"),
            ],
            style=MENU_STYLE,
        ).ask()
        if choice is None or choice == "cancel":
            return None
        if choice == "resume":
            return only
        slug = slugify_feature(user_prompt)
        state = WorkflowState.create_new(feature_slug=slug, user_prompt=user_prompt)
        state.save(workspace)
        return state

    choices = [
        questionary.Choice(f"Continuar: {wf.feature_slug} (fase: {wf.current_phase})", value=wf)
        for wf in workflows
    ]
    choices.append(questionary.Choice("Iniciar novo workflow", value="new"))
    choices.append(questionary.Choice("Cancelar", value="cancel"))

    picked = questionary.select(
        "Workflows em andamento encontrados. O que deseja?",
        choices=choices,
        style=MENU_STYLE,
    ).ask()
    if picked is None or picked == "cancel":
        return None
    if picked == "new":
        slug = slugify_feature(user_prompt)
        state = WorkflowState.create_new(feature_slug=slug, user_prompt=user_prompt)
        state.save(workspace)
        return state
    return picked


def _print_header(
    console: Console,
    workspace: Path,
    state: WorkflowState,
    user_prompt: str,
) -> None:
    console.print()
    console.print(
        Panel(
            "\n".join(
                [
                    "Skill: tlc-spec-driven",
                    f"Workspace: {workspace}",
                    f"Feature: {state.feature_slug}",
                    f"Fase atual: {state.current_phase}",
                    f"Tarefa: {user_prompt.strip() or '—'}",
                ]
            ),
            title="[bold cyan]New issue — Specify pipeline[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()


def _run_pipeline(
    *,
    runner: AcpSessionRunner,
    console: Console,
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

        start_index = _phase_start_index(state)
        for phase in PHASE_ORDER[start_index:]:
            if phase == "execute":
                exit_code = _run_execute_phase(
                    runner=runner,
                    console=console,
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
                console.print(f"[dim]⏭  {phase.capitalize()} pulada: {reason}[/dim]")
                continue

            if state.phases[phase].status in {PhaseStatus.APPROVED, PhaseStatus.DONE}:
                continue

            exit_code = _run_approval_phase(
                runner=runner,
                console=console,
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
            if phase in OPTIONAL_PHASES and state.phases[phase].skip:
                reason = state.phases[phase].skip_reason or "Marcada como skip pelo agente"
                state.mark_phase_skipped(phase, reason)
                state.save(workspace)
                console.print(f"[dim]⏭  {phase.capitalize()} pulada: {reason}[/dim]")

        console.print()
        console.print("[green]✓[/green] Pipeline Specify concluído")
        console.print(f"[dim]Estado em {state.workflow_path.as_posix()}[/dim]")
        return 0
    finally:
        runner.close()


def _phase_start_index(state: WorkflowState) -> int:
    current = state.current_phase
    if current in PHASE_ORDER:
        index = PHASE_ORDER.index(current)
        phase_status = state.phases[current].status
        if phase_status in {PhaseStatus.APPROVED, PhaseStatus.DONE, PhaseStatus.SKIPPED}:
            return min(index + 1, len(PHASE_ORDER) - 1)
        return index
    return 0


def _run_approval_phase(
    *,
    runner: AcpSessionRunner,
    console: Console,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    phase: str,
    preferred_model: str | None,
) -> int:
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

    initial_prompt = prompt_builder(
        workspace=workspace,
        user_prompt=user_prompt,
        skill_dir=skill_dir,
        state=state,
    )

    result = runner.run_isolated_phase(
        workflow="new-issue",
        phase_label=f"Fase {phase.capitalize()}",
        initial_prompt=initial_prompt,
        preferred_model=preferred_model,
        build_continuation=build_continuation,
        continuation_kwargs={},
    )

    outcome = str(result.get("outcome", ""))
    if outcome in {"cancel", "cancelled"}:
        console.print(f"[yellow]{phase.capitalize()} cancelada.[/yellow]")
        state.save(workspace)
        return 1

    if not bool(result.get("approved")):
        console.print(f"[yellow]{phase.capitalize()} não aprovada — pipeline pausado.[/yellow]")
        state.mark_phase_awaiting_approval(phase)
        state.save(workspace)
        return 0

    state.approve_phase(phase)
    state.save(workspace)
    console.print(f"[green]✓[/green] {phase.capitalize()} aprovada")

    state = _reload_state(workspace, state)
    if phase == "tasks":
        tasks_path = workspace / state.feature_dir / "tasks.md"
        state.sync_tasks_from_markdown(tasks_path)
        state.save(workspace)

    return 0


def _run_execute_phase(
    *,
    runner: AcpSessionRunner,
    console: Console,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    preferred_model: str | None,
) -> int:
    state.mark_phase_in_progress("execute")
    state.save(workspace)

    tasks_skipped = not state.should_run_phase("tasks") or state.phases["tasks"].skip
    if tasks_skipped or not state.tasks:
        tasks_path = workspace / state.feature_dir / "tasks.md"
        state.sync_tasks_from_markdown(tasks_path)
        state.save(workspace)

    if not state.tasks:
        console.print("[cyan]Execute — implementação inline (Tasks pulada)[/cyan]")
        result = runner.run_isolated_prompt(
            workflow="new-issue",
            phase_label="Fase Execute — implementação",
            prompt_text=build_execute_inline_prompt(
                workspace=workspace,
                user_prompt=user_prompt,
                skill_dir=skill_dir,
                state=state,
            ),
            preferred_model=preferred_model,
        )
        if result.get("stopReason") == "cancelled":
            console.print("[yellow]Execute cancelada.[/yellow]")
            return 1
        state.mark_phase_done("execute")
        state.save(workspace)
        console.print("[green]✓[/green] Execute concluída")
        return 0

    tasks_path = workspace / state.feature_dir / "tasks.md"
    specs = _load_task_specs(tasks_path, state)
    done_ids = {task.task_id for task in state.tasks if task.status == "done"}
    waves = build_waves(specs, done_ids=done_ids)

    console.print(
        f"[cyan]Execute — {len(state.tasks)} task(s) em {len(waves)} wave(s)[/cyan]"
    )
    for wave in waves:
        exit_code = _run_execute_wave(
            runner=runner,
            console=console,
            workspace=workspace,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            state=state,
            preferred_model=preferred_model,
            tasks_skipped=tasks_skipped,
            wave=wave,
        )
        if exit_code != 0:
            return exit_code

    state.mark_phase_done("execute")
    state.save(workspace)
    console.print("[green]✓[/green] Execute concluída — todas as waves finalizadas")
    return 0


def _load_task_specs(tasks_path: Path, state: WorkflowState):
    if tasks_path.is_file():
        return parse_task_specs(tasks_path.read_text(encoding="utf-8"))
    from pulse.plan.task_waves import TaskSpec

    return [
        TaskSpec(task_id=task.task_id, title=task.title)
        for task in state.tasks
    ]


def _run_execute_wave(
    *,
    runner: AcpSessionRunner,
    console: Console,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    preferred_model: str | None,
    tasks_skipped: bool,
    wave: Wave,
) -> int:
    pending = [task for task in wave.tasks if _task_status(state, task.task_id) != "done"]
    if not pending:
        console.print(f"[dim]  {wave.label} — já concluída[/dim]")
        return 0

    console.print(f"[cyan]{wave.label}[/cyan]")
    task_lines = [f"- **{task.task_id}** — {task.title}" for task in pending]
    pending_ids = [task.task_id for task in pending]
    result = runner.run_isolated_prompt(
        workflow="new-issue",
        phase_label=f"Execute — {wave.label}",
        prompt_text=build_execute_wave_prompt(
            workspace=workspace,
            user_prompt=user_prompt,
            skill_dir=skill_dir,
            state=state,
            wave_label=wave.label,
            task_lines=task_lines,
            task_ids=pending_ids,
            parallel=wave.parallel and len(pending) > 1,
            tasks_skipped=tasks_skipped,
        ),
        preferred_model=preferred_model,
    )
    if result.get("stopReason") == "cancelled":
        console.print(f"[yellow]{wave.label} cancelada — pipeline pausado.[/yellow]")
        state.save(workspace)
        return 1

    reloaded = _reload_state(workspace, state)
    _sync_workflow_tasks(state, reloaded)
    for task in pending:
        _force_task_pending(state, task.task_id)

    gate_wave = Wave(
        wave_id=wave.wave_id,
        tasks=tuple(pending),
        parallel=wave.parallel and len(pending) > 1,
    )
    gate_results = run_wave_gates(workspace=workspace, wave=gate_wave)
    failed = [item for item in gate_results if not item.ok]
    if failed:
        for item in failed:
            console.print(f"[red]Gate falhou:[/red] `{item.command}` (exit {item.exit_code})")
            if item.output:
                console.print(f"[dim]{item.output[-2000:]}[/dim]")
        console.print(
            f"[yellow]{wave.label} não marcada como done — corrija o gate e retome.[/yellow]"
        )
        state.save(workspace)
        return 1

    for task in pending:
        state.mark_task_done(task.task_id)
    state.save(workspace)
    if gate_results:
        console.print(f"[green]✓[/green] {wave.label} — gates ok")
    else:
        console.print(f"[green]✓[/green] {wave.label}")
    return 0


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
