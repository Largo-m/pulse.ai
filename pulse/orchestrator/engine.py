"""The orchestrator: which agent runs now, and when.

The only state machine in Pulse, agnostic of what agents do. A workflow is an
ordered list of steps ([pulse.domain.workflow.WorkflowDef]); for each step the
engine resolves the agent, renders `prompt_template`, opens an isolated session
and records the outcome on the run.

Everything the engine does to the world goes through the ports in
[pulse.domain.ports], handed in as `EnginePorts`; only the daemon knows which
adapters stand behind them.

Sessions are isolated per step on purpose: the next step only receives the summary
Pulse forwards, which allows switching runtimes between steps and redoing one step.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from pulse.domain.control import RUN_BLOCKED, RUN_STOPPED, RunControl
from pulse.domain.outcome import LoopSignal, Outcome, OutcomeStatus, parse_outcome
from pulse.domain.ports import (
    AgentProfiles,
    AgentSession,
    JsonObject,
    PhaseContinuation,
    PromptContinuation,
    RunRepository,
    StreamSink,
    Workspace,
    WorkspaceError,
)
from pulse.domain.run import RunRecord, StepRecord, StepStatus
from pulse.domain.workflow import StepDef, WorkflowDef
from pulse.orchestrator.agent_text import (
    build_continuation_prompt,
    build_outcome_reminder_prompt,
    build_unblock_prompt,
    guidance_block,
    outcome_protocol,
)
from pulse.orchestrator.fanout import POSITION_STRIDE, Item, expand
from pulse.orchestrator.loops import close_loop, repeat_loop
from pulse.orchestrator.render import TemplateError, render
from pulse.orchestrator.turn import MenuChoice, TurnResult
from pulse.orchestrator.waits import RunWaits
from pulse.orchestrator.worktree import prepare_workspace
from pulse.replies.approval import format_summary


class EmptyWorkflow(ValueError):
    """A definition with no step: there is nothing to run."""


@dataclass(frozen=True)
class EnginePorts:
    """Everything the engine does to the world, wired by the daemon."""

    session: AgentSession
    stream: StreamSink
    runs: RunRepository
    workspace: Workspace
    agents: AgentProfiles


@dataclass(frozen=True)
class _Wiring:
    """What every step of one run shares: the ports, the stop switch and where it works."""

    ports: EnginePorts
    control: RunControl
    exec_dir: Path

    @property
    def session(self) -> AgentSession:
        return self.ports.session

    @property
    def runs(self) -> RunRepository:
        return self.ports.runs


def run_workflow(
    *,
    definition: WorkflowDef,
    user_prompt: str,
    ports: EnginePorts,
    use_worktree: bool = False,
    resume_run_id: str | None = None,
    control: RunControl | None = None,
    run_id: str | None = None,
) -> int:
    """Run the workflow to its end and return the run's exit code.

    A refusal before the first step (no step, no worktree) raises for the caller;
    a crash mid-run is recorded on the run, then raised.
    """
    if not definition.steps:
        raise EmptyWorkflow(f"workflow `{definition.id}` não tem step nenhum")

    run = _resolve_run(
        definition,
        ports,
        user_prompt,
        resume_run_id=resume_run_id,
        run_id=run_id,
    )

    try:
        exec_dir, branch = prepare_workspace(
            run, ports.workspace, ports.runs, use_worktree=use_worktree
        )
    except WorkspaceError as error:
        raise RuntimeError(f"Não consegui abrir o worktree desta run: {error}") from error

    # Must precede the first `phase.begin`: the artifact pane uses it to know
    # which folder to watch.
    ports.stream.set_context(cwd=str(exec_dir), branch=branch)
    ports.session.bind_run(run.id, RunWaits(run, ports.runs))
    wiring = _Wiring(ports=ports, control=control or RunControl(), exec_dir=exec_dir)

    try:
        return _execute(wiring, definition=definition, run=run)
    # The run is the boundary: record the crash on it, then let the caller report it.
    except Exception:  # noqa: BLE001
        run.crash()
        ports.runs.save(run)
        raise


def _resolve_run(
    definition: WorkflowDef,
    ports: EnginePorts,
    user_prompt: str,
    *,
    resume_run_id: str | None,
    run_id: str | None = None,
) -> RunRecord:
    """The stored run. `run_id` lets the caller name it.

    The daemon passes its own id so the API and storage share one run id.
    """
    if resume_run_id:
        existing = ports.runs.load(resume_run_id)
        if existing is not None:
            # A killed daemon leaves its step `running`; one step runs at a time.
            existing.fail_running_steps()
            return existing
    return ports.runs.create(
        run_id=run_id or str(uuid.uuid4()),
        workflow_id=definition.id,
        workspace=ports.workspace.root,
        user_prompt=user_prompt,
        steps=[
            StepRecord(
                step_id=step.step_id,
                position=step.position * POSITION_STRIDE,
                label=step.label,
                agent_id=step.agent_id,
            )
            for step in definition.steps
        ],
    )


def _execute(wiring: _Wiring, *, definition: WorkflowDef, run: RunRecord) -> int:
    try:
        wiring.session.open(wiring.exec_dir)
        _sync_steps(wiring, run)

        loops = definition.loops()
        index = 0
        while index < len(definition.steps):
            definition_step = definition.steps[index]
            at = index
            index += 1
            previous = run.previous_delivery(definition_step.step_id)
            units = expand(run, definition_step, previous.summary if previous else "")
            wiring.runs.save(run)
            _sync_steps(wiring, run)

            for step, item in units:
                record = run.add_step(
                    StepRecord(
                        step_id=step.step_id,
                        position=step.position,
                        label=step.label,
                        agent_id=step.agent_id,
                    )
                )

                if record.settled:
                    continue

                if not wiring.control.checkpoint():
                    _notify(wiring, "Run parada pelo usuário")
                    run.end(RUN_STOPPED)
                    wiring.runs.save(run)
                    return RUN_STOPPED

                loop = loops.get(at)
                opens_loop = loop is not None and loop.opens(at)
                exit_code, signal = _run_step(
                    wiring,
                    run=run,
                    step=step,
                    record=record,
                    item=item,
                    may_close=opens_loop,
                )
                _sync_steps(wiring, run)
                if exit_code != 0:
                    run.end(exit_code)
                    wiring.runs.save(run)
                    return exit_code

                if signal == LoopSignal.CLOSE and loop is not None and opens_loop:
                    index = close_loop(run, definition, loop)
                    wiring.runs.save(run)
                    _sync_steps(wiring, run)
                    _notify(wiring, f"{record.label}: nada a corrigir — laço encerrado")
                    break

                if signal == LoopSignal.REPEAT and loop is not None and loop.closes(at):
                    target, message = repeat_loop(run, definition, loop, record.label)
                    wiring.runs.save(run)
                    _notify(wiring, message)
                    if target is not None:
                        index = target
                        _sync_steps(wiring, run)
                        break

        run.retire_steps_outside({step.step_id for step in definition.steps})
        run.complete()
        wiring.runs.save(run)
        _sync_steps(wiring, run)
        return 0
    finally:
        wiring.session.close()


def _run_step(
    wiring: _Wiring,
    *,
    run: RunRecord,
    step: StepDef,
    record: StepRecord,
    item: Item | None = None,
    may_close: bool = False,
) -> tuple[int, LoopSignal | None]:
    """`(exit code, loop signal)`; how the step ended is in `record.status`."""
    guidance = ""
    while True:
        signal, reason = _attempt_step(
            wiring,
            run=run,
            step=step,
            record=record,
            guidance=guidance,
            item=item,
            may_close=may_close,
        )
        if record.settled:
            return 0, signal

        if wiring.control.interrupted:
            _release_step(wiring, run=run, record=record, label=record.label)
            return RUN_STOPPED, None

        blocked = record.status == StepStatus.BLOCKED
        if blocked:
            choice, guidance = _offer_blocked(wiring, f"{record.label} está bloqueado", reason)
        else:
            choice, guidance = _offer_retry(wiring, f"Step {record.label} falhou", reason)
        if wiring.control.interrupted:
            _release_step(wiring, run=run, record=record, label=record.label)
            return RUN_STOPPED, None

        if blocked:
            if choice == MenuChoice.SKIP:
                record.skip_blocked()
                wiring.runs.save(run)
                _sync_steps(wiring, run)
                _notify(wiring, f"{record.label} pulado pelo usuário")
                return 0, None
            if choice != MenuChoice.RETRY:
                record.close_after_wait()
                wiring.runs.save(run)
                _notify(wiring, f"Run bloqueada em {record.label}: {reason}")
                return RUN_BLOCKED, None
        elif choice != MenuChoice.RETRY:
            record.close_after_wait()
            wiring.runs.save(run)
            return 1, None
        _revive_session(wiring)
        if guidance:
            _notify(wiring, f"Refazendo {record.label} com orientação do usuário")
        else:
            _notify(wiring, f"Refazendo {record.label}")


def _attempt_step(
    wiring: _Wiring,
    *,
    run: RunRecord,
    step: StepDef,
    record: StepRecord,
    guidance: str,
    item: Item | None = None,
    may_close: bool = False,
) -> tuple[LoopSignal | None, str]:
    """`(loop signal, reason)`. How the attempt ended is the step's status;
    `reason` explains a failure or a block to the person deciding what next."""
    run.start_step(record.step_id)
    wiring.runs.save(run)

    profile = wiring.ports.agents.profile(step.agent_id)
    wiring.session.use_agent(profile)
    try:
        prompt_text = render(step.prompt_template, _template_values(wiring, run, step, item))
    except TemplateError as error:
        _fail(wiring, run, record)
        return None, str(error)
    # Inlined, not passed as a system prompt, so instructions work with any runtime.
    if profile.instructions:
        prompt_text = f"{profile.instructions}\n\n---\n\n{prompt_text}"
    prompt_text += guidance_block(guidance)

    if step.declares_outcome:
        prompt_text += outcome_protocol()

    try:
        if step.requires_approval:
            raw = wiring.session.run_isolated_phase(
                workflow=run.workflow_id,
                phase_label=record.label or step.step_id,
                initial_prompt=prompt_text,
                preferred_model=profile.model,
                build_continuation=_approval_continuation(step),
                phase_id=step.step_id,
            )
        else:
            raw = wiring.session.run_isolated_prompt(
                workflow=run.workflow_id,
                phase_label=record.label or step.step_id,
                prompt_text=prompt_text,
                preferred_model=profile.model,
                phase_id=step.step_id,
                build_continuation=_unblock_continuation(step) if step.declares_outcome else None,
            )
    # The session is the boundary to the agent: any failure fails the attempt, not the run.
    except Exception as error:  # noqa: BLE001
        _fail(wiring, run, record)
        return None, _session_error(error)

    turn = TurnResult.parse(raw)
    record.record_reply(
        session_id=wiring.session.last_session_id, summary=format_summary(turn.summary)
    )

    if turn.cancelled:
        _fail(wiring, run, record)
        return None, "step cancelado"

    if turn.skipped:
        record.skip()
        wiring.runs.save(run)
        return None, ""

    if may_close and not turn.approved and parse_outcome(turn.summary).closes:
        return _settle(wiring, run, record, LoopSignal.CLOSE)

    if step.requires_approval and not turn.approved:
        _fail(wiring, run, record)
        if not turn.has_approval_answers:
            return None, "o agente encerrou sem o bloco de aprovação nem um desfecho válido"
        return None, "step não aprovado"

    if not step.requires_approval and not turn.ended_cleanly:
        _fail(wiring, run, record)
        return None, turn.stop_reason or "o agente não concluiu o step"

    repeats = False
    if step.declares_outcome:
        declared = parse_outcome(turn.summary)
        if not declared.delivered:
            record.block()
            wiring.runs.save(run)
            return None, _blocked_reason(declared)
        repeats = step.repeat is not None and declared.repeats
        if may_close and declared.closes:
            return _settle(wiring, run, record, LoopSignal.CLOSE)

    return _settle(wiring, run, record, LoopSignal.REPEAT if repeats else None)


def _settle(
    wiring: _Wiring, run: RunRecord, record: StepRecord, signal: LoopSignal | None
) -> tuple[LoopSignal | None, str]:
    """Record the step as delivered and pass the agent's loop signal on."""
    record.deliver()
    wiring.runs.save(run)
    return signal, ""


