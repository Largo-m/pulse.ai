from __future__ import annotations

from collections.abc import Callable

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse.tui.adapters.prompt_bridge import PromptKind, PromptRequest


class PromptDock(Widget):
    can_focus = True
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        request: PromptRequest,
        on_result: Callable[[object | None], None],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._request = request
        self._on_result = on_result
        self._selected_multi: set[str] = set()
        self._closed = False

    def compose(self) -> ComposeResult:
        yield Static(self._request.title or "Prompt", classes="prompt-title")
        yield Static(self._request.prompt, classes="prompt-text")
        kind = self._request.kind
        if kind in {PromptKind.SELECT, PromptKind.MULTI_SELECT}:
            options = [
                Option(label, id=option_id or None)
                for option_id, label in self._request.choices
            ]
            yield OptionList(*options, id="prompt-options", compact=True)
            if kind == PromptKind.MULTI_SELECT:
                yield Static("Espaço marca · Enter confirma · Esc cancela", classes="prompt-hint")
                with Horizontal(id="prompt-actions"):
                    yield Button("Confirmar", variant="primary", id="ok")
                    yield Button("Cancelar", id="cancel")
            else:
                yield Static("↑↓ escolhe · Enter confirma · Esc cancela", classes="prompt-hint")
        elif kind == PromptKind.TEXT:
            default = str(self._request.default or "")
            yield Input(value=default, placeholder="Resposta…", id="prompt-input")
            yield Static("Enter confirma · Esc cancela", classes="prompt-hint")
        elif kind == PromptKind.CONFIRM:
            with Horizontal(id="prompt-actions"):
                yield Button("Sim", variant="success", id="yes")
                yield Button("Não", variant="error", id="no")

    def on_mount(self) -> None:
        kind = self._request.kind
        if kind in {PromptKind.SELECT, PromptKind.MULTI_SELECT}:
            options = self.query_one("#prompt-options", OptionList)
            options.styles.height = max(1, min(len(self._request.choices), 10))
            options.focus()
        elif kind == PromptKind.TEXT:
            self.query_one("#prompt-input", Input).focus()
        elif kind == PromptKind.CONFIRM:
            self.query_one("#yes", Button).focus()

    def action_cancel(self) -> None:
        self._finish(None)

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self._finish(None)

    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self._submit()

    @on(Button.Pressed, "#yes")
    def on_yes(self) -> None:
        self._finish(True)

    @on(Button.Pressed, "#no")
    def on_no(self) -> None:
        self._finish(False)

    @on(Input.Submitted, "#prompt-input")
    def on_input_submitted(self) -> None:
        self._submit()

    @on(OptionList.OptionSelected, "#prompt-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if self._request.kind == PromptKind.SELECT:
            option_id = event.option_id
            self._finish(None if option_id is None else str(option_id))
        elif self._request.kind == PromptKind.MULTI_SELECT:
            option_id = event.option_id
            if option_id is None:
                return
            key = str(option_id)
            if key in self._selected_multi:
                self._selected_multi.remove(key)
            else:
                self._selected_multi.add(key)

    def _submit(self) -> None:
        if self._request.kind == PromptKind.TEXT:
            value = self.query_one("#prompt-input", Input).value
            self._finish(value)
            return
        if self._request.kind == PromptKind.MULTI_SELECT:
            self._finish(list(self._selected_multi))
            return
        if self._request.kind == PromptKind.SELECT:
            options = self.query_one("#prompt-options", OptionList)
            highlighted = options.highlighted
            if highlighted is None:
                self._finish(None)
                return
            option = options.get_option_at_index(highlighted)
            self._finish(None if option.id is None else str(option.id))
            return
        self._finish(None)

    def _finish(self, result: object | None) -> None:
        if self._closed:
            return
        self._closed = True
        callback = self._on_result
        self._on_result = None
        if callback is not None:
            callback(result)
