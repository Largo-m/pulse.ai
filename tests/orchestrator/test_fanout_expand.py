"""Expanding a fan-out step into one child per listed item, in the step's place."""

from __future__ import annotations

from pulse.domain.run import RunRecord, StepRecord
from pulse.domain.workflow import StepDef
from pulse.orchestrator.fanout import POSITION_STRIDE, Item, expand, parse_items

LIST = "```pulse:items\n- T1: First\n- T2: Second\n```"


def _step(*, fan_out: bool = True) -> StepDef:
    return StepDef(
        workflow_id="demo",
        step_id="impl",
        position=2,
        label="Implement",
        agent_id="builder",
        prompt_template="{{item_label}}",
        requires_approval=False,
        fan_out=fan_out,
    )


def _run(*steps: StepRecord) -> RunRecord:
    return RunRecord(id="run", workflow_id="demo", workspace_root="/w", steps=list(steps))


def test_children_take_the_place_and_the_agent_of_the_fan_out_step():
    run = _run(
        StepRecord(step_id="plan", position=1000, label="Plan", agent_id="planner"),
        StepRecord(step_id="impl", position=2000, label="Implement", agent_id="builder"),
        StepRecord(step_id="review", position=3000, label="Review", agent_id="reviewer"),
    )

    units = expand(run, _step(), LIST)

    assert [(unit.step_id, unit.label, unit.position) for unit, _item in units] == [
        ("impl:T1", "First", 2001),
        ("impl:T2", "Second", 2002),
    ]
    assert [item for _unit, item in units] == [Item("T1", "First"), Item("T2", "Second")]
    assert [(step.step_id, step.position, step.agent_id) for step in run.steps] == [
        ("plan", 1000, "planner"),
        ("impl:T1", 2001, "builder"),
        ("impl:T2", 2002, "builder"),
        ("review", 3000, "reviewer"),
    ]


def test_without_a_recorded_step_children_are_placed_by_the_definition():
    run = _run()

    units = expand(run, _step(), LIST)

    base = _step().position * POSITION_STRIDE
    assert [unit.position for unit, _item in units] == [base + 1, base + 2]
    assert [(step.step_id, step.position) for step in run.steps] == [
        ("impl:T1", base + 1),
        ("impl:T2", base + 2),
    ]


def test_a_step_that_does_not_fan_out_runs_once_as_defined():
    run = _run()

    assert expand(run, _step(fan_out=False), LIST) == [(_step(fan_out=False), None)]
    assert run.steps == []


def test_lines_that_are_not_items_do_not_end_the_list():
    text = "```pulse:items\nTasks, in order:\n\n- T1: First\n- T2: Second\n```"

    assert [item.id for item in parse_items(text)] == ["T1", "T2"]