def _approval_continuation(step: StepDef) -> PhaseContinuation:
    """What to send after an approval answer that asked for more."""

    def build(*, phase_summary: str, questionnaire_answers: str, outcome: str) -> str:
        return build_continuation_prompt(
            step_id=step.step_id,
            summary=phase_summary,
            answers=questionnaire_answers,
            outcome=outcome,
        )

    return build


def _unblock_continuation(step: StepDef) -> PromptContinuation:
    """Give the agent one chance to unblock itself before involving the user.

    Runs in the same session (see `run_isolated_prompt`), once per attempt. Also
    covers a missing outcome block, usually just a forgotten declaration.
    """
    spent = False

    def build(*, result: JsonObject, turn: int) -> str:
        nonlocal spent
        if spent:
            return ""
        declared = parse_outcome(TurnResult.parse(result).summary)
        if declared.delivered:
            return ""
        spent = True
        if declared.status == OutcomeStatus.MISSING:
            return build_outcome_reminder_prompt(step_id=step.step_id)
        if declared.needs_user:
            return ""
        return build_unblock_prompt(step_id=step.step_id, reason=declared.reason)

    return build


def _blocked_reason(declared: Outcome) -> str:
    if declared.status == OutcomeStatus.MISSING:
        return (
            "o agente encerrou sem declarar o desfecho do step — "
            "não dá para afirmar que ele entregou o que o step pede"
        )
    return declared.reason or "o agente declarou bloqueio sem dizer o motivo"


