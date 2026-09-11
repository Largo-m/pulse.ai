from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen

from pulse.history.hydrate import hydrate_history_item
from pulse.history.models import HistoryItem
from pulse.tui.widgets.app_footer import AppFooter
from pulse.tui.widgets.app_header import AppHeader
from pulse.tui.widgets.artifact_pane import (
    ArtifactPane,
    ArtifactPaneClosed,
    ArtifactPaneOpened,
    ArtifactTabSelected,
)
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import NavSelected, PhaseSidebar


class HistoryDetailScreen(Screen[None]):
    BINDINGS = [
        ("q", "back_list", "Voltar"),
        ("b", "back_list", "Voltar"),
        ("tab", "toggle_focus", "Focus"),
        ("a", "toggle_artifact_pane", "Artifacts"),
        ("escape", "escape_back", "Back"),
        ("left_square_bracket", "artifact_prev", "Prev file"),
        ("right_square_bracket", "artifact_next", "Next file"),
        ("left", "artifact_left", "Prev file"),
        ("right", "artifact_right", "Next file"),
        ("up", "nav_up", "Up"),
        ("down", "nav_down", "Down"),
        ("k", "nav_up", "Up"),
        ("j", "nav_down", "Down"),
    ]

    def __init__(self, item: HistoryItem, workspace: Path | None = None) -> None:
        super().__init__()
        self.item = item
        self._cwd = str(workspace or Path.cwd())
        self.state = hydrate_history_item(item, Path(self._cwd))

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="cockpit-body"):
            yield PhaseSidebar(self.state, id="phase-sidebar")
            yield LogStream(self.state, id="log-stream")
            yield ArtifactPane(self.state, cwd=self._cwd, id="artifact-pane")
        yield AppFooter(back_label="VOLTAR")

    def on_mount(self) -> None:
        self._sync_ui(force=True)

    def _sync_ui(self, *, force: bool = False) -> None:
        body = self.query_one("#cockpit-body")
        body.set_class(self.state.artifact_pane_open, "artifacts-open")
        body.set_class(
            self.state.phase_has_artifacts() and not self.state.artifact_pane_open,
            "artifacts-rail",
        )
        self.query_one(AppHeader).sync_from_state(self.state)
        self.query_one(PhaseSidebar).sync_from_state(self.state)
        self.query_one(LogStream).sync_from_state(self.state, force=force)
        self.query_one(ArtifactPane).sync_from_state(self.state, force=force)
        self.query_one(AppFooter).sync_from_state(self.state)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "close_artifact_pane":
            return self.state.artifact_pane_open
        if action == "toggle_artifact_pane":
            return self.state.artifact_pane_open or self.state.phase_has_artifacts()
        if action in {"artifact_prev", "artifact_next"}:
            return self.state.artifact_pane_open
        if action in {"artifact_left", "artifact_right"}:
            return self.state.artifact_pane_open and self.state.focus_target == "artifact"
        return True

    def action_escape_back(self) -> None:
        if self.state.artifact_pane_open:
            self.action_close_artifact_pane()
            return
        self.action_back_list()

    def _apply_focus(self) -> None:
        if self.state.focus_target == "phases":
            self.query_one(PhaseSidebar).focus()
        elif self.state.focus_target == "artifact" and self.state.artifact_pane_open:
            self.query_one(ArtifactPane).focus()
        else:
            self.query_one(LogStream).focus()

    def action_toggle_focus(self) -> None:
        self.state.toggle_focus()
        self._sync_ui(force=True)
        self._apply_focus()

    def action_toggle_artifact_pane(self) -> None:
        self.state.toggle_artifact_pane()
        self._sync_ui(force=True)
        self._apply_focus()

    def action_close_artifact_pane(self) -> None:
        if not self.state.artifact_pane_open:
            return
        self.state.close_artifact_pane()
        self._sync_ui(force=True)
        self._apply_focus()

    def action_open_artifact_pane(self) -> None:
        if self.state.artifact_pane_open or not self.state.phase_has_artifacts():
            return
        self.state.open_artifact_pane()
        self._sync_ui(force=True)
        self._apply_focus()

    def on_artifact_pane_closed(self, event: ArtifactPaneClosed) -> None:
        event.stop()
        self.action_close_artifact_pane()

    def on_artifact_pane_opened(self, event: ArtifactPaneOpened) -> None:
        event.stop()
        self.action_open_artifact_pane()

    def action_artifact_prev(self) -> None:
        if not self.state.artifact_pane_open:
            return
        self.state.move_artifact(-1)
        self._sync_ui(force=True)

    def action_artifact_next(self) -> None:
        if not self.state.artifact_pane_open:
            return
        self.state.move_artifact(1)
        self._sync_ui(force=True)

    def action_artifact_left(self) -> None:
        self.action_artifact_prev()

    def action_artifact_right(self) -> None:
        self.action_artifact_next()

    def action_nav_up(self) -> None:
        if self.state.focus_target == "artifact":
            self.query_one(ArtifactPane).scroll_by(-1)
            return
        if self.state.focus_target != "phases":
            return
        self.state.move_nav(-1)
        self._sync_ui(force=True)

    def action_nav_down(self) -> None:
        if self.state.focus_target == "artifact":
            self.query_one(ArtifactPane).scroll_by(1)
            return
        if self.state.focus_target != "phases":
            return
        self.state.move_nav(1)
        self._sync_ui(force=True)

    def on_nav_selected(self, event: NavSelected) -> None:
        if event.kind == "task":
            self.state.select_task(event.index)
        else:
            self.state.select_phase(event.index)
        self.state.focus_target = "phases"
        self._sync_ui(force=True)

    def on_artifact_tab_selected(self, event: ArtifactTabSelected) -> None:
        self.state.select_artifact(event.path)
        self.state.focus_target = "artifact"
        self._sync_ui(force=True)

    def action_back_list(self) -> None:
        self.app.pop_screen()
