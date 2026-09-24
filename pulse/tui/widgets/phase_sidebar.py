from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pulse.tui.state import NAV_PHASE, NAV_TASK, CockpitState, PhaseItem, PhaseStatus

_STATUS_LABEL = {
    PhaseStatus.PENDING: "pendente",
    PhaseStatus.RUNNING: "em curso",
    PhaseStatus.DONE: "concluído",
    PhaseStatus.SKIPPED: "pulado",
    PhaseStatus.FAILED: "falhou",
}


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

        for index, phase in enumerate(state.phases):
            nested = phase.id == "execute" and bool(state.tasks)
            height = 2 if nested else 3
            self._slots.append((line, line + height - 1, NAV_PHASE, index))
            selected = state.selected_nav_kind == NAV_PHASE and index == state.selected_phase_index
            output.append_text(
                self._render_item(
                    state,
                    phase,
                    selected=selected,
                    now=now,
                    trailing_blank=not nested,
                )
            )
            line += height
            if not nested:
                continue
            for task_index, task in enumerate(state.tasks):
                self._slots.append((line, line + 1, NAV_TASK, task_index))
                selected = (
                    state.selected_nav_kind == NAV_TASK and task_index == state.selected_task_index
                )
                output.append_text(
                    self._render_item(
                        state,
                        task,
                        selected=selected,
                        now=now,
                        nested=True,
                        trailing_blank=False,
                    )
                )
                line += 2
        return output

    def _render_item(
        self,
        state: CockpitState,
        item: PhaseItem,
        *,
        selected: bool,
        now: float,
        nested: bool = False,
        trailing_blank: bool = True,
    ) -> Text:
        output = Text()
        running = item.status == PhaseStatus.RUNNING
        focused = selected and state.focus_target == "phases"
        accent = running or selected
        indent = "  " if nested else ""
        if running:
            output.append(f"{indent}▌ ", style="#D4AF37")
        elif focused:
            output.append(f"{indent}▌ ", style="#A2D729")
        elif selected:
            output.append(f"{indent}│ ", style="#A2D729")
        else:
            output.append(f"{indent}  ", style="#333333")

        if item.status == PhaseStatus.RUNNING:
            prefix = "▸ "
        elif item.status == PhaseStatus.PENDING:
            prefix = "Ⅱ "
        elif item.status == PhaseStatus.SKIPPED:
            prefix = "⏭ "
        elif item.status == PhaseStatus.FAILED:
            prefix = "✗ "
        else:
            prefix = "✓ "

        name_style = "#E07070" if item.status == PhaseStatus.FAILED else (
            "#A2D729" if running else ("#E0E0E0" if accent else "#888888")
        )
        label = f"{prefix}{self._item_label(item, nested=nested)}"
        max_len = 24 if nested else 28
        if len(label) > max_len:
            label = f"{label[: max_len - 1]}…"
        output.append(label, style=name_style)
        output.append("\n")
        status = _STATUS_LABEL.get(item.status, item.status.value)
        timer = item.elapsed_label(now) or "--:--"
        meta_indent = "     " if nested else "   "
        output.append(f"{meta_indent}{status} · {timer}\n", style="#888888")
        if trailing_blank:
            output.append("\n")
        return output

    @staticmethod
    def _item_label(item: PhaseItem, *, nested: bool) -> str:
        if not nested:
            return item.label
        if item.label == item.id or item.label.startswith(f"{item.id} "):
            return item.label
        return f"{item.id} · {item.label}"
