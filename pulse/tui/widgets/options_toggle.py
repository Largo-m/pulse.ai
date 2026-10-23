from __future__ import annotations

from collections.abc import Iterable

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Static

from pulse.tui import strings
from pulse.tui.palette import BG_PANEL, LIME, TEXT, TEXT_MUTED

COLLAPSED = "▸"
EXPANDED = "▾"
CHIP_GAP = "   "


def key_chips(keys: Iterable[tuple[str, str]]) -> Text:
    """Keys as highlighted chips, each followed by its action: scanned, not read."""
    chips = Text()
    for index, (key, action) in enumerate(keys):
        if index:
            chips.append(CHIP_GAP)
        chips.append(f" {key} ", style=f"bold {LIME} on {BG_PANEL}")
        chips.append(f" {action}", style=TEXT_MUTED)
    return chips


class OptionsToggle(Static, can_focus=True):
    """Disclosure that shows or hides the detailed fields.

    A control rather than a sentence in the hint: it is reached with Tab and
    chosen with Enter, Space or a click, and names its own shortcut.
    """

    BINDINGS = [
        Binding("enter", "press", show=False),
        Binding("space", "press", show=False),
    ]

    class Pressed(Message):
        pass

    def show_state(self, *, expanded: bool) -> None:
        label = Text()
        label.append(f"{EXPANDED if expanded else COLLAPSED} ", style=LIME)
        label.append(
            strings.TASK_FEWER_OPTIONS if expanded else strings.TASK_MORE_OPTIONS,
            style=f"bold {TEXT}",
        )
        if not expanded:
            label.append(f"  {strings.TASK_MORE_OPTIONS_DETAIL}", style=TEXT_MUTED)
        label.append(CHIP_GAP)
        label.append(f" {strings.TASK_OPTIONS_SHORTCUT} ", style=f"bold {LIME} on {BG_PANEL}")
        self.update(label)

    def action_press(self) -> None:
        self.post_message(self.Pressed())

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.action_press()
