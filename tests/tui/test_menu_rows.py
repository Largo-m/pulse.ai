from __future__ import annotations

from rich.text import Text

from pulse.tui.menu_rows import CURRENT, POINTER, MenuRow, breadcrumb, label_width, menu_row
from pulse.tui.palette import LIME


def test_values_start_in_one_column_measured_by_the_labels_that_have_a_value():
    """A long label without a value (an action row) must not push every value right."""
    rows = [
        MenuRow("a", "Runtime", "cursor"),
        MenuRow("b", "Permissões", "ask"),
        MenuRow("c", "Verificar ambiente"),
    ]
    width = label_width(rows)

    lines = [menu_row(row, selected=False, width=width).plain for row in rows[:2]]

    assert width == len("Permissões")
    assert [line.index(value) for line, value in zip(lines, ["cursor", "ask"], strict=True)] == [
        2 + width + 3,
        2 + width + 3,
    ]


def test_only_the_selected_row_carries_the_pointer():
    row = MenuRow("a", "Modelo", "opus")

    assert menu_row(row, selected=True, width=6).plain.startswith(f"{POINTER} Modelo")
    assert menu_row(row, selected=False, width=6).plain.startswith("  Modelo")


def test_the_current_choice_is_marked_with_a_check_and_others_are_not():
    current = menu_row(MenuRow("m", "opus", current=True), selected=False, width=0)
    other = menu_row(MenuRow("m", "sonnet"), selected=False, width=0)

    assert current.plain == f"  opus  {CURRENT}"
    assert CURRENT not in other.plain


def test_a_description_sits_indented_under_its_label_with_a_gap_after():
    row = MenuRow("w", "Worktree", "x", "Isola cada run")

    assert menu_row(row, selected=False, width=8).plain.split("\n") == [
        "  Worktree   x",
        "    Isola cada run",
        "",
    ]


def test_a_bare_pick_row_is_a_single_line():
    assert "\n" not in menu_row(MenuRow("m", "opus"), selected=True, width=0).plain


def test_the_breadcrumb_names_every_level_down_to_the_workspace():
    line = breadcrumb("Configurações", ("Por agent", "Review", "Modelo"), "pulse.ai")

    assert line.plain == "Configurações › Por agent › Review › Modelo  ·  pulse.ai"


def test_the_root_breadcrumb_is_the_title_and_the_workspace():
    assert breadcrumb("Nova sessão", (), "pulse.ai").plain == "Nova sessão  ·  pulse.ai"


def test_a_value_given_as_text_keeps_its_own_style():
    value = Text("● ligado", style=LIME)
    line = menu_row(MenuRow("w", "Worktree", value), selected=False, width=8)

    spans = [span for span in line.spans if line.plain[span.start : span.end] == "● ligado"]
    assert [span.style for span in spans] == [LIME]
