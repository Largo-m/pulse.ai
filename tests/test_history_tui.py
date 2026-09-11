from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from pulse.history.catalog import HistoryCatalog
from pulse.history.models import HistoryKind, RunRecord, RunStatus
from pulse.history.runs import save_run
from pulse.plan.specify_state import WorkflowState
from pulse.tui.screens.history import HistoryListScreen
from pulse.tui.screens.history_detail import HistoryDetailScreen
from pulse.tui.state import LogEntry, LogKind, PhaseStatus
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import PhaseSidebar


def _write_issue(workspace: Path) -> None:
    state = WorkflowState.create_new(feature_slug="login-flow", user_prompt="Adicionar login social")
    for phase in ("specify", "design", "tasks"):
        state.approve_phase(phase)
        state.mark_phase_done(phase)
    state.mark_phase_done("execute")
    state.save(workspace)
    (workspace / ".pulse/specs/features/login-flow/spec.md").write_text("# Spec\n", encoding="utf-8")


def _write_fix(workspace: Path) -> None:
    path = workspace / ".pulse/specs/quick/001-token-refresh/TASK.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Quick Task 001: Corrigir refresh token\n\n**Status:** Done\n",
        encoding="utf-8",
    )


def test_history_list_filters_items(tmp_path: Path):
    _write_issue(tmp_path)
    _write_fix(tmp_path)

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
            assert set(screen._items) == {"issue:login-flow", "fix:001-token-refresh"}

            screen.action_filter_issues()
            await pilot.pause()
            assert set(screen._items) == {"issue:login-flow"}

            screen.action_filter_fixes()
            await pilot.pause()
            assert set(screen._items) == {"fix:001-token-refresh"}

            screen.action_filter_all()
            screen._query = "token"
            screen._refresh()
            await pilot.pause()
            assert set(screen._items) == {"fix:001-token-refresh"}

    asyncio.run(run())


def test_history_detail_renders_steps_and_logs(tmp_path: Path):
    _write_issue(tmp_path)
    save_run(
        tmp_path,
        RunRecord(
            id="run-login",
            workflow_id="new-issue",
            prompt="Adicionar login social",
            status=RunStatus.COMPLETED,
            kind=HistoryKind.ISSUE,
            slug="login-flow",
            spec_dir=".pulse/specs/features/login-flow",
            started_at="2026-01-02T00:00:00+00:00",
            ended_at="2026-01-02T01:00:00+00:00",
            exit_code=0,
        ),
        [
            LogEntry(
                kind=LogKind.READ,
                title="spec.md",
                detail="Reading spec.md",
                entry_id=1,
                phase_id="specify",
            ),
            LogEntry(
                kind=LogKind.ASSISTANT,
                title="Assistant",
                body="Specify concluído",
                entry_id=2,
                phase_id="specify",
            ),
        ],
    )
    item = HistoryCatalog(tmp_path).get("issue:login-flow")
    assert item is not None
    assert item.run_id == "run-login"

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
            assert "Specify" in phases
            assert "Read" in content
            assert "Specify concluído" in content or "Assistente" in content
            assert LogKind.READ in {entry.kind for entry in screen.state.entries}
            assert screen.query_one(PhaseSidebar)
            assert screen.query_one(LogStream)

    asyncio.run(run())
