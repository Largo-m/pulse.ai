"""Loops: a step may send the run back to repeat a span, within its round cap."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from pulse.domain import run as run_model
from pulse.domain.control import RUN_STOPPED, RunControl
from pulse.domain.workflow import RepeatRule
from pulse.store.workflow_defs import save_workflow
from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import approved_turn, delivered_turn


def _repeating(summary: str = "corrigi") -> dict:
    """Turn of a step that delivered and asks for another loop round."""
    return {
        "stopReason": "end_turn",
        "phaseSummary": f"{summary}\n\n```pulse:outcome\nstatus: done\nnext: repeat\n```",
    }


def test_a_step_can_send_the_run_back_to_repeat_the_stretch(wired, monkeypatch, tmp_path):
    """The loop: review, fix, review again, until nobody asks for more."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    runner = FakeAgentSession(
        [
            delivered_turn(),
            _repeating(),
            delivered_turn(),
            _repeating(),
            delivered_turn(),
            delivered_turn(),
        ]
    )

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    record = wired.runs.only()
    assert [step.step_id for step in record.steps] == ["review", "fix"]
    assert all(step.status == "done" for step in record.steps)
    assert record.step("review").rounds == 3
    assert record.step("fix").rounds == 1


def test_without_a_request_the_loop_runs_only_once(wired, monkeypatch, tmp_path):
    """`repeat_from` is a permission, not an obligation: no request, no repeat."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    runner = FakeAgentSession([delivered_turn(), delivered_turn()])

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    record = wired.runs.only()
    assert [step.step_id for step in record.steps] == ["review", "fix"]
    assert record.step("review").rounds == 1


def test_the_round_cap_ends_the_loop(wired, monkeypatch, tmp_path):
    """Without a cap, an agent that always asks for one more leaves the run endless."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 2),
    )
    runner = FakeAgentSession([delivered_turn(), _repeating(), delivered_turn(), _repeating()])

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    record = wired.runs.only()
    assert [step.step_id for step in record.steps] == ["review", "fix"]
    assert record.step("review").rounds == 2, "stopped at the second, as the cap dictates"
    assert record.status == "completed"


def test_the_loop_ends_on_its_opener_never_on_its_closer(wired, monkeypatch, tmp_path):
    """Review -> fix -> review: at the cap, fix does not run after the last review.

    The closer asks for another round because it changed something nobody checked.
    Letting it run in the last round would end the run on an unchecked fix.
    """
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    runner = FakeAgentSession(
        [
            delivered_turn("r1"),
            _repeating("f1"),
            delivered_turn("r2"),
            _repeating("f2"),
            delivered_turn("r3"),
            _repeating("f3 — não deveria rodar"),
        ]
    )

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert len(runner.sent) == 5
    assert len(runner._results) == 1
    record = wired.runs.only()
    assert record.step("review").rounds == 3
    assert all(step.status == "done" for step in record.steps)
    assert any("a última" in message for message in runner.stream.messages)


def test_the_cap_counts_recorded_rounds_on_resume(wired, monkeypatch, tmp_path):
    """Resuming mid-loop does not give back rounds already spent."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    control = RunControl()
    fixes = 0

    def stop_at_the_second_fix(step_id: str) -> dict | None:
        nonlocal fixes
        if step_id != "fix":
            return None
        fixes += 1
        if fixes < 2:
            return None
        control.stop()
        return {"stopReason": "cancelled"}

    first = FakeAgentSession(
        [delivered_turn(), _repeating(), delivered_turn()],
        control=control,
        before_turn=stop_at_the_second_fix,
    )
    assert wired.run(first, workflow_id="demo", user_prompt="x") == RUN_STOPPED
    run_id = wired.runs.only().id
    assert wired.runs.load(run_id).step("review").rounds == 2

    second = FakeAgentSession([_repeating(), delivered_turn(), _repeating("não deveria rodar")])
    code = wired.run(
        second,
        workflow_id="demo",
        user_prompt="x",
        resume_run_id=run_id,
    )

    assert code == 0
    assert len(second.sent) == 2
    assert len(second._results) == 1
    assert wired.runs.load(run_id).step("review").rounds == 3


def test_round_time_adds_up_instead_of_resetting(wired, monkeypatch, tmp_path):
    """Each round reopens the clock, but time spent by earlier rounds is kept."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    runner = FakeAgentSession([delivered_turn(), _repeating(), delivered_turn(), delivered_turn()])

    start = datetime(2026, 10, 6, tzinfo=UTC)
    seconds = iter(range(0, 10_000, 10))
    monkeypatch.setattr(
        run_model,
        "utc_now",
        lambda: start + timedelta(seconds=next(seconds)),
    )

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    record = wired.runs.only()
    review = record.step("review")
    assert review.rounds == 2
    assert review.carried_seconds > 0
    assert review.started_at
    assert review.ended_at
    assert review.elapsed_seconds() > review.carried_seconds


def _clean(summary: str = "nada a corrigir", *, approval: bool = False) -> dict:
    """Turn of the loop opener that found nothing to fix: no approval."""
    result = {
        "stopReason": "end_turn",
        "phaseSummary": f"{summary}\n\n```pulse:outcome\nstatus: done\nnext: close\n```",
    }
    if approval:
        result.update(approved=False, outcome="unknown")
    return result


