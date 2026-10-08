from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from pulse.tui import strings

RESUME = "resume"
BACK = "back"


class ResumeChoiceScreen(ModalScreen[str | None]):
    """Asks what to do with a workflow that was left unfinished."""

    BINDINGS = [
        ("escape", "back", strings.BACK),
        ("q", "back", strings.BACK),
    ]

    def __init__(self, *, slug: str, summary: str) -> None:
        super().__init__()
        self._slug = slug
        self._summary = summary

    def compose(self) -> ComposeResult:
        with Vertical(id="resume-box"):
            yield Static(strings.RESUME_TITLE, classes="resume-title")
            yield Static(self._slug, classes="resume-slug")
            yield Static(
                strings.RESUME_STOPPED_AT.format(summary=self._summary), classes="resume-summary"
            )
            yield OptionList(
                Option(strings.RESUME_OPTION, id=RESUME),
                Option(strings.BACK, id=BACK),
                id="resume-options",
            )
            yield Static(strings.HINT_CONFIRM_OR_BACK, classes="resume-hint")

    def on_mount(self) -> None:
        self.query_one("#resume-options", OptionList).focus()

    @on(OptionList.OptionSelected, "#resume-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        choice = str(event.option_id or BACK)
        self.dismiss(None if choice == BACK else choice)

    def action_back(self) -> None:
        self.dismiss(None)
