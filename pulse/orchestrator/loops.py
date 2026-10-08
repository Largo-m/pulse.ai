"""Step loops: a range of the definition that may run more than once.

The definition holds the loop and its rounds ([pulse.domain.workflow.Loop]);
the agent requests another round or the end via the outcome block's `next`
field. This module applies that decision to the run and persists it.
"""

from __future__ import annotations

from pulse.domain.workflow import Loop, WorkflowDef
from pulse.store import runs as run_store


def repeat_loop(
    run: run_store.RunRecord, definition: WorkflowDef, loop: Loop, label: str
) -> tuple[int | None, str]:
    """Handle a request for another round: `(index to jump back to, notice)`.

    Index is `None` when the ceiling was reached. The ceiling counts the opener's
    rounds as persisted in the DB so it survives resuming the run. Rounds reuse
    the same `step_id`s so the panel keeps one row per step.
    """
    opener_id = definition.steps[loop.start].step_id
    opener = run.step(opener_id)
    following = loop.next_round(opener.rounds if opener is not None else 1)
    if following is None:
        return None, (
            f"{label}: teto de {loop.max_rounds} rodadas atingido — o que sobrou vai no relatório"
        )
    run.reopen_loop(
        [definition.steps[index].step_id for index in following.reopens], opener_id=opener_id
    )
    run_store.save(run)
    if not following.last:
        return loop.start, f"{label} pediu a {following.number}ª rodada"
    who = opener.label if opener else "o início do laço"
    return loop.start, f"{label} pediu a {following.number}ª rodada — a última: só {who} roda"


def close_loop(run: run_store.RunRecord, definition: WorkflowDef, loop: Loop) -> int:
    """Settle the rest of the range without running it; return the index to continue from.

    Steps that ran in an earlier round become `done`; steps that never ran become `skipped`.
    """
    run.close_loop(
        [definition.steps[index].step_id for index in loop.rest],
        opener_id=definition.steps[loop.start].step_id,
    )
    run_store.save(run)
    return loop.end + 1
