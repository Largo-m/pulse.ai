from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

#: Valores devolvidos pela tela.
RESUME = "resume"
RESTART = "restart"
VIEW = "view"


class ResumeChoiceScreen(ModalScreen[str | None]):
    """Pergunta o que fazer com um workflow que ficou pela metade."""

    BINDINGS = [
        ("escape", "just_view", "Só visualizar"),
        ("q", "just_view", "Só visualizar"),
    ]

    def __init__(self, *, slug: str, summary: str) -> None:
        super().__init__()
        self._slug = slug
        self._summary = summary

    def compose(self) -> ComposeResult:
        with Vertical(id="resume-box"):
            yield Static("WORKFLOW NÃO CONCLUÍDO", classes="resume-title")
            yield Static(self._slug, classes="resume-slug")
            yield Static(f"parou em: {self._summary}", classes="resume-summary")
            yield OptionList(
                Option("Retomar de onde parou", id=RESUME),
                Option("Refazer do zero (reescreve os artefatos)", id=RESTART),
                Option("Só visualizar", id=VIEW),
                id="resume-options",
            )
            yield Static("Enter confirma · Esc só visualiza", classes="resume-hint")

    def on_mount(self) -> None:
        self.query_one("#resume-options", OptionList).focus()

    @on(OptionList.OptionSelected, "#resume-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        choice = str(event.option_id or VIEW)
        self.dismiss(None if choice == VIEW else choice)

    def action_just_view(self) -> None:
        self.dismiss(None)
