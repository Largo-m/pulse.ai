from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pulse.tui.state import NAV_PHASE, NAV_TASK, CockpitState, PhaseItem, PhaseStatus, progress_bar


class NavSelected(Message):
    def __init__(self, kind: str, index: int) -> None:
        super().__init__()
        self.kind = kind
        self.index = index


PhaseSelected = NavSelected


class PhaseSidebar(Widget):
    can_focus = True
    selected_index: reactive[int] = reactive(0)

    def __init__(self, state: CockpitState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state
        self._slots: list[tuple[int, int, str, int]] = []

    def compose(self) -> ComposeResult:
        yield Static("", id="phase-content")

    def on_mount(self) -> None:
        self.refresh_phases()
        self.set_interval(0.25, self.refresh_phases)

    def refresh_phases(self) -> None:
        content = self.query_one("#phase-content", Static)
        content.update(self._render_phases(self._state))

    def sync_from_state(self, state: CockpitState) -> None:
        self._state = state
        self.selected_index = state._selected_nav_index()
        self.refresh_phases()

    def on_click(self, event: Click) -> None:
        if not self._state.phases and not self._state.tasks:
            return
        try:
            content = self.query_one("#phase-content", Static)
        except Exception:
            return
        y = event.screen_y - content.region.y
        if y < 0:
            return
        for start, end, kind, index in self._slots:
            if start <= y <= end:
                event.stop()
                self.post_message(NavSelected(kind, index))
                return

    def _render_phases(self, state: CockpitState) -> Text:
        output = Text()
        self._slots = []
        now = time.monotonic()
        line = 0
        if not state.phases:
            output.append("Nenhum step configurado\n", style="#888888")
            return output

        output.append("STEPS\n", style="#888888")
        line += 1
        for index, phase in enumerate(state.phases):
            self._slots.append((line, line + 2, NAV_PHASE, index))
            selected = state.selected_nav_kind == NAV_PHASE and index == state.selected_phase_index
            output.append_text(self._render_item(state, phase, selected=selected, now=now))
            line += 3

        if state.tasks:
            done = state.task_done_count()
            total = state.task_total_count()
            bar = progress_bar(done, total, width=10)
            output.append("\n", style="#888888")
            line += 1
            output.append(f"TASKS {bar} {done}/{total}\n", style="#A2D729")
            line += 1
            for index, task in enumerate(state.tasks):
                self._slots.append((line, line + 2, NAV_TASK, index))
                selected = state.selected_nav_kind == NAV_TASK and index == state.selected_task_index
                output.append_text(self._render_item(state, task, selected=selected, now=now))
                line += 3
        return output

    def _render_item(
        self,
        state: CockpitState,
        item: PhaseItem,
        *,
        selected: bool,
        now: float,
    ) -> Text:
        output = Text()
        running = item.status == PhaseStatus.RUNNING
        focused = selected and state.focus_target == "phases"
        accent = running or selected
        if running:
            output.append("▌ ", style="#D4AF37")
        elif focused:
            output.append("▌ ", style="#A2D729")
        elif selected:
            output.append("│ ", style="#A2D729")
        else:
            output.append("  ", style="#333333")

        if item.status == PhaseStatus.RUNNING:
            prefix = "▸ "
        elif item.status == PhaseStatus.PENDING:
            prefix = "Ⅱ "
        elif item.status == PhaseStatus.SKIPPED:
            prefix = "⏭ "
        else:
            prefix = "✓ "

        name_style = "#A2D729" if running else ("#E0E0E0" if accent else "#888888")
        label = f"{prefix}{item.label}"
        if len(label) > 28:
            label = f"{label[:27]}…"
        output.append(label, style=name_style)
        output.append("\n")
        status = item.status.value.upper()
        timer = item.elapsed_label(now) or "--:--"
        output.append(f"   {status} · {timer}\n", style="#888888")
        output.append("\n")
        return output
