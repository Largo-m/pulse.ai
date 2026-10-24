"""How a menu row reads: a `❯` pointer, a label column, its value, a muted line of why.

Kept apart from the screens so a row is a pure function of its data, testable
without mounting Textual. The layout follows the `/config` and `/model` menus
of agent CLIs: a pointer instead of a highlight bar, the value aligned in its
own column, and the current choice marked with a check.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text

from pulse.tui.palette import LIME, TEXT, TEXT_MUTED

POINTER = "❯"
CURRENT = "✓"
VALUE_GAP = 3
INDENT = "    "


@dataclass(frozen=True)
class MenuRow:
    """One line of a menu; `id` is the option id the screen routes on."""

    id: str
    label: str
    value: Text | str = ""
    description: str = ""
    current: bool = False
    muted: bool = False


def label_width(rows: list[MenuRow]) -> int:
    """The column every value starts at: the widest label that has a value."""
    return max((len(row.label) for row in rows if row.value), default=0)


def menu_row(row: MenuRow, *, selected: bool, width: int) -> Text:
    """The pointer and a lime label mark the selected row; `✓` marks the current choice."""
    line = Text(no_wrap=True, overflow="ellipsis")
    line.append(f"{POINTER} " if selected else "  ", style=f"bold {LIME}")
    label_style = f"bold {LIME}" if selected else (TEXT_MUTED if row.muted else TEXT)
    line.append(row.label, style=label_style)
    if row.value:
        line.append(" " * (width - len(row.label) + VALUE_GAP))
        value = row.value if isinstance(row.value, Text) else Text(row.value, style=TEXT_MUTED)
        line.append_text(value)
    if row.current:
        line.append(f"  {CURRENT}", style=f"bold {LIME}")
    if row.description:
        # The blank line keeps described rows apart; bare pick lists stay dense.
        line.append(f"\n{INDENT}{row.description}\n", style=TEXT_MUTED)
    return line


def breadcrumb(title: str, trail: tuple[str, ...], workspace: str) -> Text:
    """Where the menu is: the title, each level down, then the workspace it edits."""
    line = Text(title, style=f"bold {LIME}")
    for index, level in enumerate(trail):
        line.append(" › ", style=TEXT_MUTED)
        line.append(level, style=TEXT if index == len(trail) - 1 else TEXT_MUTED)
    line.append(f"  ·  {workspace}", style=TEXT_MUTED)
    return line
