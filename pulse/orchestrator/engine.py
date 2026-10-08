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

from pulse.domain import ui_text
from pulse.domain.control import RUN_STOPPED, RunControl
from pulse.domain.outcome import LoopSignal, Outcome, OutcomeStatus, parse_outcome
from pulse.domain.ports import (
    AgentProfile,
    JsonObject,
    PhaseContinuation,
    PromptContinuation,
    WorkspaceError,
)
from pulse.domain.run import RunRecord, StepRecord
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
from pulse.orchestrator.menus import end_without_retry, offer_next, revive_session
from pulse.orchestrator.render import TemplateError, render
from pulse.orchestrator.turn import TurnResult
from pulse.orchestrator.waits import RunWaits
from pulse.orchestrator.wiring import EnginePorts, Wiring, notify, sync_steps
from pulse.orchestrator.worktree import prepare_workspace
from pulse.replies.approval import format_summary


class EmptyWorkflow(ValueError):
    """A definition with no step: there is nothing to run."""


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
        raise EmptyWorkflow(f"workflow `{definition.id}` has no steps")

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
        raise RuntimeError(f"could not open the worktree for this run: {error}") from error

    # Must precede the first `phase.begin`: the artifact pane uses it to know
    # which folder to watch.
    ports.stream.set_context(cwd=str(exec_dir), branch=branch)
    ports.session.bind_run(run.id, RunWaits(run, ports.runs))
    wiring = Wiring(ports=ports, control=control or RunControl(), exec_dir=exec_dir)

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


def _execute(wiring: Wiring, *, definition: WorkflowDef, run: RunRecord) -> int:
    try:
        wiring.session.open(wiring.exec_dir)
        sync_steps(wiring, run)

        loops = definition.loops()
        index = 0
        while index < len(definition.steps):
            definition_step = definition.steps[index]
            at = index
            index += 1
            previous = run.previous_delivery(definition_step.step_id)
            units = expand(run, definition_step, previous.summary if previous else "")
            wiring.runs.save(run)
            sync_steps(wiring, run)

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
                    notify(wiring, ui_text.RUN_STOPPED_BY_USER)
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
                sync_steps(wiring, run)
                if exit_code != 0:
                    run.end(exit_code)
                    wiring.runs.save(run)
                    return exit_code

                if signal == LoopSignal.CLOSE and loop is not None and opens_loop:
                    index = close_loop(run, definition, loop)
                    wiring.runs.save(run)
                    sync_steps(wiring, run)
                    notify(wiring, ui_text.loop_closed(record.label))
                    break

                if signal == LoopSignal.REPEAT and loop is not None and loop.closes(at):
                    target, message = repeat_loop(run, definition, loop, record.label)
                    wiring.runs.save(run)
                    notify(wiring, message)
                    if target is not None:
                        index = target
                        sync_steps(wiring, run)
                        break

        run.retire_steps_outside({step.step_id for step in definition.steps})
        run.complete()
        wiring.runs.save(run)
        sync_steps(wiring, run)
        return 0
    finally:
        wiring.session.close()


