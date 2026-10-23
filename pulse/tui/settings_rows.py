"""How a settings menu reads: a label column, its value, and a muted line of why.

Kept apart from the screen so a row is a pure function of its data, testable
without mounting Textual. The layout follows the `/config` and `/model` menus
of agent CLIs: a `❯` pointer instead of a highlight bar, the value aligned in
its own column, and the current choice marked with a check.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rich.text import Text

from pulse.tui import strings
from pulse.tui.palette import ACCENT_YELLOW, ERROR, LIME, TEXT, TEXT_MUTED

POINTER = "❯"
CURRENT = "✓"
VALUE_GAP = 3
INDENT = "    "


class Toggle(Enum):
    ON = "on"
    OFF = "off"
    UNAVAILABLE = "unavailable"


TOGGLE_ICONS = {Toggle.ON: "●", Toggle.OFF: "○", Toggle.UNAVAILABLE: "–"}
TOGGLE_LABELS = {
    Toggle.ON: strings.SETTINGS_TOGGLE_ON,
    Toggle.OFF: strings.SETTINGS_TOGGLE_OFF,
    Toggle.UNAVAILABLE: strings.SETTINGS_TOGGLE_UNAVAILABLE,
}


def toggle_state(enabled: bool, *, available: bool) -> Toggle:
    if not available:
        return Toggle.UNAVAILABLE
    return Toggle.ON if enabled else Toggle.OFF


def toggle_value(state: Toggle) -> Text:
    """Icon and word together, so the state never rests on color alone."""
    return Text(
        f"{TOGGLE_ICONS[state]} {TOGGLE_LABELS[state]}",
        style=LIME if state is Toggle.ON else TEXT_MUTED,
    )


@dataclass(frozen=True)
class SettingRow:
    """One line of a settings menu; `id` is the option id the screen routes on."""

    id: str
    label: str
    value: Text | str = ""
    description: str = ""
    current: bool = False
    muted: bool = False


def label_width(rows: list[SettingRow]) -> int:
    """The column every value starts at: the widest label that has a value."""
    return max((len(row.label) for row in rows if row.value), default=0)


def setting_row(row: SettingRow, *, selected: bool, width: int) -> Text:
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


class Tone(Enum):
    """How the feedback under the menu reads: a plain note, a done change or a failure."""

    NOTE = "note"
    DONE = "done"
    ERROR = "error"


TONE_STYLES = {Tone.NOTE: TEXT_MUTED, Tone.DONE: TEXT, Tone.ERROR: ERROR}


def feedback(text: str, tone: Tone) -> Text:
    # Plain text: daemon errors and check messages are not Rich markup.
    return Text(text, style=TONE_STYLES[tone])


CHECK_ICONS = {"ok": ("✓", LIME), "warn": ("!", ACCENT_YELLOW), "fail": ("✗", ERROR)}


def check_line(status: str, message: str) -> Text:
    """A doctor check as an icon and its message; an unknown status shows as itself."""
    icon, style = CHECK_ICONS.get(status, (status.upper(), TEXT_MUTED))
    line = Text(f"{icon} ", style=f"bold {style}")
    line.append(message, style=TEXT)
    return line


def breadcrumb(trail: tuple[str, ...], workspace: str) -> Text:
    """Where the menu is: the title, each level down, then the workspace it edits."""
    line = Text(strings.SETTINGS_TITLE, style=f"bold {LIME}")
    for index, level in enumerate(trail):
        line.append(" › ", style=TEXT_MUTED)
        line.append(level, style=TEXT if index == len(trail) - 1 else TEXT_MUTED)
    line.append(f"  ·  {workspace}", style=TEXT_MUTED)
    return line
