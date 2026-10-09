"""When a step fails, times out or is not approved: retry, skip or stop, never a hidden failure."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pulse.domain import run as run_model
from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import approved_turn


def test_a_step_that_is_not_approved_stops_the_run(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = FakeAgentSession([{"approved": False, "outcome": "continue"}])
    runner.prompts.choice = "stop"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 1
    record = wired.runs.only()
    assert record.step("one").status == "failed"
    assert record.step("two").status == "pending", "the next step never ran"


def test_retry_runs_the_same_step_again(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um")])
    runner = FakeAgentSession([{"approved": False, "outcome": "continue"}, approved_turn()])
    runner.prompts.choice = "retry"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert len(runner.sent) == 2
    assert wired.runs.only().step("one").status == "done"


def test_a_timeout_offers_retry_instead_of_killing_the_run(wired, monkeypatch, tmp_path: Path):
    """A timed-out session is a failed attempt, not the end of the run."""
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = FakeAgentSession(
        [
            TimeoutError("the agent gave no sign of life for 600s in `session/prompt`"),
            approved_turn(),
            approved_turn(),
        ]
    )
    runner.prompts.choice = "retry"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert runner.prompts.asked == ["Step Um falhou"]
    assert runner.revivals == 1
    record = wired.runs.only()
    assert [step.status for step in record.steps] == ["done", "done"]


def test_a_dead_session_that_the_user_gives_up_on_fails_the_step(
    wired, monkeypatch, tmp_path: Path
):
    """`Parar` closes the run the normal way: failed step, no exception."""
    make_workflow("demo", steps=[("one", "Um")])
    runner = FakeAgentSession([RuntimeError("o processo do agente encerrou")])
    runner.prompts.choice = "stop"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 1
    assert runner.revivals == 0
    record = wired.runs.only()
    assert record.step("one").status == "failed"
    assert record.status == "failed"


def test_skip_settles_the_step_without_failing_the_run(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = FakeAgentSession([{"approved": False, "outcome": "skip"}, approved_turn()])

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    record = wired.runs.only()
    assert record.step("one").status == "skipped"
    assert record.step("two").status == "done"


def test_a_broken_template_fails_the_step_instead_of_prompting_a_hole(
    wired, monkeypatch, tmp_path: Path
):
    """A placeholder without a value is an error: a truncated instruction would go out silently."""
    make_workflow("demo", steps=[("one", "Um")], prompt_template="{{nao_existe}}")
    runner = FakeAgentSession([])
    runner.prompts.choice = "stop"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 1
    assert runner.sent == []


def test_an_unexpected_error_also_offers_retry(wired, monkeypatch, tmp_path: Path):
    """Not only timeouts and dead processes: any crash inside the step asks.

    The caught types used to be (Timeout, Runtime, OSError); a `ValueError` from
    an already-closed stdin killed the run with no menu and left the step
    recorded as running.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = FakeAgentSession(
        [ValueError("I/O operation on closed file"), approved_turn(), approved_turn()]
    )
    runner.prompts.choice = "retry"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert runner.prompts.asked == ["Step Um falhou"]
    record = wired.runs.only()
    assert [step.status for step in record.steps] == ["done", "done"]


def test_a_step_that_failed_is_never_left_as_running(wired, monkeypatch, tmp_path: Path):
    """The database must not keep "running" after the run ended.

    That state made the run come back from history offering neither resume nor
    restart: no step was pending, just one stuck midway.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = FakeAgentSession([RuntimeError("o processo do agente encerrou")])
    runner.prompts.choice = "stop"

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    record = wired.runs.only()
    assert [step.status for step in record.steps] == ["failed", "pending"]
    assert record.step("one").ended_at, "failure also stops the step clock"


def test_the_wait_in_the_retry_menu_stays_inside_the_step_window(
    wired, monkeypatch, tmp_path: Path
):
    """`_fail` stamps `ended_at` before the menu, and menu wait time is discounted.

    If the user gives up, the end must be restamped after the menu; otherwise the
    discount falls outside the window and the duration disappears from history.
    """
    make_workflow("demo", steps=[("one", "Um")])
    clock = [datetime(2026, 1, 1, tzinfo=UTC)]
    monkeypatch.setattr(run_model, "utc_now", lambda: clock[0])

    runner = FakeAgentSession([RuntimeError("o processo do agente encerrou")])
    stamped_before_menu: list[datetime] = []

    def stop_after_ten_minutes(prompt, choices, *, title=""):
        stamped_before_menu.append(wired.runs.only().step("one").ended_at)
        clock[0] += timedelta(minutes=10)
        return "stop"

    runner.prompts.select_choice = stop_after_ten_minutes

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 1
    step = wired.runs.only().step("one")
    assert stamped_before_menu
    assert stamped_before_menu[0]
    assert step.ended_at - stamped_before_menu[0] == timedelta(minutes=10)
