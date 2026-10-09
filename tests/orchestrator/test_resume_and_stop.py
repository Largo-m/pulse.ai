"""Stopping a run and resuming it: only unfinished steps run again."""

from __future__ import annotations

from pathlib import Path

from pulse.domain import run as run_model
from pulse.domain.control import RUN_STOPPED, RunControl
from pulse.domain.run import RunStatus, StepStatus
from pulse.orchestrator.engine import run_workflow
from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import approved_turn, blocked_turn


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
