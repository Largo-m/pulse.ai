"""Fan-out: one definition step that becomes N in the run, one per listed item."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_workflow
from tests.test_engine_steps import (  # noqa: F401
    _approved,
    _blocked,
    _delivered,
    _install,
    _Runner,
    wired,
)

from pulse.orchestrator import engine
from pulse.orchestrator.fanout import MAX_ITEMS, parse_items
from pulse.orchestrator.engine import run_workflow
from pulse.store import runs as run_store


def _block(*lines: str) -> str:
    body = "\n".join(lines)
    return f"Resumo da fase.\n\n```pulse:items\n{body}\n```\n"


def test_reads_the_items_from_the_fenced_block():
    items = parse_items(_block("T1 — Criar o endpoint", "T2 - Montar o CSV", "T3: Testar"))

    assert [(item.id, item.label) for item in items] == [
        ("T1", "Criar o endpoint"),
        ("T2", "Montar o CSV"),
        ("T3", "Testar"),
    ]


def test_text_without_a_block_has_no_items():
    """No block means no fan-out and no error: the step runs once."""
    assert parse_items("Escrevi tasks.md com 3 tarefas.") == ()
    assert parse_items("") == ()


def test_the_last_block_wins():
    """A re-presented adjustment: the bottom list is the one that counts."""
    text = _block("T1 — Antigo") + _block("T1 — Novo", "T2 — Extra")

    assert [item.label for item in parse_items(text)] == ["Novo", "Extra"]


def test_a_repeated_id_is_dropped():
    """A repeated id would become a duplicate `step_id` and overwrite the first."""
    items = parse_items(_block("T1 — Primeiro", "T1 — Repetido", "T2 — Segundo"))

    assert [item.id for item in items] == ["T1", "T2"]


def test_the_item_count_is_capped():
    items = parse_items(_block(*(f"T{index} — Task" for index in range(1, MAX_ITEMS + 10))))

    assert len(items) == MAX_ITEMS


def test_each_item_becomes_its_own_step_and_its_own_session(wired, monkeypatch, tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
        prompt_template="{{user_prompt}}{{#if item_id}} | {{item_id}} {{item_index}}/{{item_total}}{{/if}}",
    )
    runner = _Runner(
        [
            _approved(_block("T1 — Criar o endpoint", "T2 — Montar o CSV")),
            _approved(),
            _approved(),
        ]
    )
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="exportar csv",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    record = run_store.list_runs(tmp_path)[0]
    assert [(step.step_id, step.label, step.status) for step in record.steps] == [
        ("plan", "Planejar", "done"),
        ("run:T1", "Criar o endpoint", "done"),
        ("run:T2", "Montar o CSV", "done"),
    ]
    assert runner.prompts[1].endswith("| T1 1/2")
    assert runner.prompts[2].endswith("| T2 2/2")


def test_the_panel_receives_the_expanded_step_list(wired, monkeypatch, tmp_path: Path):
    """The panel built phases from the definition; fan-out changes that midway."""
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    runner = _Runner([_approved(_block("T1 — Um", "T2 — Dois")), _approved(), _approved()])
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    last = runner._stream.statuses[-1]
    assert [step["id"] for step in last["steps"]] == ["plan", "run:T1", "run:T2"]
    assert [step["label"] for step in last["steps"]] == ["Planejar", "Um", "Dois"]


def test_a_step_that_declares_nothing_still_runs_once(wired, monkeypatch, tmp_path: Path):
    """A protocol the agent did not follow is no reason to stop the run."""
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    runner = _Runner([_approved("Escrevi o plano, sem bloco."), _approved()])
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == ["plan", "run"]


def test_resuming_does_not_redo_an_item_that_already_passed(wired, monkeypatch, tmp_path: Path):
    """Resuming redoes the remaining item, not the whole list."""
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    summary = _block("T1 — Um", "T2 — Dois")
    failing = _Runner([_approved(summary), _approved(), {"approved": False, "outcome": "approve"}])
    _install(monkeypatch, failing)
    assert (
        run_workflow(
            workflow_id="demo",
            user_prompt="x",
            stream=failing._stream,
            prompt_handler=failing._prompt_handler,
            render_header=False,
        )
        != 0
    )
    run_id = run_store.list_runs(tmp_path)[0].id

    resumed = _Runner([_approved()])
    _install(monkeypatch, resumed)
    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=resumed._stream,
        prompt_handler=resumed._prompt_handler,
        render_header=False,
        resume_run_id=run_id,
    )

    assert code == 0
    assert len(resumed.prompts) == 1
    record = run_store.load_run(run_id)
    assert record is not None
    assert [(step.step_id, step.status) for step in record.steps] == [
        ("plan", "done"),
        ("run:T1", "done"),
        ("run:T2", "done"),
    ]


def test_items_keep_their_order_beyond_nine(wired, monkeypatch, tmp_path: Path):
    """`run_steps` sorts by position: T10 must not land between T1 and T2."""
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    ids = [f"T{index}" for index in range(1, 12)]
    runner = _Runner(
        [_approved(_block(*(f"{item} — Task {item}" for item in ids)))]
        + [_approved() for _ in ids]
    )
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == ["plan"] + [f"run:{item}" for item in ids]


def test_every_item_is_recorded_before_the_first_one_runs(
    wired, monkeypatch, tmp_path: Path
):
    """The N children are persisted at expansion, not when each one starts.

    A child that only existed in memory vanished if the run crashed mid fan-out:
    history reopened with only the tasks that had already run.
    """
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    ids = [f"T{index}" for index in range(1, 11)]
    runner = _Runner(
        [
            _approved(_block(*(f"{item} — Task {item}" for item in ids))),
            _approved(),
            RuntimeError("o processo do agente encerrou"),
        ]
    )
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 1
    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == ["plan"] + [f"run:{item}" for item in ids]
    assert [step.status for step in record.steps[:3]] == ["done", "done", "failed"]
    assert {step.status for step in record.steps[3:]} == {"pending"}


def test_resuming_keeps_the_fan_out_instead_of_redoing_the_parent_step(
    wired, monkeypatch, tmp_path: Path
):
    """The parent does not come back: on resume, the items block is still the previous step's.

    The previous-summary lookup used to stop at the parent step, which fan-out
    removed. Without it, the scan picked the last task's summary, which has no
    `pulse:items` block, so fan-out collapsed and `run` ran as a single step.
    """
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    first = _Runner(
        [
            _approved(_block("T1 — Um", "T2 — Dois")),
            _approved("terminei a T1, sem bloco de itens"),
            RuntimeError("o processo do agente encerrou"),
        ]
    )
    first._prompt_handler.choice = "stop"
    _install(monkeypatch, first)
    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=first._stream,
        prompt_handler=first._prompt_handler,
        render_header=False,
    )
    run_id = run_store.list_runs(tmp_path)[0].id

    resumed = _Runner([_approved()])
    _install(monkeypatch, resumed)
    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=resumed._stream,
        prompt_handler=resumed._prompt_handler,
        render_header=False,
        resume_run_id=run_id,
    )

    assert code == 0
    record = run_store.load_run(run_id)
    assert record is not None
    assert [(step.step_id, step.status) for step in record.steps] == [
        ("plan", "done"),
        ("run:T1", "done"),
        ("run:T2", "done"),
    ]


def test_a_blocked_task_does_not_drag_the_next_ones_along(wired, monkeypatch, tmp_path: Path):
    """The original case: T2 got stuck and T3 ran anyway.

    Each task has an isolated session, so T3 would not know T2 did not deliver.
    The engine has to know, and it stops at the blocked task.
    """
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
        requires_approval=False,
    )
    runner = _Runner(
        [
            _delivered(_block("T1 — Um", "T2 — Dois", "T3 — Três")),
            _delivered(),
            _blocked("a migration depende de uma decisão de schema", needs="user"),
        ]
    )
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == engine.RUN_BLOCKED
    record = run_store.list_runs(tmp_path)[0]
    assert [(step.step_id, step.status) for step in record.steps] == [
        ("plan", "done"),
        ("run:T1", "done"),
        ("run:T2", "blocked"),
        ("run:T3", "pending"),
    ]
    assert len(runner.prompts) == 3, "T3 never opened a session"
    assert runner._stream.statuses[-1]["blocked_ids"] == ["run:T2"]


def test_children_inherit_requires_outcome(tmp_path: Path):
    from pulse.orchestrator.fanout import expand
    from pulse.store.workflow_defs import StepDef

    step = StepDef(
        workflow_id="demo",
        step_id="impl",
        position=2,
        label="Implementar",
        agent_id="implement",
        prompt_template="",
        requires_approval=False,
        fan_out=True,
        requires_outcome=False,
    )
    run = run_store.create_run(
        run_id="run-fan",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[],
    )

    units = expand(run, step, _block("- T1: primeira", "- T2: segunda"))

    assert [child.requires_outcome for child, _item in units] == [False, False]
