from __future__ import annotations

from textual.app import App

from pulse.tui.screens.cockpit import CockpitScreen
from pulse.tui.screens.history import HistoryListScreen
from pulse.tui.screens.home import HomeScreen
from pulse.tui.theme import COCKPIT_CSS


class PulseApp(App[None]):
    CSS = COCKPIT_CSS
    TITLE = "Pulse // ACP Cockpit"

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())

    def open_cockpit(self, workflow_id: str, user_prompt: str) -> None:
        self.push_screen(CockpitScreen(workflow_id, user_prompt))

    def open_history(self) -> None:
        self.push_screen(HistoryListScreen())


def run_pulse_app() -> int:
    app = PulseApp()
    app.run()
    return 0
