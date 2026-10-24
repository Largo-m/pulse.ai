from __future__ import annotations

from rich.text import Text

from pulse.tui.palette import LIME, TEXT_MUTED


def key_line(keys: tuple[tuple[str, str], ...]) -> Text:
    """The bottom line of a picker: each key in lime, what it does muted."""
    line = Text()
    for index, (key, label) in enumerate(keys):
        if index:
            line.append("  ·  ", style=TEXT_MUTED)
        line.append(key, style=LIME)
        line.append(f" {label}", style=TEXT_MUTED)
    return line
