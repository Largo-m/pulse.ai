from __future__ import annotations

from pulse.domain.workflow import StepDef, WorkflowDef
from pulse.orchestrator.loops import Loop, find_loops


def _workflow(*steps: tuple[str, str]) -> WorkflowDef:
    return WorkflowDef(
        id="w",
        label="w",
        description="",
        is_default=False,
        default_prompt="",
        steps=tuple(
            StepDef(
                workflow_id="w",
                step_id=step_id,
                position=position,
                label=step_id,
                agent_id="default",
                prompt_template="",
                requires_approval=False,
                repeat_from=repeat_from,
                repeat_max=3 if repeat_from else 0,
            )
            for position, (step_id, repeat_from) in enumerate(steps, start=1)
        ),
    )


def test_a_range_crossing_another_is_ignored():
    """c goes back to a, d goes back to b: the second range used to overwrite the first."""
    loops = find_loops(_workflow(("a", ""), ("b", ""), ("c", "a"), ("d", "b")))

    assert loops[2] == Loop(start=0, end=2)
    assert 3 not in loops


def test_separate_ranges_both_count():
    loops = find_loops(_workflow(("a", ""), ("b", "a"), ("c", ""), ("d", "c")))

    assert loops[1] == Loop(start=0, end=1)
    assert loops[3] == Loop(start=2, end=3)