def _fail(wiring: _Wiring, run: RunRecord, record: StepRecord) -> None:
    record.fail()
    wiring.runs.save(run)


def _template_values(
    wiring: _Wiring,
    run: RunRecord,
    step: StepDef,
    item: Item | None = None,
) -> dict[str, str]:
    """Values `prompt_template` may reference.

    Keys are generic: the engine knows no artifact or phase names. `workspace` is
    where the agent works (the run's worktree, if any). `item_*` are empty strings
    outside fan-out, so the same template works in both modes. `previous_status`
    is the status (`done`/`skipped`) of the step `previous_summary` came from,
    empty when none. A skip from the blocked menu clears `summary`, so that step
    drops out and the earlier one is reported.
    """
    artifacts = wiring.runs.artifacts(run.id)
    siblings = run.fan_out_siblings(step.step_id) if item is not None else []
    previous = run.previous_delivery(step.step_id)
    return {
        "user_prompt": run.user_prompt.strip(),
        "workspace": str(wiring.exec_dir),
        "workflow_id": run.workflow_id,
        "run_id": run.id,
        "step_id": step.step_id,
        "step_label": step.label,
        "previous_summary": previous.summary if previous is not None else "",
        "previous_status": previous.status if previous is not None else "",
        "artifacts": "\n".join(f"- {path}" for path in artifacts),
        "item_id": item.id if item else "",
        "item_label": item.label if item else "",
        "item_index": str(_index_of(siblings, step.step_id)) if item else "",
        "item_total": str(len(siblings)) if item else "",
    }


