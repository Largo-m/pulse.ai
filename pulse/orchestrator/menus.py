"""What a person decides when a step does not close: retry, guide, skip or stop.

With nobody to ask, the answer is stop: what nobody sees does not go on alone.
"""

from __future__ import annotations

from pulse.domain import ui_text
from pulse.domain.control import RUN_BLOCKED
from pulse.domain.run import RunRecord, StepRecord, StepStatus
from pulse.orchestrator.turn import MenuChoice
from pulse.orchestrator.wiring import Wiring, notify, sync_steps


def offer_next(wiring: Wiring, record: StepRecord, reason: str) -> tuple[MenuChoice, str]:
    """A blocked step may be skipped; a failed one may only be retried or abandoned."""
    if record.status == StepStatus.BLOCKED:
        return _offer_blocked(wiring, ui_text.step_blocked_title(record.label), reason)
    return _offer_retry(wiring, ui_text.step_failed_title(record.label), reason)


def end_without_retry(
    wiring: Wiring, run: RunRecord, record: StepRecord, choice: MenuChoice, reason: str
) -> int | None:
    """The run's exit code when the person chose not to retry; `None` means retry."""
    if choice == MenuChoice.RETRY:
        return None
    if record.status != StepStatus.BLOCKED:
        record.close_after_wait()
        wiring.runs.save(run)
        return 1
    if choice == MenuChoice.SKIP:
        record.skip_blocked()
        wiring.runs.save(run)
        sync_steps(wiring, run)
        notify(wiring, ui_text.step_skipped_by_user(record.label))
        return 0
    record.close_after_wait()
    wiring.runs.save(run)
    notify(wiring, ui_text.run_blocked_at(record.label, reason))
    return RUN_BLOCKED


def revive_session(wiring: Wiring) -> None:
    """Restart the agent process before retrying the step.

    Retrying on a dead session would just fail again.
    """
    try:
        if wiring.session.revive():
            notify(wiring, ui_text.AGENT_SESSION_RESTARTED)
    except (RuntimeError, TimeoutError, OSError) as error:
        notify(wiring, ui_text.agent_session_restart_failed(str(error)))


def _offer_retry(wiring: Wiring, title: str, reason: str) -> tuple[MenuChoice, str]:
    """Decide what to do with a failed step."""
    return _choose(
        wiring,
        title,
        reason,
        [
            (ui_text.RETRY, MenuChoice.RETRY),
            (ui_text.GIVE_GUIDANCE, MenuChoice.GUIDANCE),
            (ui_text.STOP, MenuChoice.STOP),
        ],
    )


def _offer_blocked(wiring: Wiring, title: str, reason: str) -> tuple[MenuChoice, str]:
    """Decide what to do with a step the agent could not complete.

    Adds a skip option, recorded as `skipped` rather than hidden as `done`.
    """
    return _choose(
        wiring,
        title,
        reason,
        [
            (ui_text.RETRY_RESOLVED, MenuChoice.RETRY),
            (ui_text.GIVE_GUIDANCE, MenuChoice.GUIDANCE),
            (ui_text.SKIP_STEP, MenuChoice.SKIP),
            (ui_text.STOP_RUN, MenuChoice.STOP),
        ],
    )


def _choose(
    wiring: Wiring,
    title: str,
    reason: str,
    choices: list[tuple[str, MenuChoice]],
) -> tuple[MenuChoice, str]:
    """Ask the user and return `(choice, guidance)`.

    The guidance option lets the user write what the agent should do. With nobody to ask,
    the answer is stop, and the reason is left on the stream for whoever reads it.
    """
    prompt = reason.strip() or ui_text.STEP_NOT_COMPLETED
    choice = wiring.session.prompts.select_choice(prompt, choices, title=title)
    if choice is None:
        if not wiring.control.interrupted:
            notify(wiring, f"{title}: {prompt}")
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


def _ask_guidance(wiring: Wiring, title: str) -> str:
    answer = wiring.session.prompts.ask_text(ui_text.GUIDANCE_QUESTION, title=title)
    return (answer or "").strip()
