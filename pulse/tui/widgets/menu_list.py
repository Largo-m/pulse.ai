from __future__ import annotations

from typing import TYPE_CHECKING

from textual import on
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from pulse.tui.menu_rows import MenuRow, label_width, menu_row

if TYPE_CHECKING:
    from typing import Unpack

    from pulse.tui.widgets.options import WidgetOptions


class MenuList(OptionList):
    """An option list of `MenuRow`s that marks the highlighted row with a `❯` pointer.

    The pointer replaces the highlight bar, as in agent CLI menus; the screens
    that use it style the bar away (`.option-list--option-highlighted`).
    """

    def __init__(self, **kwargs: Unpack[WidgetOptions]) -> None:
        super().__init__(**kwargs)
        self._rows: dict[str, MenuRow] = {}
        self._width = 0
        self._pointed: str | None = None

    @property
    def pointed(self) -> MenuRow | None:
        return self._rows.get(self._pointed or "")

    def show_rows(self, rows: list[MenuRow], *, focus: str | None = None) -> None:
        """Show `rows`, keeping the pointer where the user expects it.

        The pointer lands on `focus`, else on the row it was on (a redraw of
        the same menu), else on the current choice, else on the top.
        """
        ids = [row.id for row in rows]
        current = next((row.id for row in rows if row.current), None)
        pointed = next(
            (
                candidate
                for candidate in (focus, self._pointed, current)
                if candidate is not None and candidate in ids
            ),
            ids[0] if ids else None,
        )
        self._rows = {row.id: row for row in rows}
        self._width = label_width(rows)
        self._pointed = pointed
        self.clear_options()
        self.add_options(
            Option(menu_row(row, selected=row.id == pointed, width=self._width), id=row.id)
            for row in rows
        )
        if pointed is not None:
            self.highlighted = ids.index(pointed)

    @on(OptionList.OptionHighlighted)
    def _move_pointer(self, event: OptionList.OptionHighlighted) -> None:
        """Only the two rows that change are redrawn; the event still reaches the screen."""
        target = str(event.option_id) if event.option_id is not None else None
        if target == self._pointed:
            return
        for row_id, selected in ((self._pointed, False), (target, True)):
            row = self._rows.get(row_id or "")
            if row is not None:
                self.replace_option_prompt(
                    row.id, menu_row(row, selected=selected, width=self._width)
                )
        self._pointed = target