def _index_of(records: list[StepRecord], step_id: str) -> int:
    for index, record in enumerate(records, start=1):
        if record.step_id == step_id:
            return index
    return 1


def _release_step(
    wiring: _Wiring,
    *,
    run: RunRecord,
    record: StepRecord,
    label: str,
) -> None:
    """Release the step cut by a stop, returning it to pending.

    Pending makes `resume_run_id` restart from this step only; settled steps are
    not redone.
    """
    if record.release():
        wiring.runs.save(run)
        _sync_steps(wiring, run)
    _notify(wiring, f"Run parada em {label}" if label else "Run parada pelo usuário")


def _offer_retry(wiring: _Wiring, title: str, reason: str) -> tuple[MenuChoice, str]:
    """Decide what to do with a failed step."""
    return _choose(
        wiring,
        title,
        reason,
        [
            ("Refazer", MenuChoice.RETRY),
            ("Outro — dizer o que fazer", MenuChoice.GUIDANCE),
            ("Parar", MenuChoice.STOP),
        ],
    )


def _offer_blocked(wiring: _Wiring, title: str, reason: str) -> tuple[MenuChoice, str]:
    """Decide what to do with a step the agent could not complete.

    Adds a skip option, recorded as `skipped` rather than hidden as `done`.
    """
    return _choose(
        wiring,
        title,
        reason,
        [
            ("Refazer — já resolvi", MenuChoice.RETRY),
            ("Outro — dizer o que fazer", MenuChoice.GUIDANCE),
            ("Pular este step", MenuChoice.SKIP),
            ("Parar a run", MenuChoice.STOP),
        ],
    )


