from __future__ import annotations

import contextlib
from datetime import datetime
from functools import partial
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse.client.active_runs import active_run_ids
from pulse.domain.run import utc_now
from pulse.history.models import LIVE_STATUSES, HistoryItem
from pulse.tui import engine, strings
from pulse.tui.history_rows import history_row
from pulse.tui.key_hints import key_line
from pulse.tui.palette import LIME, TEXT_MUTED
from pulse.tui.screens.confirm import ConfirmScreen
from pulse.tui.screens.history_detail import HistoryDetailScreen
from pulse.tui.screens.navigation import pulse_app

REFRESH_SECONDS = 2.0


class HistoryListScreen(Screen[None]):
    BINDINGS = [
        ("q", "back_home", strings.BACK),
        ("b", "back_home", strings.BACK),
        ("escape", "back_home", strings.BACK),
        ("slash", "focus_search", strings.HISTORY_BINDING_SEARCH),
        ("/", "focus_search", strings.HISTORY_BINDING_SEARCH),
        ("d", "delete_run", strings.REMOVE),
        ("delete", "delete_run", strings.REMOVE),
        # The search box has no use for the arrows: they keep driving the list,
        # so filtering and picking never needs a focus switch.
        Binding("up", "cursor(-1)", show=False),
        Binding("down", "cursor(1)", show=False),
    ]

    def __init__(self, workspace: Path | None = None) -> None:
        super().__init__()
        self._workspace = workspace or Path.cwd()
        self._query = ""
        self._items: dict[str, HistoryItem] = {}
        self._now = utc_now()
        self._pointed: str | None = None
        self._generation = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="history-content"):
            yield Static(id="history-header")
            yield Input(placeholder=strings.HISTORY_SEARCH_PLACEHOLDER, id="history-search")
            yield OptionList(id="history-options")
            yield Static("", id="history-empty")
        yield Static(id="history-keys")

    def on_mount(self) -> None:
        self._refresh()
        self.query_one("#history-options", OptionList).focus()
        self.set_interval(REFRESH_SECONDS, self._poll)

    def on_screen_resume(self) -> None:
        self._refresh()

    def _poll(self) -> None:
        """Reload history off the screen loop so a busy database never blocks the UI."""
        fetch = partial(self._fetch, self._query, self._generation)
        self.run_worker(fetch, exclusive=True, thread=True)

    def _fetch(self, query: str, generation: int) -> None:
        try:
            items = engine.history(self._workspace, query)
        except engine.EngineError:
            # A busy daemon skips this poll; the next one retries.
            return
        # The app already exited while the poll was in flight.
        with contextlib.suppress(RuntimeError):
            self.app.call_from_thread(self._apply_poll, items, query, generation)

    def _apply_poll(self, items: list[HistoryItem], query: str, generation: int) -> None:
        if generation == self._generation:
            self._apply(items, query)

    def _refresh(self) -> None:
        self._generation += 1
        try:
            items = engine.history(self._workspace, self._query)
        except engine.EngineError as error:
            self.notify(error.describe())
            items = []
        self._apply(items, self._query, force=True)

    def _apply(self, items: list[HistoryItem], query: str, *, force: bool = False) -> None:
        """Show `items` in the list, redrawing only when a row changed.

        Always redrawing would reset the cursor every tick; results for a stale
        query are dropped.
        """
        if query != self._query or not self.is_mounted:
            return
        now = utc_now()
        rows = [_row_key(item, now) for item in items]
        unchanged = rows == [_row_key(item, self._now) for item in self._items.values()]
        selected = self._highlighted()
        self._items = {item.item_id: item for item in items}
        self._now = now
        if unchanged and not force:
            return
        self._show_header()
        options = self.query_one("#history-options", OptionList)
        options.clear_options()
        self._pointed = None
        options.display = bool(items)
        self._show_empty(not items)
        self._show_keys()
        if not items:
            return
        ids = [item.item_id for item in items]
        keep = selected.item_id if selected is not None and selected.item_id in ids else ids[0]
        options.add_options(
            Option(history_row(item, now=now, selected=item.item_id == keep), id=item.item_id)
            for item in items
        )
        self._pointed = keep
        options.highlighted = ids.index(keep)

    def _show_header(self) -> None:
        line = Text(strings.HISTORY_TITLE, style=f"bold {LIME}")
        # While searching the list holds matches, not the workspace's runs.
        if not self._query.strip():
            count = len(self._items)
            counted = (
                strings.HISTORY_COUNT_ONE
                if count == 1
                else strings.HISTORY_COUNT_MANY.format(count=count)
            )
            line.append(f"  ·  {counted}", style=TEXT_MUTED)
        line.append(f"  ·  {self._workspace.name}", style=TEXT_MUTED)
        self.query_one("#history-header", Static).update(line)

    def _show_empty(self, empty: bool) -> None:
        panel = self.query_one("#history-empty", Static)
        panel.display = empty
        if not empty:
            panel.update("")
            return
        if self._query.strip():
            headline = strings.HISTORY_NO_MATCH.format(query=self._query.strip())
            action = strings.HISTORY_NO_MATCH_ACTION
        else:
            headline, action = strings.HISTORY_EMPTY, strings.HISTORY_EMPTY_ACTION
        message = Text(headline)
        message.append(f"\n{action}", style=TEXT_MUTED)
        panel.update(message)

    def _show_keys(self) -> None:
        searching = isinstance(self.focused, Input)
        keys: tuple[tuple[str, str], ...]
        if not self._items:
            keys = strings.HISTORY_KEYS_SEARCH_EMPTY if searching else strings.HISTORY_KEYS_EMPTY
        elif searching:
            keys = strings.HISTORY_KEYS_SEARCH
        else:
            keys = strings.HISTORY_KEYS_LIST
        self.query_one("#history-keys", Static).update(key_line(keys))

    def on_descendant_focus(self) -> None:
        self._show_keys()

    @on(OptionList.OptionHighlighted, "#history-options")
    def on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Move the `❯` pointer: only the two rows that change are redrawn."""
        target = str(event.option_id) if event.option_id is not None else None
        if target == self._pointed:
            return
        options = self.query_one("#history-options", OptionList)
        for item_id, selected in ((self._pointed, False), (target, True)):
            item = self._items.get(item_id or "")
            if item is not None:
                options.replace_option_prompt(
                    item.item_id, history_row(item, now=self._now, selected=selected)
                )
        self._pointed = target

    @on(Input.Changed, "#history-search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._query = event.value
        self._refresh()

    @on(Input.Submitted, "#history-search")
    def on_search_submitted(self) -> None:
        """Enter in the search opens the run under the pointer, as agent CLI pickers do."""
        options = self.query_one("#history-options", OptionList)
        if options.highlighted is not None:
            options.action_select()

    @on(OptionList.OptionSelected, "#history-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option_id
        if option_id is None:
            return
        item = self._items.get(str(option_id))
        if item is None:
            return
        if item.status in LIVE_STATUSES and item.run_id in active_run_ids():
            pulse_app(self).open_cockpit(
                item.workflow_id,
                item.prompt,
                attach_run_id=item.run_id,
                workspace=self._workspace,
            )
            return
        self.app.push_screen(HistoryDetailScreen(item, workspace=self._workspace))

    def action_back_home(self) -> None:
        """Esc first leaves the search, so one key never both clears and exits."""
        search = self.query_one("#history-search", Input)
        if self.focused is search:
            if search.value:
                search.value = ""
            else:
                self.query_one("#history-options", OptionList).focus()
            return
        self.app.pop_screen()

    def action_focus_search(self) -> None:
        self.query_one("#history-search", Input).focus()

    def action_cursor(self, step: int) -> None:
        options = self.query_one("#history-options", OptionList)
        if step < 0:
            options.action_cursor_up()
        else:
            options.action_cursor_down()

    def check_action(self, action: str, _parameters: tuple[object, ...]) -> bool | None:
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
            try:
                removed = engine.delete_history_item(self._workspace, item.item_id)
            except engine.RunInUse:
                self.notify(strings.HISTORY_RUN_IN_USE)
                return
            except engine.EngineError as error:
                self.notify(error.describe())
                return
            self._refresh()
            self.query_one("#history-options", OptionList).focus()
            if removed:
                self.notify(strings.HISTORY_RUN_REMOVED.format(title=item.title))
            else:
                self.notify(strings.HISTORY_RUN_ALREADY_GONE)

        self.app.push_screen(
            ConfirmScreen(
                title=strings.CONFIRM_TITLE_REMOVE_FROM_HISTORY,
                detail=_delete_warning(item),
                confirm_label=strings.REMOVE,
            ),
            callback=_answered,
        )

    def _highlighted(self) -> HistoryItem | None:
        """The run under the list cursor, if any."""
        try:
            options = self.query_one("#history-options", OptionList)
        except NoMatches:
            return None
        index = options.highlighted
        if index is None or not (0 <= index < options.option_count):
            return None
        option_id = options.get_option_at_index(index).id
        return self._items.get(str(option_id)) if option_id else None


def _delete_warning(item: HistoryItem) -> str:
    """Describe what deletion removes, plus a warning when the run looks live.

    The screen does not block live-looking runs: one stuck as running after
    its process died must stay removable. Only the daemon knows which runs it
    still executes, and it refuses those.
    """
    lines = [
        item.title,
        strings.HISTORY_REMOVE_DETAIL,
    ]
    if item.status in LIVE_STATUSES:
        lines.append(strings.HISTORY_REMOVE_LIVE_WARNING)
    return "\n".join(lines)


def _row_key(item: HistoryItem, now: datetime) -> tuple[str, str]:
    """What a row displays; when this changes the list is redrawn."""
    return (item.item_id, history_row(item, now=now, selected=False).plain)
