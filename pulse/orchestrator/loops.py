"""Step loops: a range of the definition that may run more than once.

The definition allows the loop (`repeat_from`, `repeat_max`); the agent requests
another round or the end via the outcome block's `next` field.
"""

from __future__ import annotations

from dataclasses import dataclass

from pulse.store import runs as run_store
from pulse.store.runs import DONE, PENDING, SETTLED, SKIPPED
from pulse.store.workflow_defs import WorkflowDef

REPEAT = "repeat"
CLOSE = "close"


@dataclass(frozen=True)
class Loop:
    """A repeatable range of the definition."""

    start: int
    end: int


def find_loops(definition: WorkflowDef) -> dict[int, Loop]:
    """Repeatable ranges of the definition, keyed by step index.

    A `repeat_from` that does not point to an earlier step is silently ignored,
    as is a range overlapping one already found.
    """
    found: dict[int, Loop] = {}
    at = {step.step_id: index for index, step in enumerate(definition.steps)}
    for end, step in enumerate(definition.steps):
        if not step.repeat_from or step.repeat_max < 2:
            continue
        start = at.get(step.repeat_from)
        if start is None or start >= end:
            continue
        span = range(start, end + 1)
        if any(index in found for index in span):
            continue
        loop = Loop(start=start, end=end)
        for index in span:
            found[index] = loop
    return found


def repeat_loop(
    run: run_store.RunRecord, definition: WorkflowDef, loop: Loop, label: str
) -> tuple[int | None, str]:
    """Handle a request for another round: `(index to jump back to, notice)`.

    Index is `None` when the ceiling was reached. The ceiling counts the opener's
    rounds as persisted in the DB so it survives resuming the run.
    """
    ceiling = definition.steps[loop.end].repeat_max
    opener = run.step(definition.steps[loop.start].step_id)
    number = opener.rounds if opener is not None else 1
    if number >= ceiling:
        return None, f"{label}: teto de {ceiling} rodadas atingido — o que sobrou vai no relatório"
    last = number + 1 >= ceiling
    reopen_loop(run, definition, loop, last=last)
    if not last:
        return loop.start, f"{label} pediu a {number + 1}ª rodada"
    who = opener.label if opener else "o início do laço"
    return loop.start, f"{label} pediu a {number + 1}ª rodada — a última: só {who} roda"


def reopen_loop(
    run: run_store.RunRecord,
    definition: WorkflowDef,
    loop: Loop,
    *,
    last: bool = False,
) -> None:
    """Reset the range's steps to `pending` and count one more round on the opener.

    Rounds reuse the same `step_id`s so the panel keeps one row per step. On the
    `last` round only the opener is reopened, so the closer never gets the final
    word on its own fix. Elapsed time accumulates via [pulse.store.runs.carry_round].
    """
    steps = definition.steps[loop.start : loop.start + 1 if last else loop.end + 1]
    for step in steps:
        record = run.step(step.step_id)
        if record is None:
            continue
        if step.step_id == definition.steps[loop.start].step_id:
            record.rounds += 1
        record.carried_seconds = run_store.carry_round(run.id, step.step_id)
        record.waiting_seconds = 0.0
        record.status = PENDING
        record.summary = ""
        record.started_at = ""
        record.ended_at = ""
        record.acp_session_id = ""
        run_store.save_step(run.id, record)


def close_loop(run: run_store.RunRecord, definition: WorkflowDef, loop: Loop) -> int:
    """Settle the rest of the range without running it; return the index to continue from.

    Steps that ran in an earlier round become `done`; steps that never ran become `skipped`.
    """
    opener = run.step(definition.steps[loop.start].step_id)
    ran_before = opener is not None and opener.rounds > 1
    for step in definition.steps[loop.start + 1 : loop.end + 1]:
        record = run.step(step.step_id)
        if record is None or record.status in SETTLED:
            continue
        record.status = DONE if ran_before else SKIPPED
        record.summary = ""
        record.ended_at = record.ended_at or run_store.utc_now()
        run_store.save_step(run.id, record)
    return loop.end + 1
