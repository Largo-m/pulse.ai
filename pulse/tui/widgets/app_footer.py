from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from pulse.tui import strings
from pulse.tui.state import CockpitState

if TYPE_CHECKING:
    from typing import Unpack

    from pulse.tui.widgets.options import WidgetOptions


class AppFooter(Widget):
    def __init__(
        self, back_label: str = strings.FOOTER_MENU, **kwargs: Unpack[WidgetOptions]
    ) -> None:
        super().__init__(**kwargs)
        self._back_label = back_label

    def compose(self) -> ComposeResult:
        yield Static(id="footer-text")

    def on_mount(self) -> None:
        self.sync_from_state(None)

    def sync_from_state(self, state: CockpitState | None) -> None:
        focus = strings.FOOTER_FOCUS_PHASES
        if state is not None:
            if state.focus_target == "stream":
                focus = strings.FOOTER_FOCUS_STREAM
            elif state.focus_target == "artifact":
                focus = strings.FOOTER_FOCUS_ARTIFACT
        text = Text()
        text.append(f"{strings.FOOTER_FOCUS} {focus}  ", style="#888888")
        if state is not None and state.artifact_pane_open:
            text.append("[A/ESC]", style="#A2D729")
            text.append(f" {strings.FOOTER_CLOSE}  ", style="#888888")
            text.append("[[] []]", style="#A2D729")
            text.append(f" {strings.FOOTER_FILE}  ", style="#888888")
        elif state is not None and state.phase_has_artifacts():
            text.append("[A]", style="#A2D729")
            text.append(f" {strings.FOOTER_OPEN}  ", style="#888888")
        if state is not None and state.running and state.can_stop:
            text.append("[S]", style="#A2D729")
            text.append(f" {strings.FOOTER_STOP}  ", style="#888888")
        text.append("[↑↓/JK]", style="#A2D729")
        text.append(f" {strings.FOOTER_NAV}  ", style="#888888")
        text.append("[TAB]", style="#A2D729")
        text.append(f" {strings.FOOTER_FOCUS}  ", style="#888888")
        text.append("[Q/B]", style="#A2D729")
        text.append(f" {self._back_label}", style="#888888")
        self.query_one("#footer-text", Static).update(text)
