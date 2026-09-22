from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("textual")

from pulse.history.catalog import HistoryCatalog
from pulse.history.models import HistoryKind, RunRecord, RunStatus
from pulse.history.runs import save_run
from pulse.plan.specify_state import WorkflowState
from pulse.tui.screens.history import HistoryListScreen
from pulse.tui.screens.history_detail import HistoryDetailScreen
from pulse.tui.state import PhaseStatus
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
            assert set(screen._items) == {
                "spec:features/login-flow",
                "spec:quick/001-token-refresh",
            }

            screen._query = "token"
            screen._refresh()
            await pilot.pause()
            assert set(screen._items) == {"spec:quick/001-token-refresh"}

    asyncio.run(run())


def test_history_detail_renders_steps_and_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_issue(tmp_path)
    session_id = "sess-login"
    store_root = tmp_path / "acp-sessions" / session_id
    store_root.mkdir(parents=True)
    db = store_root / "store.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    blob = {
        "role": "assistant",
        "content": [
            {
                "type": "tool-call",
                "toolCallId": "call-1",
                "title": "Read spec.md",
                "toolName": "Read",
                "args": {"path": "spec.md"},
            },
            {
                "type": "text",
                "text": "Specify concluído",
            },
        ],
    }
    con.execute("INSERT INTO blobs(id, data) VALUES (?, ?)", ("1", json.dumps(blob).encode("utf-8")))
    con.commit()
    con.close()
    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", tmp_path / "acp-sessions")
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")
    save_run(
        tmp_path,
        RunRecord(
            id="run-login",
            workflow_id="new-issue",
            prompt="Adicionar login social",
            status=RunStatus.COMPLETED,
            kind=HistoryKind.SPEC,
            slug="login-flow",
            spec_dir=".pulse/specs/features/login-flow",
            started_at="2026-01-02T00:00:00+00:00",
            ended_at="2026-01-02T01:00:00+00:00",
            exit_code=0,
            acp_session_id=session_id,
        ),
        [],
    )
    item = HistoryCatalog(tmp_path).get("spec:features/login-flow")
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
            assert "Read spec.md" in content or "Tool" in content
            assert "Specify concluído" in content
            assert screen.state.acp_session_id == "sess-login"
            assert screen.query_one(PhaseSidebar)
            assert screen.query_one(LogStream)

    asyncio.run(run())
