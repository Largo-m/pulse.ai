"""The artifact pane as the user sees it: placeholders, tabs, clicks and scrolling."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from pulse.tui import strings
from pulse.tui.state import CockpitState
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.artifact_pane import ArtifactPane, ArtifactTabSelected
from tests.conftest import configure_from_db, make_workflow

STEPS = [("one", "Um"), ("two", "Dois")]


def _state() -> CockpitState:
    make_workflow("demo", steps=STEPS)
    state = CockpitState()
    configure_from_db(state, "demo")
    return state


def _harness(state: CockpitState, cwd: Path, selected: list[str] | None = None):
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal

    class Harness(App[None]):
        CSS = COCKPIT_CSS

        def compose(self) -> ComposeResult:
            with Horizontal(id="cockpit-body"):
                yield ArtifactPane(state, cwd=str(cwd), id="artifact-pane")

        def on_artifact_tab_selected(self, event: ArtifactTabSelected) -> None:
            if selected is not None:
                selected.append(event.path)

    return Harness()


def _markdown(app) -> str:
    return app.query_one("#artifact-markdown").source


def _meta(app) -> str:
    return str(app.query_one("#artifact-meta").render())


def _tab_names(app) -> list[str]:
    return [child.name for child in app.query_one("#artifact-tabs").children]


def test_pane_shows_writing_then_empty_then_content_as_the_file_evolves(tmp_path):
    """The agent writes a file over time; each stage has its own placeholder, never a blank."""
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("docs/plan.md", ready=False)
    state.open_artifact_pane()
    target = tmp_path / "docs" / "plan.md"

    async def run() -> None:
        app = _harness(state, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            pane = app.query_one(ArtifactPane)
            pane.sync_from_state(state, force=True)
            await pilot.pause()
            assert _markdown(app) == strings.ARTIFACT_WRITING_MARKDOWN.format(name="plan.md")
            assert _meta(app) == f"plan.md · {strings.ARTIFACT_WRITING}"
            tab = app.query_one("#artifact-tabs").children[0]
            assert str(tab.render()).startswith("… plan.md")

            target.parent.mkdir(parents=True)
            target.write_text("", encoding="utf-8")
            os.utime(target, (1_000, 1_000))
            state.upsert_artifact("docs/plan.md", ready=True, has_content=True)
            pane.sync_from_state(state)
            await pilot.pause()
            assert _markdown(app) == strings.ARTIFACT_EMPTY_MARKDOWN.format(name="plan.md")
            assert _meta(app) == f"plan.md · {strings.ARTIFACT_LIVE}"

            target.write_text("# Plan\n\nship it\n", encoding="utf-8")
            os.utime(target, (2_000, 2_000))
            pane.sync_from_state(state)
            await pilot.pause()
            assert _markdown(app) == "# Plan\n\nship it\n"

            state.select_artifact("docs/plan.md")
            pane.sync_from_state(state)
            await pilot.pause()
            assert _meta(app) == f"plan.md · {strings.ARTIFACT_PAUSED}", "a manual pick pauses"

    asyncio.run(run())


def test_open_pane_on_a_phase_without_artifacts_says_so(tmp_path):
    """Opening the pane where nothing was written shows the empty message, not stale text."""
    state = _state()
    state.begin_phase("Um")
    state.open_artifact_pane()

    async def run() -> None:
        app = _harness(state, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one(ArtifactPane).sync_from_state(state, force=True)
            await pilot.pause()
            assert _markdown(app) == strings.ARTIFACT_NONE_IN_PHASE_MARKDOWN
            assert _meta(app) == strings.ARTIFACT_NONE_IN_PHASE
            assert str(app.query_one("#artifact-header").render()) == (
                strings.ARTIFACT_HEADER.format(count=0)
            )
            assert _tab_names(app) == []

    asyncio.run(run())


def test_tabs_follow_the_selected_phase_and_drop_the_other_phase_files(tmp_path):
    """Each phase shows only its own files; tabs of the previous phase are removed."""
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n", encoding="utf-8")
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("a.md", ready=True, has_content=True)
    state.begin_phase("Dois")
    state.upsert_artifact("b.md", ready=True, has_content=True)
    state.select_phase(0)
    state.open_artifact_pane()

    async def run() -> None:
        app = _harness(state, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            pane = app.query_one(ArtifactPane)
            pane.sync_from_state(state, force=True)
            await pilot.pause()
            assert _tab_names(app) == ["a.md"]
            assert app.query_one("#artifact-tabs").children[0].has_class("-active")
            assert _markdown(app) == "# A\n"

            state.select_phase(1)
            pane.sync_from_state(state)
            await pilot.pause()
            assert _tab_names(app) == ["b.md"]
            assert _markdown(app) == "# B\n"

    asyncio.run(run())


def test_repointing_the_pane_to_the_worktree_reloads_the_file_from_there(tmp_path):
    """The worktree is known only after `run.context`; the same path must be read again."""
    project = tmp_path / "project"
    worktree = tmp_path / "worktree"
    project.mkdir()
    worktree.mkdir()
    (worktree / "spec.md").write_text("# From worktree\n", encoding="utf-8")
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("spec.md", ready=True, has_content=True)
    state.open_artifact_pane()

    async def run() -> None:
        app = _harness(state, project)
        async with app.run_test(size=(120, 40)) as pilot:
            pane = app.query_one(ArtifactPane)
            pane.sync_from_state(state, force=True)
            await pilot.pause()
            assert _markdown(app) == strings.ARTIFACT_WRITING_MARKDOWN.format(name="spec.md")

            pane.set_cwd(str(project))
            pane.set_cwd(str(worktree))
            pane.sync_from_state(state)
            await pilot.pause()
            assert _markdown(app) == "# From worktree\n"

    asyncio.run(run())


def test_clicking_a_tab_asks_to_select_that_file(tmp_path):
    """The pane does not change the selection itself; it tells its screen which tab was hit."""
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n", encoding="utf-8")
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("a.md", ready=True, has_content=True)
    state.upsert_artifact("b.md", ready=True, has_content=True)
    state.open_artifact_pane()
    selected: list[str] = []

    async def run() -> None:
        app = _harness(state, tmp_path, selected)
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one(ArtifactPane).sync_from_state(state, force=True)
            await pilot.pause()
            tabs = list(app.query_one("#artifact-tabs").children)
            assert [tab.name for tab in tabs] == ["a.md", "b.md"]

            await pilot.click(tabs[0])
            await pilot.pause()
            await pilot.click("#artifact-meta")
            await pilot.pause()

            assert selected == ["a.md"], "a click outside the tabs selects nothing"
            assert state.selected_artifact_path == "b.md"

    asyncio.run(run())


def test_scroll_moves_the_artifact_body_both_ways(tmp_path):
    """Arrow keys in artifact focus scroll the document instead of changing the phase."""
    lines = "\n\n".join(f"line {index}" for index in range(200))
    (tmp_path / "long.md").write_text(lines, encoding="utf-8")
    state = _state()
    state.begin_phase("Um")
    state.upsert_artifact("long.md", ready=True, has_content=True)
    state.open_artifact_pane()

    async def run() -> None:
        app = _harness(state, tmp_path)
        async with app.run_test(size=(120, 30)) as pilot:
            pane = app.query_one(ArtifactPane)
            pane.sync_from_state(state, force=True)
            await pilot.pause()
            body = app.query_one("#artifact-body")
            assert body.scroll_y == 0

            pane.scroll_by(1)
            pane.scroll_by(1)
            await pilot.pause()
            lowered = body.scroll_y
            assert lowered > 0

            pane.scroll_by(-1)
            await pilot.pause()
            assert 0 <= body.scroll_y < lowered

    asyncio.run(run())
