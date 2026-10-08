from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from pulse.tui import strings

_CONFIRM = "confirm"
_CANCEL = "cancel"


class ConfirmScreen(ModalScreen[bool]):
    """Yes/no confirmation for an irreversible action.

    Cancel comes first and is preselected so a stray Enter never deletes anything.
    """

    BINDINGS = [
        ("escape", "cancel", strings.CANCEL),
        ("q", "cancel", strings.CANCEL),
        ("n", "cancel", strings.CANCEL),
    ]

    def __init__(
        self,
        *,
        title: str,
        detail: str = "",
        confirm_label: str = strings.CONFIRM,
        cancel_label: str = strings.CANCEL,
    ) -> None:
        super().__init__()
        self._title = title
        self._detail = detail
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static(self._title, classes="confirm-title")
            if self._detail:
                yield Static(self._detail, classes="confirm-detail")
            yield OptionList(
                Option(self._cancel_label, id=_CANCEL),
                Option(self._confirm_label, id=_CONFIRM),
                id="confirm-options",
            )
            yield Static(strings.HINT_CONFIRM_OR_CANCEL, classes="confirm-hint")

    def on_mount(self) -> None:
        self.query_one("#confirm-options", OptionList).focus()

    @on(OptionList.OptionSelected, "#confirm-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option_id or _CANCEL) == _CONFIRM)

    def action_cancel(self) -> None:
        self.dismiss(False)
