from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from pulse.tui.app import PulseApp
from pulse.tui.screens.cockpit import CockpitScreen
from pulse.tui.screens.home import HomeScreen, default_prompt
from pulse.tui.state import LogKind, PhaseStatus
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import PhaseSidebar


def test_pulse_app_has_cockpit_theme():
    app = PulseApp()
    assert app.CSS == COCKPIT_CSS
    assert "#A2D729" in COCKPIT_CSS
    assert "SettingsScreen" in COCKPIT_CSS
    assert "OnboardingScreen" in COCKPIT_CSS
    assert "HistoryListScreen" in COCKPIT_CSS


def test_cockpit_screen_initial_state():
    screen = CockpitScreen("new-issue", "demo feature")
    assert len(screen.state.phases) == 4
    assert all(phase.status == PhaseStatus.PENDING for phase in screen.state.phases)
    assert screen.workflow_id == "new-issue"
    assert screen.sink.cockpit is True
    assert screen.state.entries == []


def test_home_opens_settings_screen(monkeypatch):
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Static

        class Harness(App[None]):
            def compose(self) -> ComposeResult:
                yield Static("ok")

            def open_settings(self) -> None:
                called.append("settings")

        called: list[str] = []
        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()
            screen.app.open_settings()
            assert called == ["settings"]

    asyncio.run(run())


def test_log_stream_and_sidebar_render_text():
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal

        state_holder: dict = {}

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                screen = CockpitScreen("fix-bug", "demo")
                state_holder["screen"] = screen
                with Horizontal(id="cockpit-body"):
                    yield PhaseSidebar(screen.state, id="phase-sidebar")
                    yield LogStream(screen.state, id="log-stream")

            def on_mount(self) -> None:
                screen = state_holder["screen"]
                screen.sink.begin_phase("Fase 1 — Planejando quick task")
                screen.sink.handle_update(
                    {
                        "update": {
                            "sessionUpdate": "tool_call",
                            "toolCallId": "t1",
                            "title": "Read File",
                            "kind": "read",
                            "rawInput": {"path": "/repo/pulse/cli.py"},
                        }
                    }
                )
                screen.sink.handle_update(
                    {
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": "Plano pronto"},
                        }
                    }
                )
                screen.sink.error(
                    "Classificação cancelada",
                    "O agente não definiu o flow (quick ou full).",
                )
                self.query_one(PhaseSidebar).sync_from_state(screen.state)
                self.query_one(LogStream).sync_from_state(screen.state, force=True)

        app = Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            content = str(app.query_one("#stream-content").render())
            phases = str(app.query_one("#phase-content").render())
            assert "Read" in content
            assert "Plano" in content
            assert "Assistente" in content
            assert "Erro" in content
            assert "Classificação cancelada" in content
            assert "flow" in content
            assert "Planejar" in phases
            assert LogKind.READ in {
                entry.kind for entry in state_holder["screen"].state.entries
            }

    asyncio.run(run())


def test_cockpit_layout_keeps_header_and_body_sizes():
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal

        from pulse.tui.state import CockpitState
        from pulse.tui.widgets.app_footer import AppFooter
        from pulse.tui.widgets.app_header import AppHeader

        state = CockpitState()
        state.configure_workflow("new-issue")
        state.set_tasks([("T1", "One", "pending"), ("T2", "Two", "pending")])

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield AppHeader()
                with Horizontal(id="cockpit-body"):
                    yield PhaseSidebar(state, id="phase-sidebar")
                    yield LogStream(state, id="log-stream")
                yield AppFooter()

            def on_mount(self) -> None:
                self.query_one(AppHeader).sync_from_state(state)
                self.query_one(PhaseSidebar).sync_from_state(state)
                self.query_one(LogStream).sync_from_state(state, force=True)
                self.query_one(AppFooter).sync_from_state(state)

        app = Harness()
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause()
            header = app.query_one(AppHeader)
            body = app.query_one("#cockpit-body")
            footer = app.query_one(AppFooter)
            sidebar = app.query_one(PhaseSidebar)
            stream = app.query_one(LogStream)
            assert header.size.height == 3
            assert footer.size.height == 1
            assert body.size.height == 28
            assert body.size.width == 120
            assert sidebar.size.height >= 24
            assert stream.size.height >= 24
            assert sidebar.size.width >= 20
            assert stream.size.width > sidebar.size.width
            assert "[............] 0/2" in str(app.query_one("#run-status").render())

    asyncio.run(run())
