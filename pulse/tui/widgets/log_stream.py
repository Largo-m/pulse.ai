from __future__ import annotations

import re
import textwrap
from collections.abc import Callable

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from pulse.tui.adapters.prompt_bridge import PromptKind, PromptRequest, format_prompt_reply
from pulse.tui.state import CockpitState, LogKind, PhaseStatus
from pulse.tui.theme import ERROR, ERROR_SOFT
from pulse.tui.widgets.prompt_dock import PromptDock

_SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_INLINE_RE = re.compile(r"`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__")
_ASSIST_INDENT = "  "
_ASSIST_GUTTER = "│ "


def _assistant_line(text: str) -> Text:
    line = Text()
    pos = 0
    for match in _INLINE_RE.finditer(text):
        if match.start() > pos:
            line.append(text[pos : match.start()], style="#E0E0E0")
        code, bold_a, bold_b = match.groups()
        if code is not None:
            line.append(code, style="bold #A2D729")
        else:
            line.append(bold_a or bold_b or "", style="bold #E0E0E0")
        pos = match.end()
    if pos < len(text):
        line.append(text[pos:], style="#E0E0E0")
    if not line.plain:
        line.append(text, style="#E0E0E0")
    return line


def format_assistant_lines(body: str, *, width: int = 72) -> list[str]:
    text = (body or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    wrap_width = max(24, width)
    lines: list[str] = []
    paragraphs = re.split(r"\n\s*\n", text)
    for index, paragraph in enumerate(paragraphs):
        chunk = " ".join(part.strip() for part in paragraph.splitlines() if part.strip())
        if not chunk:
            continue
        wrapped = textwrap.wrap(
            chunk,
            width=wrap_width,
            break_long_words=True,
            break_on_hyphens=False,
        )
        lines.extend(wrapped or [chunk])
        if index < len(paragraphs) - 1:
            lines.append("")
    return lines


class LogStream(Widget):
    can_focus = True

    def __init__(self, state: CockpitState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state
        self._fingerprint: tuple[object, ...] | None = None
        self._spin_frame = 0

    def compose(self) -> ComposeResult:
        yield Static("", id="stream-header", classes="stream-title")
        yield Static("", id="stream-meta", classes="stream-meta")
        with VerticalScroll(id="stream-body"):
            yield Static("", id="stream-content")
        slot = Vertical(id="prompt-slot")
        slot.display = False
        yield slot

    def on_mount(self) -> None:
        self.sync_from_state(self._state, force=True)
        self.set_interval(0.08, self._tick_spinner)

    def on_resize(self) -> None:
        self.sync_from_state(self._state, force=True)

    def show_prompt(
        self,
        request: PromptRequest,
        on_result: Callable[[object | None], None],
    ) -> None:
        slot = self.query_one("#prompt-slot", Vertical)

        def _done(result: object | None) -> None:
            def _hide() -> None:
                if slot.is_mounted:
                    slot.remove_children()
                    slot.styles.height = None
                    slot.display = False

            self._state.add_qa(request.prompt, format_prompt_reply(request, result))
            self.sync_from_state(self._state, force=True)
            self.call_after_refresh(_hide)
            on_result(result)

        slot.remove_children()
        slot.styles.height = self._prompt_slot_height(request)
        slot.display = True
        slot.mount(PromptDock(request, _done))

    def focus_prompt(self) -> bool:
        try:
            dock = self.query_one(PromptDock)
        except Exception:
            return False
        dock.focus_inner()
        return True

    def _prompt_slot_height(self, request: PromptRequest) -> int:
        available = self.size.height if self.size.height > 0 else 24
        cap = max(12, min(available - 3, int(available * 0.8)))
        title = 1
        border = 1
        width = max(24, (self.size.width if self.size.width > 0 else 80) - 8)
        prompt_lines = min(3, max(1, (len(request.prompt) + width - 1) // width))
        hint = 1
        if request.kind in {PromptKind.SELECT, PromptKind.MULTI_SELECT}:
            rows = max(1, min(len(request.choices), 10))
            extra = 4 if request.kind == PromptKind.MULTI_SELECT else 0
            return min(cap, border + title + prompt_lines + hint + rows + extra)
        if request.kind == PromptKind.CONFIRM:
            return min(cap, border + title + prompt_lines + 3)
        return min(cap, border + title + prompt_lines + hint + 3)

    def _tick_spinner(self) -> None:
        if not any(entry.pending for entry in self._state.visible_entries()):
            return
        self._spin_frame = (self._spin_frame + 1) % len(_SPINNER)
        self.sync_from_state(self._state, force=True)

    def sync_from_state(self, state: CockpitState, *, force: bool = False) -> None:
        self._state = state
        fingerprint = self._state_fingerprint(state)
        header = self.query_one("#stream-header", Static)
        meta = self.query_one("#stream-meta", Static)
        content = self.query_one("#stream-content", Static)
        body = self.query_one("#stream-body", VerticalScroll)

        current = state.selected_nav_item()
        if current is not None:
            surface = current.label.upper()
        else:
            surface = state.surface_title or "RUNTIME MODE & WORKSPACE CONFIG SURFACE"
        header.update(Text(f"{surface} [backend]", style="#A2D729 bold"))
        right = " · ".join(
            part
            for part in (state.model_label or state.agent_label or "Agent", state.branch_label)
            if part
        )
        visible = state.visible_entries()
        count = len(visible)
        position = (state.selected_phase_index + 1) if state.phases else 0
        total = state.total_count()
        kind = "step"
        meta.update(
            Text(f"{count} entries · {kind} {position}/{total}          {right}", style="#888888")
        )

        if not force and fingerprint == self._fingerprint:
            return
        self._fingerprint = fingerprint
        content.update(self._render_entries(state))
        body.scroll_end(animate=False)

    def _content_width(self) -> int:
        width = self.size.width if self.size.width > 0 else 80
        return max(24, width - 6)

    @staticmethod
    def _state_fingerprint(state: CockpitState) -> tuple[object, ...]:
        entries = state.visible_entries()
        current = state.selected_nav_item()
        nav_id = current.id if current is not None else ""
        if not entries:
            return (
                0,
                "",
                0,
                False,
                nav_id,
                state.selected_phase_index,
                state.model_label,
                state.branch_label,
            )
        last = entries[-1]
        pending = any(entry.pending for entry in entries)
        return (
            len(entries),
            last.entry_id,
            len(last.body),
            last.title,
            last.detail,
            last.active,
            last.pending,
            pending,
            state.model_label,
            state.branch_label,
            nav_id,
            state.selected_phase_index,
        )

    def _render_bubble(
        self,
        entry_active: bool,
        label: str,
        body: str,
        *,
        gutter_style: str = "#4A5F1A",
        styled: bool = True,
    ) -> Text:
        output = Text()
        prefix = "▌ " if entry_active else "  "
        output.append(prefix, style="#A2D729" if entry_active else "#333333")
        output.append(f"{label}\n", style="bold #E0E0E0")
        lines = format_assistant_lines(body, width=max(24, self._content_width() - 4))
        if not lines:
            output.append("\n")
            return output
        for line in lines:
            output.append(_ASSIST_INDENT)
            if line:
                output.append(_ASSIST_GUTTER, style=gutter_style)
                if styled:
                    output.append_text(_assistant_line(line))
                else:
                    output.append(line, style="#A2D729")
            else:
                output.append(_ASSIST_GUTTER.rstrip(), style=gutter_style)
            output.append("\n")
        output.append("\n")
        return output

    def _render_assistant(self, entry_active: bool, body: str) -> Text:
        return self._render_bubble(entry_active, "Assistente", body)

    def _render_entries(self, state: CockpitState) -> Text:
        output = Text()
        entries = state.visible_entries()[-120:]
        if not entries:
            current = state.selected_nav_item()
            if current is not None and current.status in {PhaseStatus.DONE, PhaseStatus.SKIPPED}:
                output.append("Nenhuma atividade neste item.\n", style="#888888")
            else:
                output.append("Aguardando atividade do agente…\n", style="#888888")
            return output

        spin = _SPINNER[self._spin_frame]
        for index, entry in enumerate(entries):
            active = entry.active or index == len(entries) - 1
            if entry.kind == LogKind.ASSISTANT:
                output.append_text(self._render_assistant(active, entry.body or ""))
                continue
            if entry.kind == LogKind.QUESTION:
                output.append_text(
                    self._render_bubble(active, "Pergunta", entry.body or entry.title)
                )
                continue
            if entry.kind == LogKind.ANSWER:
                output.append_text(
                    self._render_bubble(
                        active,
                        "Você",
                        entry.body or entry.title,
                        gutter_style="#A2D729",
                        styled=False,
                    )
                )
                continue

            prefix = "▌ " if active else "  "
            if entry.kind == LogKind.ERROR:
                output.append(prefix, style=ERROR if active else "#333333")
                output.append("Erro\n", style=f"bold {ERROR}")
                title = entry.title.strip() or "Falha no workflow"
                output.append(f"  {escape(title)}\n", style=f"bold {ERROR_SOFT}")
                reason = entry.detail.strip()
                if reason and reason != title:
                    for line in reason.splitlines():
                        output.append(f"  {escape(line)}\n", style=ERROR)
                output.append("\n")
                continue
            output.append(prefix, style="#A2D729" if active else "#333333")
            if entry.kind == LogKind.INFO:
                output.append(f"{entry.title}\n", style="#888888")
                output.append("\n")
                continue

            if entry.pending:
                output.append(f"{spin} ", style="#A2D729")
            else:
                output.append("v ", style="#A2D729")
            output.append(f"{entry.kind.value}\n", style="#A2D729")
            target = entry.title.strip() or entry.detail.strip() or "…"
            if entry.pending and target in {"…", "..."}:
                output.append("  carregando…\n", style="#888888")
            else:
                output.append(f"  {escape(target)}\n", style="#B0B0B0")
            detail = entry.detail.strip()
            if detail and detail != target:
                for line in detail.splitlines():
                    output.append(f"    {escape(line)}\n", style="#888888")
            output.append("\n")
        return output
