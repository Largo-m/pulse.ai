from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse.tui.adapters.prompt_bridge import PromptKind, PromptRequest


class PromptModal(ModalScreen):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, request: PromptRequest) -> None:
        super().__init__()
        self._request = request
        self._selected_multi: set[str] = set()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._request.title or "Prompt", classes="modal-title")
            yield Static(self._request.prompt, classes="modal-prompt")
            if self._request.kind in {PromptKind.SELECT, PromptKind.MULTI_SELECT}:
                options = [
                    Option(label, id=option_id)
                    for option_id, label in self._request.choices
                ]
                yield OptionList(*options, id="prompt-options")
                if self._request.kind == PromptKind.MULTI_SELECT:
                    yield Static("Espaço marca · Enter confirma", classes="modal-prompt")
            if self._request.kind == PromptKind.TEXT:
                default = str(self._request.default or "")
                yield Input(value=default, placeholder="Resposta…", id="prompt-input")
            if self._request.kind == PromptKind.CONFIRM:
                with Horizontal():
                    yield Button("Sim", variant="success", id="yes")
                    yield Button("Não", variant="error", id="no")
            else:
                with Horizontal():
                    yield Button("Confirmar", variant="primary", id="ok")
                    yield Button("Cancelar", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self._submit()

    @on(Button.Pressed, "#yes")
    def on_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def on_no(self) -> None:
        self.dismiss(False)

    @on(Input.Submitted, "#prompt-input")
    def on_input_submitted(self) -> None:
        self._submit()

    @on(OptionList.OptionSelected, "#prompt-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if self._request.kind == PromptKind.SELECT:
            option_id = event.option_id
            self.dismiss(None if option_id is None else str(option_id))
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
            self.dismiss(value)
            return
        if self._request.kind == PromptKind.MULTI_SELECT:
            self.dismiss(list(self._selected_multi))
            return
        if self._request.kind == PromptKind.SELECT:
            options = self.query_one("#prompt-options", OptionList)
            highlighted = options.highlighted
            if highlighted is None:
                self.dismiss(None)
                return
            option = options.get_option_at_index(highlighted)
            self.dismiss(None if option.id is None else str(option.id))
            return
        self.dismiss(None)
