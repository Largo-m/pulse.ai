from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pulse.tui.state import CockpitState, PhaseStatus


class PhaseSidebar(Widget):
    can_focus = True
    selected_index: reactive[int] = reactive(0)

    def __init__(self, state: CockpitState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Static("", id="phase-content")

    def on_mount(self) -> None:
        self.refresh_phases()
        self.set_interval(1.0, self.refresh_phases)

    def refresh_phases(self) -> None:
        content = self.query_one("#phase-content", Static)
        content.update(self._render_phases(self._state))

    def sync_from_state(self, state: CockpitState) -> None:
        self._state = state
        self.selected_index = state.selected_phase_index
        self.refresh_phases()

    def _render_phases(self, state: CockpitState) -> Text:
        output = Text()
        now = time.monotonic()
        if not state.phases:
            output.append("Nenhuma fase configurada\n", style="#888888")
            return output

        for index, phase in enumerate(state.phases):
            running = phase.status == PhaseStatus.RUNNING
            selected = index == state.selected_phase_index and state.focus_target == "phases"
            accent = running or selected

            if running:
                output.append("▌ ", style="#D4AF37")
            else:
                output.append("  ", style="#333333")

            if phase.status == PhaseStatus.RUNNING:
                prefix = "▸ "
            elif phase.status == PhaseStatus.PENDING:
                prefix = "Ⅱ "
            elif phase.status == PhaseStatus.SKIPPED:
                prefix = "⏭ "
            else:
                prefix = "✓ "

            name_style = "#A2D729" if running else ("#E0E0E0" if accent else "#888888")
            label = f"{prefix}{phase.label}"
            output.append(label, style=name_style)
            timer = phase.elapsed_label(now)
            if timer:
                output.append(f"  {timer}", style="#888888")
            output.append("\n")

            status = phase.status.value.upper()
            meta = f"   {status} · FILES {phase.files} · ISSUES {phase.issues}\n"
            output.append(meta, style="#888888")
            output.append("\n")
        return output
