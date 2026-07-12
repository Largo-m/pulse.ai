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


def test_cockpit_screen_initial_state():
    screen = CockpitScreen("new-issue", "demo feature")
    assert len(screen.state.phases) == 4
    assert all(phase.status == PhaseStatus.PENDING for phase in screen.state.phases)
    assert screen.workflow_id == "new-issue"
    assert screen.sink.cockpit is True


def test_home_default_prompts():
    assert default_prompt("setup-project") == "Novo projeto"
    assert default_prompt("analyze-codebase") == "Mapear codebase existente"
    assert HomeScreen is not None


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
                self.query_one(PhaseSidebar).sync_from_state(screen.state)
                self.query_one(LogStream).sync_from_state(screen.state, force=True)

        app = Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            content = str(app.query_one("#stream-content").render())
            phases = str(app.query_one("#phase-content").render())
            assert "Read" in content
            assert "Plano" in content or "Assistant" in content
            assert "Planejar" in phases
            assert LogKind.READ in {
                entry.kind for entry in state_holder["screen"].state.entries
            }

    asyncio.run(run())
