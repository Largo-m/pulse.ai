from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from pulse.tui.state import CockpitState
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.artifact_pane import ArtifactPane, ArtifactPaneClosed, ArtifactPaneOpened


def test_artifact_pane_renders_markdown_and_tabs(tmp_path):
    specs = tmp_path / ".pulse" / "specs" / "project"
    specs.mkdir(parents=True)
    (specs / "PROJECT.md").write_text("# Visão\n\nProduto novo.\n", encoding="utf-8")
    (specs / "ROADMAP.md").write_text("# Roadmap\n\n- v1\n", encoding="utf-8")

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal

        holder: dict = {}

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                state = CockpitState()
                state.configure_workflow("setup-project")
                holder["state"] = state
                with Horizontal(id="cockpit-body"):
                    yield ArtifactPane(state, cwd=str(tmp_path), id="artifact-pane")

            def on_mount(self) -> None:
                state = holder["state"]
                state.begin_phase("Fase 2 — Gerando specs")
                state.upsert_artifact(".pulse/specs/project/PROJECT.md", ready=True, has_content=True)
                state.upsert_artifact(".pulse/specs/project/ROADMAP.md", ready=True, has_content=True)
                state.select_artifact(".pulse/specs/project/PROJECT.md")
                state.open_artifact_pane()  # a aba não abre sozinha
                pane = self.query_one(ArtifactPane)
                pane.sync_from_state(state, force=True)

        app = Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            state = holder["state"]
            pane = app.query_one(ArtifactPane)
            assert pane.display is True
            header = str(app.query_one("#artifact-header").render())
            assert "ARTEFATOS" in header
            assert "2" in header
            tabs = app.query_one("#artifact-tabs")
            labels = [str(child.render()) for child in tabs.children]
            assert any("PROJECT.md" in label for label in labels)
            assert any("ROADMAP.md" in label for label in labels)
            md = app.query_one("#artifact-markdown")
            source = getattr(md, "_markdown", "") or ""
            assert "Visão" in source
            assert "Produto" in source
            state.select_artifact(".pulse/specs/project/ROADMAP.md")
            pane.sync_from_state(state, force=True)
            await pilot.pause()
            source = getattr(md, "_markdown", "") or ""
            assert "Roadmap" in source
            assert "v1" in source

    asyncio.run(run())


def test_artifact_pane_appends_tab_without_duplicate_ids(tmp_path):
    specs = tmp_path / ".pulse" / "specs" / "project"
    specs.mkdir(parents=True)
    (specs / "PROJECT.md").write_text("# Visão\n", encoding="utf-8")
    (specs / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal

        holder: dict = {}

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                state = CockpitState()
                state.configure_workflow("setup-project")
                holder["state"] = state
                with Horizontal(id="cockpit-body"):
                    yield ArtifactPane(state, cwd=str(tmp_path), id="artifact-pane")

            def on_mount(self) -> None:
                state = holder["state"]
                state.begin_phase("Fase 2 — Gerando specs")
                state.upsert_artifact(".pulse/specs/project/PROJECT.md", ready=True, has_content=True)
                state.open_artifact_pane()  # a aba não abre sozinha
                self.query_one(ArtifactPane).sync_from_state(state, force=True)

        app = Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            state = holder["state"]
            pane = app.query_one(ArtifactPane)
            tabs = app.query_one("#artifact-tabs")
            assert [child.name for child in tabs.children] == [
                ".pulse/specs/project/PROJECT.md"
            ]
            state.upsert_artifact(".pulse/specs/project/ROADMAP.md", ready=True, has_content=True)
            pane.sync_from_state(state, force=True)
            await pilot.pause()
            names = [child.name for child in tabs.children]
            assert names == [
                ".pulse/specs/project/PROJECT.md",
                ".pulse/specs/project/ROADMAP.md",
            ]

    asyncio.run(run())


def test_artifact_pane_close_control_hides_pane(tmp_path):
    specs = tmp_path / ".pulse" / "specs" / "project"
    specs.mkdir(parents=True)
    (specs / "PROJECT.md").write_text("# Visão\n", encoding="utf-8")

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal

        holder: dict = {}

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                state = CockpitState()
                state.configure_workflow("setup-project")
                holder["state"] = state
                with Horizontal(id="cockpit-body"):
                    yield ArtifactPane(state, cwd=str(tmp_path), id="artifact-pane")

            def on_mount(self) -> None:
                state = holder["state"]
                state.begin_phase("Fase 2 — Gerando specs")
                state.upsert_artifact(".pulse/specs/project/PROJECT.md", ready=True, has_content=True)
                state.open_artifact_pane()  # a aba não abre sozinha
                self.query_one(ArtifactPane).sync_from_state(state, force=True)

            def on_artifact_pane_closed(self, event: ArtifactPaneClosed) -> None:
                holder["closed"] = True
                state = holder["state"]
                state.close_artifact_pane()
                self.query_one(ArtifactPane).sync_from_state(state, force=True)

            def on_artifact_pane_opened(self, event: ArtifactPaneOpened) -> None:
                holder["opened"] = True
                state = holder["state"]
                state.open_artifact_pane()
                self.query_one(ArtifactPane).sync_from_state(state, force=True)

        app = Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            pane = app.query_one(ArtifactPane)
            assert pane.display is True
            assert pane.has_class("-collapsed") is False
            assert app.query_one("#artifact-close").visible is True
            await pilot.click("#artifact-close")
            await pilot.pause()
            assert holder.get("closed") is True
            assert holder["state"].artifact_pane_open is False
            assert pane.display is True
            assert pane.has_class("-collapsed") is True
            opener = app.query_one("#artifact-open")
            assert opener.display is True
            await pilot.click("#artifact-open")
            await pilot.pause()
            assert holder.get("opened") is True
            assert holder["state"].artifact_pane_open is True
            assert pane.has_class("-collapsed") is False
            assert app.query_one("#artifact-close").display is True

    asyncio.run(run())


def test_open_rail_only_when_selected_phase_has_artifacts(tmp_path):
    specs = tmp_path / ".pulse" / "specs" / "features" / "demo"
    specs.mkdir(parents=True)
    (specs / "spec.md").write_text("# Spec\n", encoding="utf-8")

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal

        holder: dict = {}

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                state = CockpitState()
                state.configure_workflow("new-issue")
                holder["state"] = state
                with Horizontal(id="cockpit-body"):
                    yield ArtifactPane(state, cwd=str(tmp_path), id="artifact-pane")

            def on_mount(self) -> None:
                state = holder["state"]
                state.begin_phase("Fase Specify")
                state.upsert_artifact(".pulse/specs/features/demo/spec.md", ready=True, has_content=True)
                state.close_artifact_pane()
                self.query_one(ArtifactPane).sync_from_state(state, force=True)

        app = Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            state = holder["state"]
            pane = app.query_one(ArtifactPane)
            assert pane.display is True
            assert pane.has_class("-collapsed") is True
            assert app.query_one("#artifact-open").display is True
            state.begin_phase("Fase Design")
            state.close_artifact_pane()
            pane.sync_from_state(state, force=True)
            await pilot.pause()
            assert state.phase_has_artifacts() is False
            assert pane.has_class("-collapsed") is False
            assert pane.display is False
            assert app.query_one("#artifact-open").display is False
            state.select_phase(0)
            pane.sync_from_state(state, force=True)
            await pilot.pause()
            assert state.phase_has_artifacts() is True
            assert pane.display is True
            assert pane.has_class("-collapsed") is True
            assert app.query_one("#artifact-open").display is True

    asyncio.run(run())
