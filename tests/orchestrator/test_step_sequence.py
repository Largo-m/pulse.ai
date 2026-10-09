"""The engine runs the steps in order and hands each one what the previous step left."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import approved_turn


def test_steps_run_in_order_and_each_one_is_recorded(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois"), ("three", "Três")])
    runner = FakeAgentSession([approved_turn(), approved_turn(), approved_turn()])

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="fazer algo",
    )

    assert code == 0
    assert runner.agents == ["tester", "tester", "tester"]
    record = wired.runs.only()
    assert [(step.step_id, step.status) for step in record.steps] == [
        ("one", "done"),
        ("two", "done"),
        ("three", "done"),
    ]
    assert record.status == "completed"


def test_the_prompt_template_is_rendered_with_run_values(wired, monkeypatch, tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("one", "Um")],
        prompt_template="tarefa: {{user_prompt}} em {{workspace}} (step {{step_id}})",
    )
    runner = FakeAgentSession([approved_turn()])

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="corrigir login",
    )

    assert runner.sent == [f"tarefa: corrigir login em {tmp_path} (step one)"]


def test_a_step_sees_what_the_previous_one_produced(wired, monkeypatch, tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("one", "Um"), ("two", "Dois")],
        prompt_template="{{#if previous_summary}}antes: {{previous_summary}}{{/if}}siga",
    )
    runner = FakeAgentSession([approved_turn("escrevi o plano"), approved_turn()])

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert runner.sent[0] == "siga"
    assert runner.sent[1] == "antes: escrevi o planosiga"


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ({"approved": True, "outcome": "approve", "phaseSummary": "o review"}, "done"),
        ({"approved": False, "outcome": "skip", "phaseSummary": "o review"}, "skipped"),
    ],
)
def test_a_step_sees_how_the_previous_one_closed(
    wired, monkeypatch, tmp_path: Path, outcome: dict, expected: str
):
    """Skipped and done must not reach the next step indistinguishable.

    Without the status, the next step would get the same summary in both cases
    and build on top of a delivery the user just dismissed.
    """
    make_workflow(
        "demo",
        steps=[("one", "Um"), ("two", "Dois")],
        prompt_template="anterior: {{previous_status}}",
    )
    runner = FakeAgentSession([outcome, approved_turn()])

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert runner.sent[0] == "anterior: "
    assert runner.sent[1] == f"anterior: {expected}"
