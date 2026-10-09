"""A step closes on its declared outcome: delivered, blocked, or asked for once more."""

from __future__ import annotations

from pathlib import Path

from pulse.domain.control import RUN_BLOCKED
from pulse.domain.ports import NullPromptPort
from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import approved_turn, blocked_turn, delivered_turn


def test_a_step_without_approval_closes_when_the_agent_declares_the_outcome(
    wired, monkeypatch, tmp_path: Path
):
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    runner = FakeAgentSession([delivered_turn("pronto")])

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert wired.runs.only().step("one").status == "done"


def test_ending_the_turn_is_no_longer_enough_for_a_step_to_count_as_done(
    wired, monkeypatch, tmp_path: Path
):
    """The old rule (`end_turn` means success) was the whole hole.

    An agent answering "I can't" ended the turn like any other, the step
    became `done` and the next one ran on top of nothing.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    runner = FakeAgentSession(
        [
            {"stopReason": "end_turn", "phaseSummary": "não consigo: falta a credencial"},
            {"stopReason": "end_turn", "phaseSummary": "continuo sem conseguir"},
        ]
    )
    runner.prompts.choice = "stop"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == RUN_BLOCKED
    record = wired.runs.only()
    assert record.step("one").status == "blocked"
    assert record.step("two").status == "pending", "the cascade stops at the blocked step"
    assert record.status == "blocked", "a block is not a failure"


def test_a_declared_block_stops_the_run_instead_of_cascading(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    runner = FakeAgentSession([blocked_turn("falta a credencial do banco", needs="user")])
    runner.prompts.choice = "stop"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == RUN_BLOCKED
    assert runner.prompts.asked == ["Um está bloqueado"]
    assert runner.prompts.prompts == ["falta a credencial do banco"], (
        "the reason the agent declared is what the user reads"
    )
    assert len(runner.sent) == 1, "`needs: user` does not spend a self-resolution turn"
    record = wired.runs.only()
    assert [step.status for step in record.steps] == ["blocked", "pending"]


def test_an_unknown_outcome_word_reaches_the_user_in_the_engine_wording(wired):
    """The menu says which word the agent used, in the language of the menu (ADR 0004)."""
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    turn = {
        "stopReason": "end_turn",
        "phaseSummary": "```pulse:outcome\nstatus: maybe\nneeds: user\n```",
    }
    runner = FakeAgentSession([turn])
    runner.prompts.choice = "stop"

    code = wired.run(runner, workflow_id="demo", user_prompt="x")

    assert code == RUN_BLOCKED
    assert runner.prompts.prompts == [
        "o agente declarou um desfecho que o Pulse não conhece: `maybe`"
    ]


def test_a_blocked_step_gets_one_shot_at_unblocking_itself(wired, monkeypatch, tmp_path: Path):
    """What the agent can fix itself does not wake anyone up.

    Without `needs`, the engine hands the block back to the agent once, in the
    same session so it does not start from scratch, before escalating.
    """
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    runner = FakeAgentSession(
        [blocked_turn("o arquivo de config não existe"), delivered_turn("criei o config e segui")]
    )

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert runner.prompts.asked == [], "nobody was interrupted"
    assert len(runner.sent) == 2
    assert "Bloqueio declarado" in runner.sent[1]
    assert "o arquivo de config não existe" in runner.sent[1]
    assert wired.runs.only().step("one").status == "done"


def test_the_agent_gets_only_one_shot_before_the_person_is_called(
    wired, monkeypatch, tmp_path: Path
):
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    runner = FakeAgentSession([blocked_turn("falta X"), blocked_turn("continua faltando X")])
    runner.prompts.choice = "stop"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == RUN_BLOCKED
    assert len(runner.sent) == 2, "two attempts, not a ping-pong"
    assert runner.prompts.prompts == ["continua faltando X"]


def test_a_forgotten_outcome_block_is_asked_for_before_it_becomes_a_block(
    wired, monkeypatch, tmp_path: Path
):
    """Forgetting the block is the most common case, and the cheapest to fix.

    Otherwise every distracted agent would become an on-screen question, the
    exact friction that would make the protocol not worth it.
    """
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    runner = FakeAgentSession(
        [{"stopReason": "end_turn", "phaseSummary": "terminei tudo"}, delivered_turn()]
    )

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert runner.prompts.asked == []
    assert "Desfecho do step" in runner.sent[1]
    assert wired.runs.only().step("one").status == "done"


def test_skipping_a_blocked_step_records_it_as_skipped_not_done(wired, monkeypatch, tmp_path: Path):
    """The explicit skip is the difference: it used to happen disguised as `done`."""
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    runner = FakeAgentSession([blocked_turn("falta acesso", needs="user"), delivered_turn()])
    runner.prompts.choice = "skip"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    record = wired.runs.only()
    assert [step.status for step in record.steps] == ["skipped", "done"]


def test_a_step_that_did_not_deliver_does_not_feed_the_next_one(wired, monkeypatch, tmp_path: Path):
    """The poisoned summary: the next step must not receive "I couldn't".

    It gets the summary of the last step that actually delivered (here, the
    first), not the one that got stuck and was skipped.
    """
    make_workflow(
        "demo",
        steps=[("one", "Um"), ("two", "Dois"), ("three", "Três")],
        requires_approval=False,
        prompt_template="{{#if previous_summary}}antes: {{previous_summary}}{{/if}}siga",
    )
    runner = FakeAgentSession(
        [
            delivered_turn("escrevi o plano"),
            blocked_turn("não consegui migrar o schema", needs="user"),
            delivered_turn(),
        ]
    )
    runner.prompts.choice = "skip"

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert "não consegui migrar o schema" not in runner.sent[2]
    assert runner.sent[2].startswith("antes: escrevi o plano")


def test_requires_outcome_off_brings_the_old_behaviour_back(wired, monkeypatch, tmp_path: Path):
    """The escape hatch, for workflows that have not adopted the protocol yet."""
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False, requires_outcome=False)
    runner = FakeAgentSession([{"stopReason": "end_turn", "phaseSummary": "pronto"}])

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert runner.sent == ["x"], "without the protocol, the prompt stays as the author wrote it"
    assert wired.runs.only().step("one").status == "done"


def test_an_approval_step_keeps_the_person_as_the_only_gate(wired, monkeypatch, tmp_path: Path):
    """A step has a single gate: where there is approval, the user attests."""
    make_workflow("demo", steps=[("one", "Um")], requires_approval=True)
    runner = FakeAgentSession([approved_turn("entreguei")])

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == 0
    assert runner.sent == ["x"], "no outcome request where approval already exists"


def test_with_nobody_to_ask_a_blocked_run_stops_instead_of_going_on(
    wired, monkeypatch, tmp_path: Path
):
    """The Null prompt port answers nothing: the safe default is to stop, saying why."""
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    runner = FakeAgentSession([blocked_turn("falta acesso", needs="user")])
    runner.prompts = NullPromptPort()

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == RUN_BLOCKED
    record = wired.runs.only()
    assert [step.status for step in record.steps] == ["blocked", "pending"]
    assert "Um está bloqueado: falta acesso" in runner.stream.messages
