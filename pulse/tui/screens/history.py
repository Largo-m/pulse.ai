from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse.history.catalog import HistoryCatalog
from pulse.history.models import HistoryItem, HistoryKind
from pulse.tui.screens.history_detail import HistoryDetailScreen

_KIND_HINT = {
    None: "todos",
    HistoryKind.ISSUE: "issues",
    HistoryKind.FIX: "fixes",
}


class HistoryListScreen(Screen[None]):
    BINDINGS = [
        ("q", "back_home", "Voltar"),
        ("b", "back_home", "Voltar"),
        ("escape", "back_home", "Voltar"),
        ("a", "filter_all", "Todos"),
        ("i", "filter_issues", "Issues"),
        ("f", "filter_fixes", "Fixes"),
        ("slash", "focus_search", "Buscar"),
        ("/", "focus_search", "Buscar"),
    ]

    def __init__(self, workspace: Path | None = None) -> None:
        super().__init__()
        self._workspace = workspace or Path.cwd()
        self._catalog = HistoryCatalog(self._workspace)
        self._query = ""
        self._kind: HistoryKind | None = None
        self._items: dict[str, HistoryItem] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="history-content"):
            yield Static("HISTÓRICO", classes="history-title")
            yield Static(self._hint_text(), id="history-hint", classes="history-hint")
            yield Input(placeholder="Buscar issues e fixes…", id="history-search")
            yield OptionList(id="history-options")
            yield Static("", id="history-empty", classes="history-empty")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()
        self.query_one("#history-search", Input).focus()

    def _hint_text(self) -> str:
        return f"Filtro: {_KIND_HINT[self._kind]}  ·  / busca  ·  A todos  ·  I issues  ·  F fixes  ·  Enter abre"

    def _refresh(self) -> None:
        items = self._catalog.search(self._query, kind=self._kind)
        self._items = {item.item_id: item for item in items}
        options = self.query_one("#history-options", OptionList)
        options.clear_options()
        empty = self.query_one("#history-empty", Static)
        hint = self.query_one("#history-hint", Static)
        hint.update(self._hint_text())
        if not items:
            empty.update("Nenhum item encontrado")
            empty.display = True
            return
        empty.update("")
        empty.display = False
        for item in items:
            options.add_option(Option(_format_item(item), id=item.item_id))

    @on(Input.Changed, "#history-search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._query = event.value
        self._refresh()

    @on(Input.Submitted, "#history-search")
    def on_search_submitted(self) -> None:
        self.query_one("#history-options", OptionList).focus()

    @on(OptionList.OptionSelected, "#history-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option_id
        if option_id is None:
            return
        item = self._items.get(str(option_id))
        if item is None:
            return
        self.app.push_screen(HistoryDetailScreen(item, workspace=self._workspace))

    def action_back_home(self) -> None:
        self.app.pop_screen()

    def action_filter_all(self) -> None:
        self._kind = None
        self._refresh()

    def action_filter_issues(self) -> None:
        self._kind = HistoryKind.ISSUE
        self._refresh()

    def action_filter_fixes(self) -> None:
        self._kind = HistoryKind.FIX
        self._refresh()

    def action_focus_search(self) -> None:
        self.query_one("#history-search", Input).focus()


def _format_item(item: HistoryItem) -> str:
    title = item.title.replace("\n", " ").strip() or item.slug
    if len(title) > 48:
        title = title[:47] + "…"
    return f"{item.kind_label:<5}  {item.status_label:<12}  {title}"
