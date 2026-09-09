from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from pulse.tui.state import CockpitState


class AppFooter(Widget):
    def compose(self) -> ComposeResult:
        yield Static(id="footer-text")

    def on_mount(self) -> None:
        self.sync_from_state(None)

    def sync_from_state(self, state: CockpitState | None) -> None:
        focus = "PHASES"
        if state is not None:
            if state.focus_target == "stream":
                focus = "STREAM"
            elif state.focus_target == "artifact":
                focus = "ARTIFACT"
        text = Text()
        text.append(f"FOCUS {focus}  ", style="#888888")
        if state is not None and state.artifact_pane_open:
            text.append("[A/ESC]", style="#A2D729")
            text.append(" FECHAR  ", style="#888888")
            text.append("[[] []]", style="#A2D729")
            text.append(" FILE  ", style="#888888")
        elif state is not None and state.phase_has_artifacts():
            text.append("[A]", style="#A2D729")
            text.append(" ABRIR  ", style="#888888")
        text.append("[↑↓/JK]", style="#A2D729")
        text.append(" NAV  ", style="#888888")
        text.append("[TAB]", style="#A2D729")
        text.append(" FOCUS  ", style="#888888")
        text.append("[Q/B]", style="#A2D729")
        text.append(" MENU", style="#888888")
        self.query_one("#footer-text", Static).update(text)
