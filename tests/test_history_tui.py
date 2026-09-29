from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from tests.conftest import make_workflow

from pulse.history.catalog import HistoryCatalog
from pulse.store import runs as run_store
from pulse.store.runs import DONE, StepRecord
from pulse.tui.screens.history import HistoryListScreen
from pulse.tui.screens.history_detail import HistoryDetailScreen
from pulse.tui.state import PhaseStatus
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import PhaseSidebar


def _finished_run(workspace: Path, run_id: str, prompt: str) -> str:
    make_workflow("demo", steps=[("plan", "Planejar"), ("build", "Construir")])
    record = run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt=prompt,
        steps=[
            StepRecord(step_id="plan", position=1, label="Planejar", agent_id="tester"),
            StepRecord(step_id="build", position=2, label="Construir", agent_id="tester"),
        ],
    )
    for step in record.steps:
        step.status = DONE
        run_store.save_step(record.id, step)
    run_store.update_run(record.id, status="completed")
    return record.id


def test_history_list_filters_items(tmp_path: Path):
    _finished_run(tmp_path, "run-login", "Adicionar login social")
    _finished_run(tmp_path, "run-token", "Corrigir refresh token")

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryListScreen(workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryListScreen)
            assert set(screen._items) == {"run-login", "run-token"}

            screen._query = "token"
            screen._refresh()
            await pilot.pause()
            assert set(screen._items) == {"run-token"}

    asyncio.run(run())


def test_history_detail_renders_steps_without_run_log(tmp_path: Path):
    run_id = _finished_run(tmp_path, "run-login", "Adicionar login social")
    item = HistoryCatalog(tmp_path).get(run_id)
    assert item is not None

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryDetailScreen(item, workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryDetailScreen)
            assert screen.state.phases[0].status == PhaseStatus.DONE
            content = str(screen.query_one("#stream-content").render())
            phases = str(screen.query_one("#phase-content").render())
            assert "Planejar" in phases
            assert "Nenhum log persistido" in content
            assert screen.state.acp_session_id == ""
            assert screen.query_one(PhaseSidebar)
            assert screen.query_one(LogStream)

    asyncio.run(run())


def test_history_detail_replays_the_log_from_the_database(tmp_path: Path):
    """Log é do Pulse: uma run feita em qualquer runtime reabre com o stream."""
    run_id = _finished_run(tmp_path, "run-login", "Adicionar login social")
    run_store.record_event(
        run_id,
        step_id="plan",
        kind="Assistant",
        title="Plano pronto",
        detail="Plano pronto",
    )
    item = HistoryCatalog(tmp_path).get(run_id)
    assert item is not None

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryDetailScreen(item, workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            content = str(app.screen.query_one("#stream-content").render())
            assert "Plano pronto" in content

    asyncio.run(run())
