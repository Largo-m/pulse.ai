from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from pulse.tui.state import CockpitState, LogKind


class LogStream(Widget):
    can_focus = True

    def __init__(self, state: CockpitState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state
        self._fingerprint: tuple[object, ...] | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="stream-header", classes="stream-title")
        yield Static("", id="stream-meta", classes="stream-meta")
        with VerticalScroll(id="stream-body"):
            yield Static("", id="stream-content")

    def on_mount(self) -> None:
        self.sync_from_state(self._state, force=True)

    def sync_from_state(self, state: CockpitState, *, force: bool = False) -> None:
        self._state = state
        fingerprint = self._state_fingerprint(state)
        header = self.query_one("#stream-header", Static)
        meta = self.query_one("#stream-meta", Static)
        content = self.query_one("#stream-content", Static)
        body = self.query_one("#stream-body", VerticalScroll)

        surface = state.surface_title or "RUNTIME MODE & WORKSPACE CONFIG SURFACE"
        header.update(Text(f"{surface} [backend]", style="#A2D729 bold"))
        right = state.model_label or state.agent_label or "Agent"
        count = len(state.entries)
        meta.update(
            Text(f"{count} entries · selected {count}/{count}          {right}", style="#888888")
        )

        if not force and fingerprint == self._fingerprint:
            return
        self._fingerprint = fingerprint
        content.update(self._render_entries(state))
        body.scroll_end(animate=False)

    @staticmethod
    def _state_fingerprint(state: CockpitState) -> tuple[object, ...]:
        if not state.entries:
            return (0, "", 0)
        last = state.entries[-1]
        return (len(state.entries), last.entry_id, len(last.body), last.title, last.detail, last.active)

    def _render_entries(self, state: CockpitState) -> Text:
        output = Text()
        entries = state.entries[-120:]
        if not entries:
            output.append("Aguardando atividade do agente…\n", style="#888888")
            return output

        for index, entry in enumerate(entries):
            active = entry.active or index == len(entries) - 1
            prefix = "▌ " if active else "  "
            if entry.kind == LogKind.ASSISTANT:
                output.append(prefix, style="#A2D729" if active else "#333333")
                output.append("Assistant\n", style="bold #E0E0E0")
                body = (entry.body or "").rstrip()
                if body:
                    for line in body.splitlines() or [""]:
                        output.append(f"  {line}\n", style="#E0E0E0")
                output.append("\n")
                continue

            mark = "v " if entry.kind != LogKind.INFO else "· "
            output.append(prefix, style="#A2D729" if active else "#333333")
            if entry.kind == LogKind.INFO:
                output.append(f"{entry.title}\n", style="#888888")
                output.append("\n")
                continue

            target = entry.title.strip() or entry.detail.strip() or "…"
            output.append(mark, style="#A2D729")
            output.append(f"{entry.kind.value}  ", style="#A2D729")
            output.append(f"{target}\n", style="#A2D729")
            detail = entry.detail.strip()
            if detail and detail != target:
                for line in detail.splitlines():
                    output.append(f"    {line}\n", style="#888888")
            output.append("\n")
        return output
