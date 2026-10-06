from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pulse.status_labels import status_color, status_icon, status_label
from pulse.tui.state import NAV_PHASE, CockpitState, PhaseItem, PhaseStatus


class NavSelected(Message):
    def __init__(self, kind: str, index: int) -> None:
        super().__init__()
        self.kind = kind
        self.index = index


PhaseSelected = NavSelected

#: Estados em que a cor do status manda no nome do step: os que pedem atenção.
#: Nos demais, o realce é da seleção. Comparados como texto porque
#: `awaiting_input` é sobreposição de exibição, não membro de `PhaseStatus` —
#: ver [PhaseItem.display_status].
_ATTENTION = frozenset(
    {
        PhaseStatus.RUNNING.value,
        PhaseStatus.FAILED.value,
        PhaseStatus.BLOCKED.value,
        "awaiting_input",
    }
)


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
        if not self._state.phases:
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

        for key, members in state.phase_groups():
            # O step de fan-out não some da lista: ele vira o cabeçalho das
            # tasks que gerou, e elas aparecem indentadas embaixo dele.
            if key:
                output.append_text(self._render_group(state, key, members))
                line += 2
            for index, phase in members:
                self._slots.append((line, line + 2, NAV_PHASE, index))
                output.append_text(
                    self._render_item(
                        state,
                        phase,
                        selected=index == state.selected_phase_index,
                        now=now,
                        nested=bool(key),
                        trailing_blank=True,
                    )
                )
                line += 3
        return output

    def _render_group(
        self,
        state: CockpitState,
        key: str,
        members: list[tuple[int, PhaseItem]],
    ) -> Text:
        """Cabeçalho do fan-out: o nome do step e quantas tasks já fecharam."""
        statuses = [phase.status for _index, phase in members]
        done = sum(1 for status in statuses if status in {PhaseStatus.DONE, PhaseStatus.SKIPPED})
        if PhaseStatus.FAILED in statuses:
            status = PhaseStatus.FAILED
        elif PhaseStatus.BLOCKED in statuses:
            status = PhaseStatus.BLOCKED
        elif PhaseStatus.RUNNING in statuses:
            status = PhaseStatus.RUNNING
        elif done == len(statuses):
            status = PhaseStatus.DONE
        else:
            status = PhaseStatus.PENDING

        # Uma task esperando o usuário manda no cabeçalho: é o grupo inteiro que
        # não avança enquanto ninguém responde.
        shown = (
            "awaiting_input"
            if any(phase.awaiting_since is not None for _index, phase in members)
            else status.value
        )

        output = Text()
        if status == PhaseStatus.RUNNING:
            output.append("▌ ", style="#D4AF37")
        else:
            output.append("  ", style="#333333")
        tone = status_color(shown)
        name_style = tone if shown in _ATTENTION else "#E0E0E0"
        label = f"{status_icon(shown)} {state.base_step_label(key) or key}"
        if len(label) > 28:
            label = f"{label[:27]}…"
        output.append(label, style=name_style)
        output.append("\n")
        output.append("   ")
        output.append(status_label(shown), style=tone)
        output.append(f" · {done}/{len(members)}\n", style="#888888")
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

        # A cor do status manda no nome só quando ele pede atenção (rodando,
        # esperando resposta ou quebrado); nos demais, o realce é da seleção.
        shown = item.display_status()
        tone = status_color(shown)
        name_style = tone if shown in _ATTENTION else (
            "#E0E0E0" if accent else "#888888"
        )
        # O contador das voltas de um laço fica fora do corte do rótulo: ele é
        # curto, e é justamente o que não pode sumir num nome comprido.
        rounds = f" ×{item.rounds}" if item.rounds > 1 else ""
        label = f"{status_icon(shown)} {self._item_label(item, nested=nested)}"
        max_len = (24 if nested else 28) - len(rounds)
        if len(label) > max_len:
            label = f"{label[: max_len - 1]}…"
        output.append(label, style=name_style)
        if rounds:
            output.append(rounds, style="#D4AF37")
        output.append("\n")
        timer = item.elapsed_label(now) or "--:--"
        meta_indent = "     " if nested else "   "
        output.append(meta_indent)
        output.append(status_label(shown), style=tone)
        output.append(f" · {timer}\n", style="#888888")
        if trailing_blank:
            output.append("\n")
        return output

    @staticmethod
    def _item_label(item: PhaseItem, *, nested: bool) -> str:
        if not nested:
            return item.label
        # `implement:T1` → `T1`: o prefixo é o cabeçalho logo acima, repetir em
        # cada filho só gastaria a largura da coluna.
        _base, _sep, task_id = item.id.partition(":")
        if not task_id or item.label == task_id or item.label.startswith(f"{task_id} "):
            return item.label or task_id
        return f"{task_id} · {item.label}"
