"""The cockpit screen mounted in an app, driven by keys, against a fake engine session.

The fake stands in for `EngineRunSession` at the client boundary: it feeds the
screen's real sink and prompt bridge, as the daemon stream would, and records
what the screen asked of the run (run, attach, stop, detach).
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pulse.client.run_session import DETACHED
from pulse.domain.control import RUN_BLOCKED, RUN_STOPPED
from pulse.domain.run import StepRecord, StepStatus
from pulse.store import runs as run_store
from pulse.tui import strings
from pulse.tui.adapters.prompt_bridge import PromptAbandoned
from pulse.tui.screens.cockpit import CockpitScreen
from pulse.tui.screens.resume_choice import ResumeChoiceScreen
from pulse.tui.state import LogKind
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.artifact_pane import ArtifactPane
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import NavSelected, PhaseSidebar
from pulse.tui.widgets.prompt_dock import PromptDock
from tests.conftest import make_workflow, store_step
from tests.tui.conftest import wait_until

STEPS = [("plan", "Plan"), ("build", "Build")]
WAIT = 5.0

Script = Callable[["_FakeSession"], int]


class _FakeSession:
    """Engine session double: runs `script` on the worker thread and records calls."""

    script: Script = staticmethod(lambda _session: 0)
    instances: list[_FakeSession] = []

    def __init__(self, *, stream: Any, prompt_handler: Any, **_kwargs: Any) -> None:
        self.stream = stream
        self.prompt_handler = prompt_handler
        self.calls: list[tuple[str, Any]] = []
        self.started = threading.Event()
        self.released = threading.Event()
        type(self).instances.append(self)

    def run(self, **kwargs: Any) -> int:
        self.calls.append(("run", kwargs))
        return type(self).script(self)

    def attach(self, run_id: str) -> int:
        self.calls.append(("attach", run_id))
        return type(self).script(self)

    def stop(self) -> bool:
        self.calls.append(("stop", None))
        self.released.set()
        return True

    def detach(self) -> None:
        self.calls.append(("detach", None))
        self.released.set()


def _use_session(monkeypatch, script: Script) -> type[_FakeSession]:
    import pulse.client.run_session as run_session

    session_class = type("_ScriptedSession", (_FakeSession,), {"instances": []})
    session_class.script = staticmethod(script)  # type: ignore[attr-defined]  # per-test script
    monkeypatch.setattr(run_session, "EngineRunSession", session_class)
    return session_class


def _app(cockpit: CockpitScreen):
    from textual.app import App

    class Harness(App[None]):
        CSS = COCKPIT_CSS

        def __init__(self) -> None:
            super().__init__()
            self.opened: list[tuple[str, str, dict[str, Any]]] = []

        def on_mount(self) -> None:
            self.push_screen(cockpit)

        def open_cockpit(self, workflow_id: str, prompt: str, **kwargs: Any) -> None:
            self.opened.append((workflow_id, prompt, kwargs))

    return Harness()


async def _wait_thread(event: threading.Event) -> None:
    assert await asyncio.to_thread(event.wait, WAIT)


def _stored_run(workspace: Path, run_id: str, *, settled: bool = False) -> str:
    make_workflow("demo", steps=STEPS)
    record = run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt="do it",
        steps=[
            StepRecord(step_id=step_id, position=index, label=label, agent_id="tester")
            for index, (step_id, label) in enumerate(STEPS, start=1)
        ],
    )
    first = record.steps[0]
    first.status = StepStatus.DONE
    store_step(record.id, first)
    if settled:
        second = record.steps[1]
        second.status = StepStatus.DONE
        store_step(record.id, second)
    return record.id


def _titles(screen: CockpitScreen, kind: LogKind) -> list[str]:
    return [entry.title for entry in screen.state.entries if entry.kind == kind]


def test_stop_cuts_the_run_and_resume_reopens_it_from_where_it_stopped(monkeypatch, tmp_path):
    """`s` asks the daemon to stop; the stopped run is offered for resume right away."""
    run_id = _stored_run(tmp_path, "run-stop")

    def script(session: _FakeSession) -> int:
        session.stream.begin_phase("Plan")
        session.started.set()
        session.released.wait(WAIT)
        return RUN_STOPPED

    sessions = _use_session(monkeypatch, script)
    cockpit = CockpitScreen("demo", "do it", workspace=tmp_path)

    async def run() -> None:
        app = _app(cockpit)
        async with app.run_test(size=(140, 40)) as pilot:
            await wait_until(pilot, lambda: bool(sessions.instances))
            session = sessions.instances[0]
            await _wait_thread(session.started)
            assert cockpit.check_action("stop_run", ()) is True

            await pilot.press("s")
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert [name for name, _ in session.calls] == ["run", "stop"]
            assert session.calls[0][1] == {
                "workflow_id": "demo",
                "user_prompt": "do it",
                "workspace": str(tmp_path),
                "resume_run_id": None,
                "branch": "",
            }
            infos = _titles(cockpit, LogKind.INFO)
            assert strings.RUN_STOPPING in infos
            assert strings.RUN_STOPPED in infos
            assert cockpit.state.exit_code == RUN_STOPPED
            choice = app.screen
            assert isinstance(choice, ResumeChoiceScreen)
            summary = str(choice.query_one(".resume-summary").render())
            assert summary == strings.RESUME_STOPPED_AT.format(
                summary=strings.RUN_SUMMARY.format(current="Build", done=1, total=2)
            )

            await pilot.press("enter")
            await pilot.pause()

            assert app.opened == [("demo", "do it", {"resume_run_id": run_id})]
            assert cockpit not in app.screen_stack

    asyncio.run(run())


def test_a_failed_run_explains_the_exit_code_and_back_keeps_the_cockpit(monkeypatch, tmp_path):
    """A non-zero exit without an error entry still tells the user why the run ended."""
    _stored_run(tmp_path, "run-fail")
    _use_session(monkeypatch, lambda _session: 2)
    cockpit = CockpitScreen("demo", "do it", workspace=tmp_path)

    async def run() -> None:
        app = _app(cockpit)
        async with app.run_test(size=(140, 40)) as pilot:
            await wait_until(pilot, lambda: isinstance(app.screen, ResumeChoiceScreen))

            assert [
                (entry.title, entry.detail)
                for entry in cockpit.state.entries
                if entry.kind == LogKind.ERROR
            ] == [(strings.WORKFLOW_FAILED, strings.WORKFLOW_EXIT_CODE.format(code=2))]
            assert strings.RUN_RESUMABLE_FROM_FAILURE in _titles(cockpit, LogKind.INFO)

            await pilot.press("escape")
            await pilot.pause()

            assert app.screen is cockpit
            assert app.opened == []

    asyncio.run(run())


def test_a_completed_run_reports_done_and_offers_nothing(monkeypatch, tmp_path):
    """Leaving after the run ended closes the bridge: nothing remains to wait for."""
    sessions = _use_session(monkeypatch, lambda _session: 0)
    cockpit = CockpitScreen("demo", "do it", workspace=tmp_path)
    make_workflow("demo", steps=STEPS)

    async def run() -> None:
        app = _app(cockpit)
        async with app.run_test(size=(140, 40)) as pilot:
            await wait_until(pilot, lambda: strings.WORKFLOW_DONE in _titles(cockpit, LogKind.INFO))
            assert cockpit.state.exit_code == 0
            assert app.screen is cockpit

            await pilot.press("q")
            await pilot.pause()

            assert cockpit not in app.screen_stack
            assert [name for name, _ in sessions.instances[0].calls] == ["run"]
            assert cockpit.bridge.select("late?", [("a", "A) a")]) is None, "bridge closed"

    asyncio.run(run())


def test_a_blocked_resumed_run_without_pending_steps_offers_no_resume(monkeypatch, tmp_path):
    """The known run decides: when all its steps settled there is nothing to resume."""
    run_id = _stored_run(tmp_path, "run-blocked", settled=True)
    _use_session(monkeypatch, lambda _session: RUN_BLOCKED)
    cockpit = CockpitScreen("demo", "do it", workspace=tmp_path, resume_run_id=run_id)

    async def run() -> None:
        app = _app(cockpit)
        async with app.run_test(size=(140, 40)) as pilot:
            await wait_until(pilot, lambda: strings.RUN_BLOCKED in _titles(cockpit, LogKind.INFO))
            await pilot.pause()
            assert app.screen is cockpit
            assert cockpit.state.exit_code == RUN_BLOCKED

    asyncio.run(run())


def test_attach_follows_the_worktree_and_leaving_detaches_without_finishing(monkeypatch, tmp_path):
    """Reattaching replays the run; quitting the screen must leave the run alive."""
    run_id = _stored_run(tmp_path, "run-attach")
    run_store.record_event(run_id, step_id="plan", kind="Assistant", title="Plan ready")
    worktree = tmp_path / "wt"
    worktree.mkdir()

    def script(session: _FakeSession) -> int:
        session.stream.begin_phase("Build")
        session.stream.set_context(cwd=str(worktree), branch="feat/x")
        session.stream.replay_finished()
        session.started.set()
        session.released.wait(WAIT)
        return DETACHED

    sessions = _use_session(monkeypatch, script)
    cockpit = CockpitScreen("demo", "do it", workspace=tmp_path, attach_run_id=run_id)

    async def run() -> None:
        app = _app(cockpit)
        async with app.run_test(size=(140, 40)) as pilot:
            await wait_until(pilot, lambda: bool(sessions.instances))
            session = sessions.instances[0]
            await _wait_thread(session.started)
            await wait_until(pilot, lambda: cockpit.query_one(ArtifactPane)._cwd == str(worktree))

            assert session.calls[0] == ("attach", run_id)
            assert cockpit.state.branch_label == "feat/x"
            restored = [entry.title for entry in cockpit.state.entries if entry.phase_id == "plan"]
            assert restored == ["Plan ready"], "the settled step's log comes from the database"

            await pilot.press("b")
            await app.workers.wait_for_complete()
            await pilot.pause()

            names = {name for name, _ in session.calls}
            assert names == {"attach", "detach"}, "leaving never stops the run"
            assert cockpit not in app.screen_stack
            assert cockpit.state.exit_code is None, "detaching is not finishing"

    asyncio.run(run())


def test_an_abandoned_prompt_ends_the_worker_quietly(monkeypatch, tmp_path):
    """The user left with a question open; the run still waits in the daemon, no error."""

    def script(_session: _FakeSession) -> int:
        raise PromptAbandoned()

    _use_session(monkeypatch, script)
    make_workflow("demo", steps=STEPS)
    cockpit = CockpitScreen("demo", "do it", workspace=tmp_path)

    async def run() -> None:
        app = _app(cockpit)
        async with app.run_test(size=(140, 40)) as pilot:
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert cockpit.state.exit_code is None
            assert _titles(cockpit, LogKind.ERROR) == []

    asyncio.run(run())


def test_artifact_keys_open_browse_and_close_the_pane(monkeypatch, tmp_path):
    """`a`, `]`, `[`, arrows and Esc drive the pane; Esc closes it before leaving."""
    (tmp_path / "one.md").write_text("# One\n", encoding="utf-8")
    (tmp_path / "two.md").write_text("# Two\n", encoding="utf-8")
    make_workflow("demo", steps=STEPS)

    def script(session: _FakeSession) -> int:
        session.stream.begin_phase("Plan")
        session.started.set()
        session.released.wait(WAIT)
        return DETACHED

    sessions = _use_session(monkeypatch, script)
    cockpit = CockpitScreen("demo", "do it", workspace=tmp_path)

    async def run() -> None:
        app = _app(cockpit)
        async with app.run_test(size=(160, 40)) as pilot:
            await wait_until(pilot, lambda: bool(sessions.instances))
            await _wait_thread(sessions.instances[0].started)
            state = cockpit.state
            assert cockpit.check_action("toggle_artifact_pane", ()) is False
            state.upsert_artifact("one.md", ready=True, has_content=True)
            state.upsert_artifact("two.md", ready=True, has_content=True)
            assert cockpit.check_action("artifact_next", ()) is False

            await pilot.press("a")
            await pilot.pause()
            body = cockpit.query_one("#cockpit-body")
            assert state.artifact_pane_open is True
            assert body.has_class("artifacts-open")
            assert state.selected_artifact_path == "two.md"

            await pilot.press("left_square_bracket")
            assert state.selected_artifact_path == "one.md"
            await pilot.press("right_square_bracket")
            assert state.selected_artifact_path == "two.md"

            while state.focus_target != "artifact":
                await pilot.press("tab")
            assert cockpit.query_one(ArtifactPane).has_focus
            await pilot.press("left")
            assert state.selected_artifact_path == "one.md"
            await pilot.press("right")
            assert state.selected_artifact_path == "two.md"
            await pilot.press("down", "up")
            assert state.selected_phase_index == 0, "arrows scroll the file in artifact focus"

            tabs = list(cockpit.query_one("#artifact-tabs").children)
            await pilot.click(tabs[0])
            await pilot.pause()
            assert state.selected_artifact_path == "one.md"
            assert state.focus_target == "artifact"

            await pilot.click("#artifact-close")
            await pilot.pause()
            assert state.artifact_pane_open is False
            assert body.has_class("artifacts-rail")

            await pilot.click("#artifact-open")
            await pilot.pause()
            assert state.artifact_pane_open is True

            await pilot.press("escape")
            await pilot.pause()
            assert state.artifact_pane_open is False
            assert app.screen is cockpit

            await pilot.press("escape")
            await pilot.pause()
            assert cockpit not in app.screen_stack

    asyncio.run(run())


def test_navigation_keys_move_between_phases_and_toggle_focus(monkeypatch, tmp_path):
    """Up/down select phases from any focus; Tab cycles where the keys go."""
    make_workflow("demo", steps=STEPS)
    _use_session(monkeypatch, lambda _session: DETACHED)
    cockpit = CockpitScreen("demo", "do it", workspace=tmp_path)

    async def run() -> None:
        app = _app(cockpit)
        async with app.run_test(size=(140, 40)) as pilot:
            await app.workers.wait_for_complete()
            await pilot.pause()
            state = cockpit.state
            assert state.selected_phase_index == 0

            await pilot.press("j")
            assert state.focus_target == "phases"
            assert state.selected_phase_index == 1
            await pilot.press("k")
            assert state.selected_phase_index == 0

            cockpit.query_one(PhaseSidebar).post_message(NavSelected("phase", 1))
            await pilot.pause()
            assert state.selected_phase_index == 1

            await pilot.press("tab")
            await pilot.pause()
            assert state.focus_target == "stream"
            assert cockpit.query_one(LogStream).has_focus
            await pilot.press("tab")
            await pilot.pause()
            assert state.focus_target == "phases"
            assert cockpit.query_one(PhaseSidebar).has_focus

    asyncio.run(run())


def test_an_open_question_blocks_run_keys_and_points_at_the_cited_artifact(monkeypatch, tmp_path):
    """While the dock asks, stop and pane keys are off; the answer reaches the run."""
    (tmp_path / "spec.md").write_text("# Spec\n", encoding="utf-8")
    make_workflow("demo", steps=STEPS)
    answers: list[object | None] = []

    def script(session: _FakeSession) -> int:
        session.stream.begin_phase("Plan")
        cockpit.state.upsert_artifact("spec.md", ready=True, has_content=True)
        cockpit.state.upsert_artifact("other.md", ready=True, has_content=False)
        answers.append(cockpit.bridge.select("Approve spec.md?", [("yes", "A) Approve")]))
        return 0

    _use_session(monkeypatch, script)
    cockpit = CockpitScreen("demo", "do it", workspace=tmp_path)

    async def run() -> None:
        app = _app(cockpit)
        async with app.run_test(size=(140, 40)) as pilot:
            try:
                await _answer_the_open_question(pilot, cockpit, answers)
            finally:
                # A failed assertion must fail the test, not leave the run's
                # thread blocked on an unanswered question while the app exits.
                cockpit.bridge.close()

    asyncio.run(run())


async def _answer_the_open_question(pilot, cockpit: CockpitScreen, answers: list) -> None:
    from textual.widgets import OptionList

    app = pilot.app
    await wait_until(pilot, lambda: bool(cockpit.query(PromptDock)))
    # A key pressed before the dock holds focus goes to the cockpit and is lost.
    dock = cockpit.query_one(PromptDock)
    await wait_until(pilot, lambda: any(options.has_focus for options in dock.query(OptionList)))
    state = cockpit.state

    assert state.selected_artifact_path == "spec.md"
    assert state.follow_artifact is False
    assert state.artifact_pane_open is False, "the question selects, the user opens"
    for action in ("stop_run", "toggle_artifact_pane", "artifact_next"):
        assert cockpit.check_action(action, ()) is False, action
    state.focus_target = "stream"
    assert cockpit.check_action("nav_down", ()) is False
    state.focus_target = "phases"
    assert cockpit.check_action("nav_down", ()) is True

    # Moving focus_target may have taken focus off the dock; hand it back first.
    dock.focus_inner()
    await wait_until(pilot, lambda: any(options.has_focus for options in dock.query(OptionList)))
    await pilot.press("a")
    await app.workers.wait_for_complete()
    await wait_until(pilot, lambda: strings.WORKFLOW_DONE in _titles(cockpit, LogKind.INFO))

    assert answers == ["yes"]
    assert list(cockpit.query(PromptDock)) == []
