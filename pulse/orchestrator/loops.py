"""Step loops: a range of the definition that may run more than once.

The definition holds the loop and its rounds ([pulse.domain.workflow.Loop]);
the agent requests another round or the end via the outcome block's `next`
field. This module applies that decision to the run; the engine saves it.
"""

from __future__ import annotations

from pulse.domain.run import RunRecord
from pulse.domain.workflow import Loop, WorkflowDef


def repeat_loop(
    run: RunRecord, definition: WorkflowDef, loop: Loop, label: str
) -> tuple[int | None, str]:
    """Handle a request for another round: `(index to jump back to, notice)`.

    Index is `None` when the ceiling was reached. The ceiling counts the opener's
    rounds as stored on the run so it survives resuming the run. Rounds reuse
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
    if not following.last:
        return loop.start, f"{label} pediu a {following.number}ª rodada"
    who = opener.label if opener else "o início do laço"
    return loop.start, f"{label} pediu a {following.number}ª rodada — a última: só {who} roda"


def close_loop(run: RunRecord, definition: WorkflowDef, loop: Loop) -> int:
    """Settle the rest of the range without running it; return the index to continue from.

    Steps that ran in an earlier round become `done`; steps that never ran become `skipped`.
    """
    run.close_loop(
        [definition.steps[index].step_id for index in loop.rest],
        opener_id=definition.steps[loop.start].step_id,
    )
    return loop.end + 1
