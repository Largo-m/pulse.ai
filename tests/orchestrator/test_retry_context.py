"""A retried step learns which files its failed attempt already wrote.

A retry opens a fresh ACP session: without this, the agent repeats the step from
scratch and may write the same artifact under another name, leaving two
versions of it in the run (issue #62).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pulse.domain import run as run_model
from pulse.orchestrator.agent_text import earlier_attempt_block
from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import approved_turn, delivered_turn

_HEADING = earlier_attempt_block(["any"]).strip().splitlines()[0]


def _fails_after_writing(wired, step_id: str, *paths: str):
    """`before_turn` hook: the first turn of `step_id` writes `paths`, then the session dies."""
    attempts: list[str] = []

    def hook(current: str) -> dict | None:
        if current != step_id:
            return None
        attempts.append(current)
        if len(attempts) > 1:
            return None
        for path in paths:
            wired.runs.add_artifact(wired.runs.ids()[0], path, step_id=step_id)
        raise RuntimeError("o processo do agente encerrou")

    return hook


def test_a_retry_lists_the_files_the_failed_attempt_wrote(wired, tmp_path: Path):
    make_workflow("demo", steps=[("spec", "Spec")])
    runner = FakeAgentSession(
        [approved_turn()],
        before_turn=_fails_after_writing(wired, "spec", "specs/login-sso/PRD.md"),
    )
    runner.prompts.choice = "retry"

    code = wired.run(runner, workflow_id="demo", user_prompt="x")

    assert code == 0
    first, retry = runner.sent
    assert _HEADING not in first
    assert earlier_attempt_block(["specs/login-sso/PRD.md"]) in retry


def test_files_of_other_steps_stay_out_of_the_retry_block(wired, tmp_path: Path):
    """Other steps' files reach a step through `{{artifacts}}` when its template asks."""
    make_workflow("demo", steps=[("plan", "Plano"), ("spec", "Spec")])

    def plan_writes_its_file(step_id: str) -> dict | None:
        if step_id == "plan":
            wired.runs.add_artifact(runner.run_id, "PLAN.md", step_id="plan")
            return approved_turn()
        return spec_fails(step_id)

    spec_fails = _fails_after_writing(wired, "spec", "specs/PRD.md")
    runner = FakeAgentSession([approved_turn()], before_turn=plan_writes_its_file)
    runner.prompts.choice = "retry"

    wired.run(runner, workflow_id="demo", user_prompt="x")

    retry = runner.sent[-1]
    assert earlier_attempt_block(["specs/PRD.md"]) in retry
    assert "PLAN.md" not in retry


def test_a_retry_of_a_step_that_wrote_nothing_has_no_block(wired, tmp_path: Path):
    make_workflow("demo", steps=[("spec", "Spec")])
    runner = FakeAgentSession([RuntimeError("o processo do agente encerrou"), approved_turn()])
    runner.prompts.choice = "retry"

    wired.run(runner, workflow_id="demo", user_prompt="x")

    assert len(runner.sent) == 2
    assert all(_HEADING not in prompt for prompt in runner.sent)


def test_a_new_loop_round_is_not_a_retry(wired, monkeypatch, tmp_path: Path):
    """Each round writes its own files on purpose: the block must not ask to overwrite them.

    A retry inside a later round lists only that round's files.
    """
    clock = [datetime(2026, 1, 1, tzinfo=UTC)]

    def tick() -> datetime:
        clock[0] += timedelta(minutes=1)
        return clock[0]

    monkeypatch.setattr(run_model, "utc_now", tick)
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        prompt_template="step {{step_id}}",
        repeat=("fix", "review", 3),
    )
    reviews: list[str] = []

    def review_writes_its_round(step_id: str) -> dict | None:
        if step_id != "review":
            return None
        reviews.append(step_id)
        round_file = "reviews/round-001.md" if len(reviews) == 1 else "reviews/round-002.md"
        wired.runs.add_artifact(runner.run_id, round_file, step_id="review")
        if len(reviews) == 2:
            raise RuntimeError("o processo do agente encerrou")
        return delivered_turn()

    runner = FakeAgentSession(
        [_repeating(), delivered_turn(), delivered_turn()],
        before_turn=review_writes_its_round,
    )
    runner.prompts.choice = "retry"

    code = wired.run(runner, workflow_id="demo", user_prompt="x")

    assert code == 0
    review_prompts = [prompt for prompt in runner.sent if prompt.startswith("step review")]
    first_round, second_round, retry = review_prompts[:3]
    assert _HEADING not in first_round
    assert _HEADING not in second_round
    assert earlier_attempt_block(["reviews/round-002.md"]) in retry


def _repeating() -> dict[str, object]:
    return {
        "stopReason": "end_turn",
        "phaseSummary": "falta corrigir\n\n```pulse:outcome\nstatus: done\nnext: repeat\n```",
    }


def test_the_block_names_each_file_and_asks_to_reuse_them():
    block = earlier_attempt_block(["docs/a.md", "src/b.py"])

    assert "- docs/a.md\n- src/b.py\n" in block
    assert "sobrescreva" in block


def test_no_files_means_no_block():
    assert earlier_attempt_block([]) == ""
