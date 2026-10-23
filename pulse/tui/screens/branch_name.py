from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse.tui import engine, strings

_CONFIRM = "confirm"
_CANCEL = "cancel"


def branch_problem(workspace: Path, name: str) -> str:
    """Why `name` cannot be the run's new branch, or empty when it can."""
    if not name:
        return strings.BRANCH_EMPTY
    try:
        valid, exists = engine.branch_check(workspace, name)
    except engine.EngineError as error:
        return error.describe()
    if not valid:
        return strings.BRANCH_INVALID
    if exists:
        return strings.BRANCH_TAKEN
    return ""


class BranchNameScreen(ModalScreen[str | None]):
    """Confirms the branch a worktree run will use. Cancel leaves the workflow unstarted."""

    BINDINGS = [
        ("escape", "cancel", strings.CANCEL),
    ]

    def __init__(self, *, suggested: str, workspace: Path) -> None:
        super().__init__()
        self._suggested = suggested
        self._workspace = workspace

    def compose(self) -> ComposeResult:
        with Vertical(id="branch-box"):
            yield Static(strings.BRANCH_TITLE, classes="branch-title")
            yield Input(value=self._suggested, id="branch-name")
            yield OptionList(
                Option(strings.BRANCH_CONFIRM, id=_CONFIRM),
                Option(strings.CANCEL, id=_CANCEL),
                id="branch-options",
            )
            yield Static("", id="branch-hint", classes="branch-hint")

    def on_mount(self) -> None:
        self.query_one("#branch-name", Input).focus()

    @on(OptionList.OptionSelected, "#branch-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if str(event.option_id or _CANCEL) == _CANCEL:
            self.dismiss(None)
            return
        self._confirm()

    @on(Input.Submitted, "#branch-name")
    def on_name_submitted(self, event: Input.Submitted) -> None:
        del event
        self._confirm()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _confirm(self) -> None:
        name = self.query_one("#branch-name", Input).value.strip()
        problem = branch_problem(self._workspace, name)
        if problem:
            self.query_one("#branch-hint", Static).update(problem)
            return
        self.dismiss(name)