def _run_step(
    wiring: Wiring,
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

        choice, guidance = offer_next(wiring, record, reason)
        if wiring.control.interrupted:
            _release_step(wiring, run=run, record=record, label=record.label)
            return RUN_STOPPED, None

        exit_code = end_without_retry(wiring, run, record, choice, reason)
        if exit_code is not None:
            return exit_code, None
        revive_session(wiring)
        notify(
            wiring,
            ui_text.retrying_step_with_guidance(record.label)
            if guidance
            else ui_text.retrying_step(record.label),
        )


def _attempt_step(
    wiring: Wiring,
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
        prompt_text = _step_prompt(wiring, run, step, profile, item=item, guidance=guidance)
    except TemplateError as error:
        _fail(wiring, run, record)
        return None, str(error)

    try:
        raw = _converse(wiring, run, step, record, profile, prompt_text)
    # The session is the boundary to the agent: any failure fails the attempt, not the run.
    except Exception as error:  # noqa: BLE001
        _fail(wiring, run, record)
        return None, _session_error(error)

    turn = TurnResult.parse(raw)
    record.record_reply(
        session_id=wiring.session.last_session_id, summary=format_summary(turn.summary)
    )
    return _judge_turn(wiring, run, step, record, turn, may_close=may_close)


def _step_prompt(
    wiring: Wiring,
    run: RunRecord,
    step: StepDef,
    profile: AgentProfile,
    *,
    item: Item | None,
    guidance: str,
) -> str:
    """The step's template rendered, wrapped in the agent's instructions and Pulse's protocol."""
    prompt_text = render(step.prompt_template, _template_values(wiring, run, step, item))
    # Inlined, not passed as a system prompt, so instructions work with any runtime.
    if profile.instructions:
        prompt_text = f"{profile.instructions}\n\n---\n\n{prompt_text}"
    prompt_text += guidance_block(guidance)
    if step.declares_outcome:
        prompt_text += outcome_protocol()
    return prompt_text


def _converse(
    wiring: Wiring,
    run: RunRecord,
    step: StepDef,
    record: StepRecord,
    profile: AgentProfile,
    prompt_text: str,
) -> JsonObject:
    """One ACP session for the step: an approval loop, or a single prompt and its follow-ups."""
    if step.requires_approval:
        return wiring.session.run_isolated_phase(
            workflow=run.workflow_id,
            phase_label=record.label or step.step_id,
            initial_prompt=prompt_text,
            preferred_model=profile.model,
            build_continuation=_approval_continuation(step),
            phase_id=step.step_id,
        )
    return wiring.session.run_isolated_prompt(
        workflow=run.workflow_id,
        phase_label=record.label or step.step_id,
        prompt_text=prompt_text,
        preferred_model=profile.model,
        phase_id=step.step_id,
        build_continuation=_unblock_continuation(step) if step.declares_outcome else None,
    )


def _judge_turn(
    wiring: Wiring,
    run: RunRecord,
    step: StepDef,
    record: StepRecord,
    turn: TurnResult,
    *,
    may_close: bool,
) -> tuple[LoopSignal | None, str]:
    """Settle, skip, fail or block the step from the agent's last turn."""
    if turn.cancelled:
        _fail(wiring, run, record)
        return None, ui_text.STEP_CANCELLED

    if turn.skipped:
        record.skip()
        wiring.runs.save(run)
        return None, ""

    if may_close and not turn.approved and parse_outcome(turn.summary).closes:
        return _settle(wiring, run, record, LoopSignal.CLOSE)

    unfinished = _unfinished_reason(step, turn)
    if unfinished is not None:
        _fail(wiring, run, record)
        return None, unfinished

    if not step.declares_outcome:
        return _settle(wiring, run, record, None)
    return _judge_outcome(wiring, run, step, record, parse_outcome(turn.summary), may_close)


def _unfinished_reason(step: StepDef, turn: TurnResult) -> str | None:
    """Why the turn does not count as finished: not approved, or not ended cleanly."""
    if step.requires_approval and not turn.approved:
        if not turn.has_approval_answers:
            return ui_text.NO_APPROVAL_NOR_OUTCOME
        return ui_text.STEP_NOT_APPROVED
    if not step.requires_approval and not turn.ended_cleanly:
        return turn.stop_reason or ui_text.AGENT_DID_NOT_COMPLETE
    return None


def _judge_outcome(
    wiring: Wiring,
    run: RunRecord,
    step: StepDef,
    record: StepRecord,
    declared: Outcome,
    may_close: bool,
) -> tuple[LoopSignal | None, str]:
    """A step that declares its outcome is delivered only if the block says so."""
    if not declared.delivered:
        record.block()
        wiring.runs.save(run)
        return None, _blocked_reason(declared)
    if may_close and declared.closes:
        return _settle(wiring, run, record, LoopSignal.CLOSE)
    repeats = step.repeat is not None and declared.repeats
    return _settle(wiring, run, record, LoopSignal.REPEAT if repeats else None)


def _settle(
    wiring: Wiring, run: RunRecord, record: StepRecord, signal: LoopSignal | None
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
        return ui_text.OUTCOME_NOT_DECLARED
    return declared.reason or ui_text.BLOCKED_WITHOUT_REASON


def _fail(wiring: Wiring, run: RunRecord, record: StepRecord) -> None:
    record.fail()
    wiring.runs.save(run)


def _template_values(
    wiring: Wiring,
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
    wiring: Wiring,
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
        sync_steps(wiring, run)
    notify(wiring, ui_text.run_stopped_at(label) if label else ui_text.RUN_STOPPED_BY_USER)


def _session_error(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return ui_text.agent_stopped_responding(str(error))
    if isinstance(error, RuntimeError | OSError):
        return ui_text.agent_session_dropped(str(error))
    return ui_text.step_crashed(f"{type(error).__name__}: {error}")
