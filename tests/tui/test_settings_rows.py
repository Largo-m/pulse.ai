from __future__ import annotations

import pytest

from pulse.tui import strings
from pulse.tui.palette import ERROR, LIME, TEXT_MUTED
from pulse.tui.settings_rows import Toggle, Tone, check_line, feedback, toggle_state, toggle_value


@pytest.mark.parametrize(
    ("enabled", "available", "expected"),
    [
        (True, True, Toggle.ON),
        (False, True, Toggle.OFF),
        (True, False, Toggle.UNAVAILABLE),
        (False, False, Toggle.UNAVAILABLE),
    ],
)
def test_a_toggle_that_cannot_turn_on_reads_unavailable_whatever_its_flag(
    enabled: bool, available: bool, expected: Toggle
):
    """A stored `true` behind a missing prerequisite does nothing; saying `ligado` would lie."""
    assert toggle_state(enabled, available=available) is expected


def test_a_toggle_value_names_its_state_in_words_not_only_color():
    assert toggle_value(Toggle.ON).plain == f"● {strings.SETTINGS_TOGGLE_ON}"
    assert toggle_value(Toggle.OFF).plain == f"○ {strings.SETTINGS_TOGGLE_OFF}"
    assert toggle_value(Toggle.UNAVAILABLE).plain == f"– {strings.SETTINGS_TOGGLE_UNAVAILABLE}"
    assert toggle_value(Toggle.ON).style == LIME
    assert toggle_value(Toggle.OFF).style == TEXT_MUTED


@pytest.mark.parametrize(
    ("status", "icon", "color"),
    [("ok", "✓", LIME), ("fail", "✗", ERROR)],
)
def test_a_check_line_leads_with_the_icon_of_its_status(status: str, icon: str, color: str):
    line = check_line(status, "agent 1.0")

    assert line.plain == f"{icon} agent 1.0"
    assert line.style == f"bold {color}"


def test_a_check_with_an_unknown_status_shows_the_status_itself():
    """A new doctor status must stay visible rather than borrow another's icon."""
    assert check_line("skip", "no runtime").plain == "SKIP no runtime"


def test_feedback_keeps_markup_like_text_verbatim():
    """Daemon errors may contain brackets; they are text, never Rich markup."""
    shown = feedback("[bold]boom[/bold]", Tone.ERROR)

    assert shown.plain == "[bold]boom[/bold]"
    assert shown.style == ERROR
