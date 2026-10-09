"""A past run reopened from history: resume offer, worktree removal and pane keys."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("textual")

from pulse import vcs
from pulse.domain.run import StepRecord, StepStatus
from pulse.history.catalog import HistoryCatalog
from pulse.history.models import HistoryItem
from pulse.store import runs as run_store
from pulse.tui import strings
from pulse.tui.screens.confirm import ConfirmScreen
from pulse.tui.screens.history_detail import HistoryDetailScreen
from pulse.tui.screens.resume_choice import ResumeChoiceScreen
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.artifact_pane import ArtifactPane
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import NavSelected, PhaseSidebar
from tests.conftest import make_workflow, store_run_status, store_step
from tests.infra.test_worktree import make_repo, prepare

STEPS = [("plan", "Plan"), ("build", "Build")]

git_only = pytest.mark.skipif(not vcs.git_available(), reason="git is not on PATH")


def _stored_run(workspace: Path, *, done: tuple[str, ...], status: str) -> str:
    make_workflow("demo", steps=STEPS)
    record = run_store.create_run(
        run_id="run-1",
        workflow_id="demo",
        workspace=workspace,
        user_prompt="do it",
        steps=[
            StepRecord(step_id=step_id, position=index, label=label, agent_id="tester")
            for index, (step_id, label) in enumerate(STEPS, start=1)
        ],
    )
    for step in record.steps:
        if step.step_id in done:
            step.status = StepStatus.DONE
            store_step(record.id, step)
    store_run_status(record.id, status)
    return record.id


def _store_worktree(path: Path, *, branch: str = "", run_id: str = "run-1") -> None:
    """The run worked in `path`: the daemon reads that from the stored run, not the screen."""
    record = run_store.load_run(run_id)
    assert record is not None
    record.worktree_path = str(path)
    record.branch = branch
    run_store.save(record)


def _item(workspace: Path, run_id: str = "run-1") -> HistoryItem:
    item = HistoryCatalog(workspace).get(run_id)
    assert item is not None
    return item


def _app(detail: HistoryDetailScreen):
    from textual.app import App

    class Harness(App[None]):
        CSS = COCKPIT_CSS

        def __init__(self) -> None:
            super().__init__()
            self.opened: list[tuple[str, str, dict[str, Any]]] = []
            self.notes: list[str] = []

        def on_mount(self) -> None:
            self.push_screen(detail)

        def open_cockpit(self, workflow_id: str, prompt: str, **kwargs: Any) -> None:
            self.opened.append((workflow_id, prompt, kwargs))

        def notify(self, message: str, **_kwargs: Any) -> None:  # type: ignore[override]  # records toasts
            self.notes.append(message)

    return Harness()


def test_an_unfinished_run_offers_resume_on_open_and_again_with_r(tmp_path):
    """Backing out of the offer keeps the page; `r` brings it back; resume opens the cockpit."""
    run_id = _stored_run(tmp_path, done=("plan",), status="stopped")
    detail = HistoryDetailScreen(_item(tmp_path), workspace=tmp_path)

    async def run() -> None:
        app = _app(detail)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            offer = app.screen
            assert isinstance(offer, ResumeChoiceScreen)
            assert str(offer.query_one(".resume-summary").render()) == (
                strings.RESUME_STOPPED_AT.format(
                    summary=strings.RUN_SUMMARY.format(current="Build", done=1, total=2)
                )
            )

            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is detail
            assert app.opened == []
            assert detail.check_action("resume_workflow", ()) is True

            await pilot.press("r")
            await pilot.pause()
            assert isinstance(app.screen, ResumeChoiceScreen)
            await pilot.press("enter")
            await pilot.pause()

            assert app.opened == [("demo", "do it", {"resume_run_id": run_id})]

    asyncio.run(run())


def test_a_finished_run_has_no_resume_and_no_worktree_to_remove(tmp_path):
    """Keys for actions that do not apply stay inert instead of opening empty dialogs."""
    _stored_run(tmp_path, done=("plan", "build"), status="completed")
    detail = HistoryDetailScreen(_item(tmp_path), workspace=tmp_path)

    async def run() -> None:
        app = _app(detail)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            assert app.screen is detail
            assert detail.check_action("resume_workflow", ()) is False
            assert detail.check_action("remove_worktree", ()) is False

            detail.action_resume_workflow()
            detail.action_remove_worktree()
            await pilot.pause()

            assert app.screen is detail
            assert app.opened == []

            await pilot.press("q")
            await pilot.pause()
            assert detail not in app.screen_stack

    asyncio.run(run())


def test_a_worktree_git_cannot_remove_is_kept_with_a_notice(tmp_path):
    """Outside a repository git refuses; the directory stays and the user is told why."""
    _stored_run(tmp_path, done=("plan", "build"), status="completed")
    worktree = tmp_path / "loose-worktree"
    worktree.mkdir()
    _store_worktree(worktree, branch="pulse/demo")
    detail = HistoryDetailScreen(_item(tmp_path), workspace=tmp_path)

    async def run() -> None:
        app = _app(detail)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await pilot.press("w")
            await pilot.pause()
            confirm = app.screen
            assert isinstance(confirm, ConfirmScreen)
            text = str(confirm.query_one(".confirm-detail").render())
            assert text.splitlines()[:2] == [
                str(worktree),
                strings.WORKTREE_BRANCH.format(branch="pulse/demo"),
            ]
            assert strings.WORKTREE_DIRTY.splitlines()[0] in text, "unknown state reads as dirty"

            await pilot.press("down", "enter")
            await pilot.pause()

            assert app.notes == [strings.WORKTREE_GIT_REFUSED]
            assert worktree.exists()

    asyncio.run(run())


@git_only
def test_a_clean_worktree_is_removed_only_after_confirmation(tmp_path):
    """Declining keeps the directory; confirming removes it and keeps the branch."""
    repo = make_repo(tmp_path / "repo")
    run_id = _stored_run(repo, done=("plan", "build"), status="completed")
    record = run_store.load_run(run_id)
    assert record is not None
    exec_dir, branch = prepare(record, repo, use_worktree=True)
    detail = HistoryDetailScreen(_item(repo), workspace=repo)

    async def run() -> None:
        app = _app(detail)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            assert detail.check_action("remove_worktree", ()) is True

            await pilot.press("w")
            await pilot.pause()
            confirm = app.screen
            assert isinstance(confirm, ConfirmScreen)
            text = str(confirm.query_one(".confirm-detail").render())
            assert strings.WORKTREE_CLEAN in text
            assert strings.WORKTREE_BRANCH.format(branch=branch) in text
            await pilot.press("escape")
            await pilot.pause()
            assert exec_dir.exists()
            assert app.notes == []

            await pilot.press("w")
            await pilot.pause()
            await pilot.press("down", "enter")
            await pilot.pause()

            assert app.notes == [strings.WORKTREE_REMOVED]
            assert not exec_dir.exists()
            assert vcs.current_branch(repo) == "main"

    asyncio.run(run())


def test_the_daemon_running_the_run_keeps_its_worktree(tmp_path, monkeypatch, in_process_daemon):
    _stored_run(tmp_path, done=("plan", "build"), status="completed")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    _store_worktree(worktree)
    item = _item(tmp_path)
    release = threading.Event()

    def engine_at_work(**_kwargs: object) -> int:
        release.wait(5)
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_engine", engine_at_work)
    in_process_daemon.app.state.runs.start_run(
        workflow_id="demo", prompt="x", workspace=str(tmp_path), resume_run_id=item.run_id
    )
    detail = HistoryDetailScreen(item, workspace=tmp_path)

    async def run() -> None:
        app = _app(detail)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await pilot.press("w")
            await pilot.pause()
            assert app.screen is detail
            assert app.notes == [strings.WORKTREE_KEPT_RUN_ACTIVE]

    try:
        asyncio.run(run())
    finally:
        release.set()


@git_only
def test_a_worktree_git_refused_can_be_removed_again_once_clean(tmp_path):
    """git keeps a dirty worktree and so does the stored path; the screen must not forget it."""
    repo = make_repo(tmp_path / "repo")
    run_id = _stored_run(repo, done=("plan", "build"), status="completed")
    record = run_store.load_run(run_id)
    assert record is not None
    exec_dir, _ = prepare(record, repo, use_worktree=True)
    draft = exec_dir / "rascunho.md"
    draft.write_text("não commitado\n", encoding="utf-8")
    detail = HistoryDetailScreen(_item(repo), workspace=repo)

    async def run() -> None:
        app = _app(detail)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await pilot.press("w")
            await pilot.pause()
            await pilot.press("down", "enter")
            await pilot.pause()
            assert app.notes == [strings.WORKTREE_GIT_REFUSED]

            draft.unlink()
            await pilot.press("w")
            await pilot.pause()
            await pilot.press("down", "enter")
            await pilot.pause()

            assert app.notes == [strings.WORKTREE_GIT_REFUSED, strings.WORKTREE_REMOVED]
            assert not exec_dir.exists()

    asyncio.run(run())


def test_artifact_and_navigation_keys_browse_the_past_run(tmp_path):
    """The page reuses the cockpit keys: pane, file switching, phases and focus."""
    run_id = _stored_run(tmp_path, done=("plan", "build"), status="completed")
    (tmp_path / "one.md").write_text("# One\n", encoding="utf-8")
    (tmp_path / "two.md").write_text("# Two\n", encoding="utf-8")
    run_store.record_artifact(run_id, "one.md", step_id="plan")
    run_store.record_artifact(run_id, "two.md", step_id="plan")
    run_store.record_event(run_id, step_id="plan", kind="Assistant", title="Plan ready")
    detail = HistoryDetailScreen(_item(tmp_path), workspace=tmp_path)

    async def run() -> None:
        app = _app(detail)
        async with app.run_test(size=(160, 40)) as pilot:
            await pilot.pause()
            state = detail.state
            body = detail.query_one("#cockpit-body")
            assert body.has_class("artifacts-rail")
            assert detail.check_action("artifact_next", ()) is False

            await pilot.press("a")
            await pilot.pause()
            assert state.artifact_pane_open is True
            assert body.has_class("artifacts-open")
            assert state.selected_artifact_path == "two.md"

            await pilot.press("left_square_bracket")
            assert state.selected_artifact_path == "one.md"
            await pilot.press("right_square_bracket")
            assert state.selected_artifact_path == "two.md"

            while state.focus_target != "artifact":
                await pilot.press("tab")
            assert detail.query_one(ArtifactPane).has_focus
            assert detail.check_action("artifact_left", ()) is True
            await pilot.press("left")
            assert state.selected_artifact_path == "one.md"
            await pilot.press("right")
            assert state.selected_artifact_path == "two.md"
            await pilot.press("down", "up")
            assert state.selected_phase_index == 0, "arrows scroll the file in artifact focus"

            tabs = list(detail.query_one("#artifact-tabs").children)
            await pilot.click(tabs[0])
            await pilot.pause()
            assert state.selected_artifact_path == "one.md"

            await pilot.click("#artifact-close")
            await pilot.pause()
            assert state.artifact_pane_open is False
            await pilot.click("#artifact-open")
            await pilot.pause()
            assert state.artifact_pane_open is True

            await pilot.press("escape")
            await pilot.pause()
            assert state.artifact_pane_open is False
            assert app.screen is detail

            await pilot.press("j")
            assert state.focus_target == "phases"
            assert state.selected_phase_index == 1
            await pilot.press("k")
            assert state.selected_phase_index == 0
            detail.query_one(PhaseSidebar).post_message(NavSelected("phase", 1))
            await pilot.pause()
            assert state.selected_phase_index == 1

            await pilot.press("tab")
            await pilot.pause()
            assert detail.query_one(LogStream).has_focus

            await pilot.press("escape")
            await pilot.pause()
            assert detail not in app.screen_stack

    asyncio.run(run())
