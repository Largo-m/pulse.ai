from __future__ import annotations

import pytest
from rich.text import Text

from pulse.tui import strings
from pulse.tui.palette import ERROR, LIME, TEXT_MUTED
from pulse.tui.settings_rows import (
    CURRENT,
    POINTER,
    SettingRow,
    Toggle,
    Tone,
    breadcrumb,
    check_line,
    feedback,
    label_width,
    setting_row,
    toggle_state,
    toggle_value,
)


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


def test_values_start_in_one_column_measured_by_the_labels_that_have_a_value():
    """A long label without a value (an action row) must not push every value right."""
    rows = [
        SettingRow("a", "Runtime", "cursor"),
        SettingRow("b", "Permissões", "ask"),
        SettingRow("c", "Verificar ambiente"),
    ]
    width = label_width(rows)

    lines = [setting_row(row, selected=False, width=width).plain for row in rows[:2]]

    assert width == len("Permissões")
    assert [line.index(value) for line, value in zip(lines, ["cursor", "ask"], strict=True)] == [
        2 + width + 3,
        2 + width + 3,
    ]


def test_only_the_selected_row_carries_the_pointer():
    row = SettingRow("a", "Modelo", "opus")

    assert setting_row(row, selected=True, width=6).plain.startswith(f"{POINTER} Modelo")
    assert setting_row(row, selected=False, width=6).plain.startswith("  Modelo")


def test_the_current_choice_is_marked_with_a_check_and_others_are_not():
    current = setting_row(SettingRow("m", "opus", current=True), selected=False, width=0)
    other = setting_row(SettingRow("m", "sonnet"), selected=False, width=0)

    assert current.plain == f"  opus  {CURRENT}"
    assert CURRENT not in other.plain


def test_a_description_sits_indented_under_its_label_with_a_gap_after():
    row = SettingRow("w", "Worktree", "x", "Isola cada run")

    assert setting_row(row, selected=False, width=8).plain.split("\n") == [
        "  Worktree   x",
        "    Isola cada run",
        "",
    ]


def test_a_bare_pick_row_is_a_single_line():
    assert "\n" not in setting_row(SettingRow("m", "opus"), selected=True, width=0).plain


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


def test_the_breadcrumb_names_every_level_down_to_the_workspace():
    line = breadcrumb(("Por agent", "Review", "Modelo"), "pulse.ai")

    assert line.plain == f"{strings.SETTINGS_TITLE} › Por agent › Review › Modelo  ·  pulse.ai"


def test_the_root_breadcrumb_is_the_title_and_the_workspace():
    assert breadcrumb((), "pulse.ai").plain == f"{strings.SETTINGS_TITLE}  ·  pulse.ai"


def test_a_value_given_as_text_keeps_its_own_style():
    value = Text("● ligado", style=LIME)
    line = setting_row(SettingRow("w", "Worktree", value), selected=False, width=8)

    spans = [span for span in line.spans if line.plain[span.start : span.end] == "● ligado"]
    assert [span.style for span in spans] == [LIME]
