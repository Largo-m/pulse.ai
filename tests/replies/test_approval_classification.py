"""How the approval answers decide whether the next agent runs.

`classify_outcome` is the gate between steps: reading "adjust" as "approve", or
stopping at the first negative answer, would advance a run nobody approved.
"""

from __future__ import annotations

import pytest

from pulse.replies.approval import (
    SUMMARY_MAX_CHARS,
    ApprovalOutcome,
    answer_needs_description,
    chosen_options,
    classify_outcome,
    format_summary,
    is_positive,
    picked_answers,
)

TRUNCATED = "\n\n[… summary truncated …]"


def test_a_blank_summary_stays_blank():
    assert format_summary("  \n\t ") == ""


def test_a_summary_at_the_limit_is_kept_whole():
    text = "x" * SUMMARY_MAX_CHARS

    assert format_summary(f"  {text}\n") == text


def test_a_longer_summary_is_cut_at_the_limit_and_marked():
    head = "a" * (SUMMARY_MAX_CHARS - 1)

    assert format_summary(f"{head} {'b' * 10}") == head + TRUNCATED


def test_only_arrow_lines_are_answers_and_the_arrow_is_dropped():
    """An indented answer used to keep its arrow: only unindented lines were cleaned."""
    text = "Q1?\n  → Xamarin\n→\nnot an answer → here\n→ B) Ajustar"

    assert picked_answers(text) == ["Xamarin", "B) Ajustar"]


def test_free_text_is_skipped_but_later_choices_still_count():
    text = "→ Outro — skip the cache section\n→ A) Aprovar — looks good — ship it"

    assert chosen_options(text) == ["a) aprovar"]


@pytest.mark.parametrize(
    ("answers", "positive"),
    [
        ("→ Não aprovar ainda\n→ A) Aprovar", True),
        ("→ B) Ajustar", False),
        ("→ A) Aprovar", True),
        ("→ Not approved", False),
    ],
)
def test_a_negative_answer_does_not_hide_a_later_approval(answers: str, positive: bool):
    assert is_positive(answers) is positive


@pytest.mark.parametrize(
    ("answers", "outcome"),
    [
        ("no arrow at all", ApprovalOutcome.UNKNOWN),
        ("→ C) Cancelar workflow", ApprovalOutcome.CANCEL),
        ("→ D) Pular este step", ApprovalOutcome.SKIP),
        ("→ A) Sim, aprovar e continuar", ApprovalOutcome.APPROVE),
        ("→ B) Não, preciso de ajustes", ApprovalOutcome.ADJUST),
        ("→ B) Usar Postgres", ApprovalOutcome.CONTINUE),
        ("→ Outro — cancel nothing, just approve later", ApprovalOutcome.CONTINUE),
    ],
)
def test_each_answer_maps_to_one_outcome(answers: str, outcome: str):
    assert classify_outcome(answers) == outcome


def test_a_label_that_asks_for_text_opens_the_field_on_any_question():
    assert answer_needs_description(prompt="Which stack?", label="B) Other (descreva)") is True


@pytest.mark.parametrize(
    ("label", "needs"),
    [("A) Aprovar", False), ("C) Cancelar", False), ("B) Ajustar", True), ("B) Talvez", True)],
)
def test_on_an_approval_gate_only_a_non_decision_asks_what_to_change(label: str, needs: bool):
    assert answer_needs_description(prompt="Aprovar o PRD e avançar?", label=label) is needs


def test_outside_an_approval_gate_a_plain_choice_needs_no_text():
    assert answer_needs_description(prompt="Which stack?", label="B) Python") is False
