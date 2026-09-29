from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pulse.status_labels import status_label
from pulse.tui.state import CockpitState, progress_bar


class AppHeader(Widget):
    run_label: reactive[str] = reactive("RUN 0/0")
    workflow_label: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-top"):
            yield Static("PULSE // ACP COCKPIT", classes="brand")
            yield Static(self.run_label, classes="run-status", id="run-status")
        with Horizontal(id="header-sub"):
            yield Static("SYS.PIPELINE", classes="pipeline-badge")
            yield Static(self.workflow_label, classes="workflow-label", id="workflow-label")

    def watch_run_label(self, value: str) -> None:
        try:
            self.query_one("#run-status", Static).update(value)
        except Exception:
            pass

    def watch_workflow_label(self, value: str) -> None:
        try:
            self.query_one("#workflow-label", Static).update(value)
        except Exception:
            pass

    def sync_from_state(self, state: CockpitState) -> None:
        done, total = state.done_count(), state.total_count()
        bar = progress_bar(done, total, width=12)
        label = f"[{bar}] {done}/{total}" if total else "RUN 0/0"
        if state.paused:
            label = f"{label} · {status_label('paused').upper()}"
        elif state.stopped:
            label = f"{label} · PARADA"
        self.run_label = label
        self.workflow_label = state.workflow_label