def _choose(
    wiring: _Wiring,
    title: str,
    reason: str,
    choices: list[tuple[str, MenuChoice]],
) -> tuple[MenuChoice, str]:
    """Ask the user and return `(choice, guidance)`.

    "Outro" lets the user write what the agent should do. With nobody to ask,
    the answer is stop, and the reason is left on the stream for whoever reads it.
    """
    prompt = reason.strip() or "O step não foi concluído."
    choice = wiring.session.prompts.select_choice(prompt, choices, title=title)
    if choice is None:
        if not wiring.control.interrupted:
            _notify(wiring, f"{title}: {prompt}")
        return MenuChoice.STOP, ""
    if choice == MenuChoice.GUIDANCE:
        guidance = _ask_guidance(wiring, title)
        if guidance:
            return MenuChoice.RETRY, guidance
        if wiring.control.interrupted:
            return MenuChoice.STOP, ""
        return _choose(wiring, title, reason, choices)
    if choice in {value for _label, value in choices}:
        return MenuChoice(choice), ""
    return MenuChoice.STOP, ""


def _session_error(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return f"o agente parou de responder — {error}"
    if isinstance(error, RuntimeError | OSError):
        return f"a sessão do agente caiu — {error}"
    return f"o step quebrou — {type(error).__name__}: {error}"


def _revive_session(wiring: _Wiring) -> None:
    """Restart the agent process before retrying the step.

    Retrying on a dead session would just fail again.
    """
    try:
        if wiring.session.revive():
            _notify(wiring, "Sessão do agente reiniciada")
    except (RuntimeError, TimeoutError, OSError) as error:
        _notify(wiring, f"Não consegui reiniciar a sessão do agente: {error}")


def _ask_guidance(wiring: _Wiring, title: str) -> str:
    answer = wiring.session.prompts.ask_text(
        "O que o agente deve fazer nesta nova tentativa?", title=title
    )
    return (answer or "").strip()


def _notify(wiring: _Wiring, message: str) -> None:
    wiring.ports.stream.info(message)


def _sync_steps(wiring: _Wiring, run: RunRecord) -> None:
    """Mirror `run_steps` to the panel, including the full step list.

    The list is sent because fan-out changes it mid-run.
    """
    grouped = run.step_ids_by_status()
    wiring.ports.stream.apply_phase_statuses(
        steps=[
            {"id": item.step_id, "label": item.label, "rounds": item.rounds} for item in run.steps
        ],
        done_ids=grouped[StepStatus.DONE],
        skipped_ids=grouped[StepStatus.SKIPPED],
        failed_ids=grouped[StepStatus.FAILED],
        blocked_ids=grouped[StepStatus.BLOCKED],
    )
