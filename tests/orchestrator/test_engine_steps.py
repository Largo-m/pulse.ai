"""The engine: which agent runs now, and what happens when a step does not close."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pulse.domain import run as run_model
from pulse.domain.control import RUN_BLOCKED, RUN_STOPPED, RunControl
from pulse.domain.ports import NullPromptPort
from pulse.domain.run import RunStatus, StepStatus
from pulse.orchestrator.engine import run_workflow
from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import approved_turn, blocked_turn, delivered_turn


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


def test_resuming_picks_up_at_the_first_unfinished_step(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    first = FakeAgentSession([approved_turn(), {"approved": False, "outcome": "continue"}])
    first.prompts.choice = "stop"
    wired.run(
        first,
        workflow_id="demo",
        user_prompt="x",
    )
    run_id = wired.runs.only().id

    second = FakeAgentSession([approved_turn()])
    code = wired.run(
        second,
        workflow_id="demo",
        user_prompt="x",
        resume_run_id=run_id,
    )

    assert code == 0
    assert len(second.sent) == 1, "the already-finished step does not run again"
    assert wired.runs.ids() == [run_id], "resuming does not create another run"


def test_resuming_after_a_step_left_the_workflow_still_completes_the_run(
    wired, monkeypatch, tmp_path: Path
):
    """Definitions are editable; a step the workflow dropped must not fail every resume.

    The engine never reaches it again, so it is skipped instead of holding the run open.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois"), ("three", "Três")])
    first = FakeAgentSession([approved_turn(), {"approved": False, "outcome": "continue"}])
    first.prompts.choice = "stop"
    wired.run(
        first,
        workflow_id="demo",
        user_prompt="x",
    )
    run_id = wired.runs.only().id
    make_workflow("demo", steps=[("one", "Um"), ("three", "Três")])

    second = FakeAgentSession([approved_turn()])
    code = wired.run(
        second,
        workflow_id="demo",
        user_prompt="x",
        resume_run_id=run_id,
    )

    assert code == 0
    record = wired.runs.load(run_id)
    assert record.status == RunStatus.COMPLETED
    assert [(step.step_id, step.status) for step in record.steps] == [
        ("one", StepStatus.DONE),
        ("two", StepStatus.SKIPPED),
        ("three", StepStatus.DONE),
    ]


def test_resuming_after_a_crash_reruns_the_step_it_left_running(wired, monkeypatch, tmp_path: Path):
    """A killed daemon leaves its step `running`; only one step may run at a time.

    Resume must release that step, or a step added to the workflow before it
    can never start and the whole resume fails.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    first = FakeAgentSession([approved_turn(), {"approved": False, "outcome": "continue"}])
    first.prompts.choice = "stop"
    wired.run(
        first,
        workflow_id="demo",
        user_prompt="x",
    )
    crashed = wired.runs.only()
    two = crashed.step("two")
    two.status = run_model.StepStatus.RUNNING
    wired.runs.save(crashed)

    make_workflow("demo", steps=[("one", "Um"), ("new", "Novo"), ("two", "Dois")])
    second = FakeAgentSession([approved_turn(), approved_turn()])
    code = wired.run(
        second,
        workflow_id="demo",
        user_prompt="x",
        resume_run_id=crashed.id,
    )

    assert code == 0
    resumed = wired.runs.load(crashed.id)
    assert {step.step_id: step.status for step in resumed.steps} == {
        "one": "done",
        "new": "done",
        "two": "done",
    }
    assert len(second.sent) == 2, "the new step and the interrupted one run; `one` does not"


def test_resume_is_the_only_way_back_into_a_run(wired, monkeypatch, tmp_path: Path):
    """There is no restart from scratch: `run_workflow` does not even take the parameter.

    A run whose steps all closed has nothing to run when reopened; whoever wants
    the whole pipeline again starts a new run.
    """
    import inspect

    assert "restart" not in inspect.signature(run_workflow).parameters

    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    first = FakeAgentSession([approved_turn(), approved_turn()])
    wired.run(
        first,
        workflow_id="demo",
        user_prompt="x",
    )
    run_id = wired.runs.only().id

    second = FakeAgentSession([approved_turn(), approved_turn()])
    code = wired.run(
        second,
        workflow_id="demo",
        user_prompt="x",
        resume_run_id=run_id,
    )

    assert code == 0
    assert second.sent == [], "everything was already done: nothing runs again"


def test_stopping_between_steps_ends_the_run_as_stopped(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    control = RunControl()
    runner = FakeAgentSession([approved_turn()], control=control)

    original = runner.run_isolated_phase

    def stop_after_first(**kwargs):
        result = original(**kwargs)
        control.stop()
        return result

    runner.run_isolated_phase = stop_after_first

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
        control=control,
    )

    assert code == RUN_STOPPED
    record = wired.runs.only()
    assert record.status == "stopped"
    assert record.step("one").status == "done", "what already closed stays closed"
    assert record.step("two").status == "pending"


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


def test_stopping_inside_a_step_leaves_it_pending_and_resume_only_redoes_it(
    wired, monkeypatch, tmp_path: Path
):
    """Stopping midway through step 2: it goes back to pending and only it is redone.

    This is the whole stop/resume contract: the interrupted step neither finished
    nor failed, and step 1, which closed, must not run again on resume.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois"), ("three", "Três")])
    control = RunControl()
    runner = FakeAgentSession([approved_turn(), {"stopReason": "cancelled"}], control=control)

    original = runner.run_isolated_phase

    def stop_during_second(**kwargs):
        if len(runner.sent) == 1:
            control.stop()
        return original(**kwargs)

    runner.run_isolated_phase = stop_during_second

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
        control=control,
    )

    assert code == RUN_STOPPED
    assert runner.prompts.asked == [], "stopping does not go through the retry menu"
    record = wired.runs.only()
    run_id = record.id
    assert record.status == "stopped"
    assert [step.status for step in record.steps] == ["done", "pending", "pending"]

    second = FakeAgentSession([approved_turn(), approved_turn()])

    code = wired.run(
        second,
        workflow_id="demo",
        user_prompt="x",
        resume_run_id=run_id,
    )

    assert code == 0
    assert len(second.sent) == 2, (
        "only the two pending steps run; the closed one does not come back"
    )
    record = wired.runs.load(run_id)
    assert [step.status for step in record.steps] == ["done", "done", "done"]


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


def test_stopping_while_the_blocked_menu_is_open_stops_the_run(wired, monkeypatch, tmp_path: Path):
    """Stopping with the menu open cancels the question, which returns `None`.

    That is a user stop: the run becomes `stopped` and the step goes back to
    pending for whoever resumes, instead of becoming `blocked`.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    runner = FakeAgentSession([blocked_turn("falta a credencial do banco", needs="user")])

    def stop_while_waiting(prompt, choices, *, title=""):
        runner.control.stop()
        return None

    runner.prompts.select_choice = stop_while_waiting

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == RUN_STOPPED
    record = wired.runs.only()
    assert record.status == "stopped"
    assert record.step("one").status == "pending"


def test_stopping_while_typing_guidance_does_not_reopen_the_menu(
    wired, monkeypatch, tmp_path: Path
):
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    runner = FakeAgentSession([RuntimeError("o processo do agente encerrou")])
    runner.prompts.choice = "guidance"

    def stop_while_typing(prompt, *, title=""):
        runner.control.stop()
        return None

    runner.prompts.ask_text = stop_while_typing

    code = wired.run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert code == RUN_STOPPED
    assert len(runner.prompts.asked) == 1, "the menu does not come back after stopping"
