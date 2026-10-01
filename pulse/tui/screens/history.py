from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse.client.active_runs import active_run_ids
from pulse.history.catalog import HistoryCatalog
from pulse.history.models import HistoryItem, HistoryStatus
from pulse.status_labels import LABEL_WIDTH, status_color
from pulse.tui.screens.confirm import ConfirmScreen
from pulse.tui.screens.history_detail import HistoryDetailScreen


class HistoryListScreen(Screen[None]):
    BINDINGS = [
        ("q", "back_home", "Voltar"),
        ("b", "back_home", "Voltar"),
        ("escape", "back_home", "Voltar"),
        ("slash", "focus_search", "Buscar"),
        ("/", "focus_search", "Buscar"),
        ("d", "delete_run", "Remover"),
        ("delete", "delete_run", "Remover"),
    ]

    def __init__(self, workspace: Path | None = None) -> None:
        super().__init__()
        self._workspace = workspace or Path.cwd()
        self._catalog = HistoryCatalog(self._workspace)
        self._query = ""
        self._items: dict[str, HistoryItem] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="history-content"):
            yield Static("HISTÓRICO", classes="history-title")
            yield Static(self._hint_text(), id="history-hint", classes="history-hint")
            yield Input(placeholder="Buscar runs…", id="history-search")
            yield OptionList(id="history-options")
            yield Static("", id="history-empty", classes="history-empty")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()
        self.query_one("#history-search", Input).focus()

    def _hint_text(self) -> str:
        return "/ busca  ·  Enter abre  ·  d remove"

    def _refresh(self) -> None:
        items = self._catalog.search(self._query)
        self._items = {item.item_id: item for item in items}
        options = self.query_one("#history-options", OptionList)
        options.clear_options()
        empty = self.query_one("#history-empty", Static)
        hint = self.query_one("#history-hint", Static)
        hint.update(self._hint_text())
        if not items:
            empty.update("Nenhuma run encontrada")
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
        # Run que ainda está rodando no daemon abre ao vivo, não como página de
        # histórico: o id da run é o mesmo dos dois lados. Item `executando`
        # cujo daemon morreu não está nesta lista e cai no detalhe estático,
        # que é o que existe para ele.
        if item.status is HistoryStatus.IN_PROGRESS and item.run_id in active_run_ids():
            self.app.open_cockpit(
                item.workflow_id,
                item.prompt,
                attach_run_id=item.run_id,
                workspace=self._workspace,
            )
            return
        self.app.push_screen(HistoryDetailScreen(item, workspace=self._workspace))

    def action_back_home(self) -> None:
        self.app.pop_screen()

    def action_focus_search(self) -> None:
        self.query_one("#history-search", Input).focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "delete_run":
            return self._highlighted() is not None
        return True

    def action_delete_run(self) -> None:
        item = self._highlighted()
        if item is None:
            return

        def _answered(confirmed: bool | None) -> None:
            if not confirmed:
                return
            removed = self._catalog.delete(item.item_id)
            self._refresh()
            self.query_one("#history-options", OptionList).focus()
            if removed:
                self.notify(f"Run removida: {item.title}")
            else:
                # Sumiu entre a listagem e o Enter — dizer isso é melhor do que
                # deixar a linha piscar e voltar.
                self.notify("Essa run já não estava mais no histórico")

        self.app.push_screen(
            ConfirmScreen(
                title="REMOVER DO HISTÓRICO",
                detail=_delete_warning(item),
                confirm_label="Remover",
            ),
            callback=_answered,
        )

    def _highlighted(self) -> HistoryItem | None:
        """A run sob o cursor da lista, se houver lista e cursor."""
        try:
            options = self.query_one("#history-options", OptionList)
        except Exception:
            return None
        index = options.highlighted
        if index is None or not (0 <= index < options.option_count):
            return None
        option_id = options.get_option_at_index(index).id
        return self._items.get(str(option_id)) if option_id else None


def _delete_warning(item: HistoryItem) -> str:
    """O que a remoção leva junto — e o risco, quando a run ainda está viva.

    Run em andamento não é bloqueada de propósito: uma que ficou marcada como
    `executando` porque o processo morreu precisa poder sair daqui.
    """
    lines = [
        item.title,
        "Apaga a run, os logs e a lista de artefatos. Os arquivos no workspace ficam.",
    ]
    if item.status is HistoryStatus.IN_PROGRESS:
        lines.append("Atenção: esta run consta em andamento — remover pode derrubá-la.")
    return "\n".join(lines)


def _format_item(item: HistoryItem) -> Text:
    title = item.title.replace("\n", " ").strip() or item.workflow_id
    if len(title) > 48:
        title = title[:47] + "…"
    line = Text(f"{item.workflow_label[:12]:<12}  ")
    line.append(f"{item.status_label:<{LABEL_WIDTH}}", style=status_color(item.status))
    line.append(f"  {title}")
    return line
