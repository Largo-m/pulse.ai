from __future__ import annotations

import contextlib

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pulse.tui import strings
from pulse.tui.state import CockpitState, progress_bar


class AppHeader(Widget):
    run_label: reactive[str] = reactive(strings.HEADER_RUN_EMPTY)
    workflow_label: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-top"):
            yield Static(strings.HEADER_BRAND, classes="brand")
            yield Static(self.run_label, classes="run-status", id="run-status")
        with Horizontal(id="header-sub"):
            yield Static(strings.HEADER_PIPELINE_BADGE, classes="pipeline-badge")
            yield Static(self.workflow_label, classes="workflow-label", id="workflow-label")

    # The watchers fire before `compose` has mounted the labels; compose seeds them.
    def watch_run_label(self, value: str) -> None:
        with contextlib.suppress(NoMatches):
            self.query_one("#run-status", Static).update(value)

    def watch_workflow_label(self, value: str) -> None:
        with contextlib.suppress(NoMatches):
            self.query_one("#workflow-label", Static).update(value)

    def sync_from_state(self, state: CockpitState) -> None:
        done, total = state.done_count(), state.total_count()
        bar = progress_bar(done, total, width=12)
        label = f"[{bar}] {done}/{total}" if total else strings.HEADER_RUN_EMPTY
        if state.stopped:
            label = f"{label} · {strings.HEADER_STOPPED}"
        elif state.awaiting_input:
            label = f"{label} · {strings.HEADER_AWAITING_INPUT}"
        self.run_label = label
        self.workflow_label = state.workflow_label
