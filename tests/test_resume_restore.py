"""Resuming reopens the run with its past, not with a blank screen."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tests.conftest import make_workflow, store_step

from pulse.store import runs as run_store
from pulse.store.runs import DONE, RUNNING, StepRecord
from pulse.tui.hydrate import restore_run
from pulse.tui.state import CockpitState, PhaseStatus


def _run_with_history(workspace: Path) -> str:
    """A run with the first step closed and its log, tool and duration recorded."""
    make_workflow("demo", steps=[("plan", "Planejar"), ("build", "Construir")])
    record = run_store.create_run(
        run_id="run-1",
        workflow_id="demo",
        workspace=workspace,
        user_prompt="fazer algo",
        steps=[
            StepRecord(step_id="plan", position=1, label="Planejar", agent_id="tester"),
            StepRecord(step_id="build", position=2, label="Construir", agent_id="tester"),
        ],
    )
    plan = record.steps[0]
    plan.status = DONE
    plan.started_at = datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    plan.ended_at = datetime(2026, 9, 29, 10, 2, 30, tzinfo=UTC)
    store_step(record.id, plan)

    run_store.record_event(
        record.id, step_id="plan", kind="Assistant", title="Plano pronto", detail="Plano pronto"
    )
    run_store.record_event(
        record.id, step_id="plan", kind="Tool", title="read README.md", detail="1..80"
    )
    return record.id


def _state() -> CockpitState:
    make_workflow("demo", steps=[("plan", "Planejar"), ("build", "Construir")])
    state = CockpitState()
    state.configure_workflow("demo")
    return state


def test_resume_brings_back_log_tool_and_duration_of_previous_steps(tmp_path: Path):
    run_id = _run_with_history(tmp_path)
    state = _state()

    restore_run(state, run_id, tmp_path)

    titles = [entry.title for entry in state.entries]
    assert "Plano pronto" in titles
    assert "read README.md" in titles, "the tool comes back too, not only the agent speech"

    plan = state.phases[0]
    assert plan.status == PhaseStatus.DONE
    assert plan.elapsed_label() != "", "the previous step shows how long it took"
    assert state.phases[1].status == PhaseStatus.PENDING


def test_the_live_run_appends_instead_of_rewriting_what_came_back(tmp_path: Path):
    """A repeated id would make the stream rewrite an old line."""
    run_id = _run_with_history(tmp_path)
    state = _state()

    restore_run(state, run_id, tmp_path)
    restored = len(state.entries)
    state.add_info("Retomando Construir")

    ids = [entry.entry_id for entry in state.entries]
    assert len(ids) == restored + 1
    assert len(set(ids)) == len(ids)


def test_a_step_interrupted_by_a_crash_comes_back_as_pending(tmp_path: Path):
    """`running` in the database is an interrupted step: nothing is in progress on reopen."""
    run_id = _run_with_history(tmp_path)
    record = run_store.load_run(run_id)
    build = record.step("build")
    build.status = RUNNING
    build.started_at = datetime(2026, 9, 29, 10, 2, 30, tzinfo=UTC)
    store_step(run_id, build)

    state = _state()
    restore_run(state, run_id, tmp_path)

    assert state.phases[1].status == PhaseStatus.PENDING
    assert state.phases[1].elapsed_label() == ""


def test_a_missing_run_leaves_the_screen_as_it_was(tmp_path: Path):
    """History is context, not a requirement: the new run can still run."""
    state = _state()

    restore_run(state, "nao-existe", tmp_path)

    assert state.entries == []
    assert [phase.status for phase in state.phases] == [PhaseStatus.PENDING] * 2


def test_the_cockpit_reopens_with_the_past_before_the_run_restarts(tmp_path: Path, monkeypatch):
    """The screen, not just the state: the cockpit `on_mount` calls the restore."""
    import asyncio

    import pytest

    pytest.importorskip("textual")

    from pulse.tui.screens.cockpit import CockpitScreen
    from pulse.tui.theme import COCKPIT_CSS

    run_id = _run_with_history(tmp_path)

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            screen = CockpitScreen(
                "demo", "fazer algo", workspace=tmp_path, resume_run_id=run_id
            )
            monkeypatch.setattr(screen, "_run_workflow", lambda: None)
            app.push_screen(screen)
            await pilot.pause()

            content = str(screen.query_one("#stream-content").render())
            assert "Plano pronto" in content
            assert screen.state.phases[0].status == PhaseStatus.DONE
            assert screen.state.phases[0].elapsed_label() != ""

    asyncio.run(run())


def test_the_choice_offers_back_instead_of_view_only():
    """"Só visualizar" promised a screen; "Voltar" says what the key does."""
    import asyncio

    import pytest

    pytest.importorskip("textual")

    from pulse.tui.screens.resume_choice import BACK, RESUME, ResumeChoiceScreen
    from pulse.tui.theme import COCKPIT_CSS

    async def run() -> None:
        from textual.app import App
        from textual.widgets import OptionList

        class Harness(App[None]):
            CSS = COCKPIT_CSS

        chosen: list[str | None] = []
        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = ResumeChoiceScreen(slug="demo", summary="plan · steps 1/2")
            app.push_screen(screen, callback=chosen.append)
            await pilot.pause()

            options = screen.query_one("#resume-options", OptionList)
            ids = [
                str(options.get_option_at_index(index).id)
                for index in range(options.option_count)
            ]
            assert ids == [RESUME, BACK], "restart from scratch is gone; only resume remains"

            screen.action_back()
            await pilot.pause()
            assert chosen == [None], "back picks nothing: the caller stays where it is"

    asyncio.run(run())
    from pulse.tui.screens.resume_choice import ResumeChoiceScreen as Screen

    assert not hasattr(Screen, "action_just_view"), "'Só visualizar' is gone for good"
