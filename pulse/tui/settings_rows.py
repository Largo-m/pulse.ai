"""What only the settings menu shows: toggle states, feedback tones and doctor checks."""

from __future__ import annotations

from enum import Enum

from rich.text import Text

from pulse.tui import strings
from pulse.tui.palette import ACCENT_YELLOW, ERROR, LIME, TEXT, TEXT_MUTED


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