def test_clean_review_ends_the_loop_without_asking_approval(wired, monkeypatch, tmp_path):
    """The loop ends on the reviewer: a review without findings does not call fix."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix"), ("after", "Depois")],
        repeat=("fix", "review", 3),
    )
    runner = FakeAgentSession([_clean(approval=True), approved_turn("depois")])

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert len(runner.sent) == 2, "review and the step after the loop; fix does not run"
    record = wired.runs.only()
    assert record.status == "completed"
    assert [step.status for step in record.steps] == ["done", "skipped", "done"]
    assert any("laço encerrado" in message for message in runner.stream.messages)


def test_clean_review_in_a_later_round_keeps_the_fix_that_already_ran(wired, monkeypatch, tmp_path):
    """Review -> fix -> clean review: the round-1 fix delivered and stays `done`."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    runner = FakeAgentSession([delivered_turn("r1"), _repeating("f1"), _clean("r2")])

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert len(runner.sent) == 3
    record = wired.runs.only()
    assert record.step("review").rounds == 2
    assert [step.status for step in record.steps] == ["done", "done"]


def test_closing_one_loop_does_not_skip_the_next_one(wired, monkeypatch, tmp_path):
    """Verify -> fix -> clean verify, then review -> fix -> clean review.

    Two loops in a row: the first closing must settle only its own range, and
    the second must count its rounds from zero.
    """
    definition = make_workflow(
        "demo",
        steps=[
            ("verify", "Verificar"),
            ("verify-fix", "Corrigir lacunas"),
            ("review", "Review"),
            ("review-fix", "Fix review"),
        ],
        repeat=("verify-fix", "verify", 3),
    )
    fixes = {"verify-fix": "verify", "review-fix": "review"}
    save_workflow(
        replace(
            definition,
            steps=tuple(
                replace(step, requires_approval=False, repeat=RepeatRule(fixes[step.step_id], 3))
                if step.step_id in fixes
                else step
                for step in definition.steps
            ),
        )
    )
    runner = FakeAgentSession(
        [
            approved_turn("FAIL, 2 lacunas"),
            _repeating("lacunas corrigidas"),
            _clean("PASS", approval=True),
            approved_turn("2 findings"),
            _repeating("findings corrigidas"),
            _clean("approved", approval=True),
        ]
    )

    code = wired.run(runner, workflow_id="demo", user_prompt="x")

    assert code == 0
    assert len(runner.sent) == 6
    record = wired.runs.only()
    assert [(step.step_id, step.status, step.rounds) for step in record.steps] == [
        ("verify", "done", 2),
        ("verify-fix", "done", 1),
        ("review", "done", 2),
        ("review-fix", "done", 1),
    ]


def test_only_the_loop_opener_can_waive_approval(wired, monkeypatch, tmp_path):
    """Outside a loop opener, `next: close` does not count as approval."""
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = FakeAgentSession([_clean(approval=True)])

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    record = wired.runs.only()
    assert record.step("one").status == "failed"
    assert record.step("two").status == "pending"
    assert any("sem o bloco de aprovação" in prompt for prompt in runner.prompts.prompts)


def test_repeat_request_is_ignored_where_the_workflow_declared_no_loop(
    wired, monkeypatch, tmp_path
):
    """An agent cannot create a loop where the definition did not open one."""
    make_workflow(
        "demo",
        steps=[("one", "Um"), ("two", "Dois")],
        requires_approval=False,
    )
    runner = FakeAgentSession([_repeating(), _repeating()])

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    record = wired.runs.only()
    assert [step.step_id for step in record.steps] == ["one", "two"]


def test_steps_after_the_loop_do_not_count_rounds(wired, monkeypatch, tmp_path):
    """The counter belongs to the loop range, not to everything after it."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix"), ("ship", "Ship")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    runner = FakeAgentSession(
        [delivered_turn(), _repeating(), delivered_turn(), delivered_turn(), delivered_turn()]
    )

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    record = wired.runs.only()
    assert [step.step_id for step in record.steps] == ["review", "fix", "ship"]
    assert record.step("review").rounds == 2
    assert record.step("ship").rounds == 1


def test_loop_rounds_stay_under_the_same_step(wired, monkeypatch, tmp_path):
    """One row per step in the panel, with log and artifacts from every round.

    This is what makes `Review` show `round-001.md` and `round-002.md` together:
    `visible_artifacts()` filters by `phase_id`, so rounds only appear together
    if they share the `step_id`.
    """
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    rounds: list[int] = []

    def each_review_writes_its_round(step_id: str) -> None:
        if step_id == "review":
            rounds.append(len(rounds) + 1)
            wired.runs.add_artifact(runner.run_id, f"reviews/round-00{len(rounds)}.md")

    runner = FakeAgentSession(
        [delivered_turn(), _repeating(), delivered_turn(), delivered_turn()],
        before_turn=each_review_writes_its_round,
    )

    wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    record = wired.runs.only()
    assert [step.step_id for step in record.steps] == ["review", "fix"]
    assert record.step("review").rounds == 2

    assert wired.runs.artifacts(record.id) == ["reviews/round-001.md", "reviews/round-002.md"]
