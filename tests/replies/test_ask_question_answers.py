"""How an `AskQuestion` is shown and how its answer goes back to the agent.

The dock and the history log both name answers through these helpers, and the
reply shape is the ACP contract: a wrong key or a missing option means the
agent reads an answer the user never gave.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pulse.replies import wording
from pulse.replies.acp_payloads import (
    Question,
    QuestionAnswer,
    QuestionnaireMeta,
    QuestionOption,
)
from pulse.replies.ask_question import (
    OTHER_OPTION_ID,
    PLAN_PREVIEW_CHARS,
    build_ask_question_answers,
    build_ask_question_cancelled,
    build_question_choices,
    format_option_label,
    is_approval_prompt,
    is_free_text_answer,
    is_other_option,
    multi_select_prompt,
    option_requires_description,
    plan_prompt_text,
    resolve_question_progress,
    should_add_other_option,
)

_OTHER = wording.OTHER_DESCRIBE_OPTION

# --- reply payloads ---------------------------------------------------------


def test_answers_reply_lists_every_answer_in_order() -> None:
    answers = [QuestionAnswer("q1", ("a",)), QuestionAnswer("q2", ("b", "c"))]

    assert build_ask_question_answers(answers) == {
        "outcome": {
            "outcome": "answered",
            "answers": [
                {"questionId": "q1", "selectedOptionIds": ["a"]},
                {"questionId": "q2", "selectedOptionIds": ["b", "c"]},
            ],
        }
    }


def test_answers_reply_without_answers_is_still_answered() -> None:
    assert build_ask_question_answers([]) == {"outcome": {"outcome": "answered", "answers": []}}


def test_cancelled_reply_carries_only_the_cancelled_outcome() -> None:
    assert build_ask_question_cancelled() == {"outcome": {"outcome": "cancelled"}}


# --- progress counter -------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "position", "batch_size", "meta", "expected"),
    [
        (Question("q", "?"), 1, 1, QuestionnaireMeta(), (None, None)),
        (Question("q", "?"), 2, 3, QuestionnaireMeta(), (2, 3)),
        (Question("q", "?"), 1, 2, QuestionnaireMeta(), (1, 2)),
        (Question("q", "?"), 1, 1, QuestionnaireMeta(total=5, index=4), (4, 5)),
        (Question("q", "?"), 2, 3, QuestionnaireMeta(total=5, index=4), (4, 5)),
        (Question("q", "?", index=2, total=7), 1, 3, QuestionnaireMeta(total=5, index=4), (2, 7)),
        (Question("q", "?", index=2), 1, 1, QuestionnaireMeta(total=5), (2, 5)),
        (Question("q", "?", total=6), 3, 4, QuestionnaireMeta(), (3, 6)),
    ],
)
def test_progress_prefers_the_question_then_the_questionnaire_then_the_batch(
    question: Question,
    position: int,
    batch_size: int,
    meta: QuestionnaireMeta,
    expected: tuple[int | None, int | None],
) -> None:
    """A lone question with no counters shows none; a batch counts its own positions."""
    assert (
        resolve_question_progress(
            question=question, position=position, batch_size=batch_size, meta=meta
        )
        == expected
    )


# --- option labels ----------------------------------------------------------


@pytest.mark.parametrize(
    ("index", "label", "expected"),
    [
        (0, "Python", "A) Python"),
        (1, "  Go  ", "B) Go"),
        (25, "Last letter", "Z) Last letter"),
        (26, "Past the alphabet", "27) Past the alphabet"),
        (0, "A) Already lettered", "A) Already lettered"),
        (0, "  a) lower case letter  ", "a) lower case letter"),
        (1, "A) Wrong letter", "B) A) Wrong letter"),
        (0, "A Python", "A) A Python"),
        (26, "27) numbered", "27) numbered"),
    ],
)
def test_option_label_gets_its_letter_once(index: int, label: str, expected: str) -> None:
    assert format_option_label(index, label) == expected


@pytest.mark.parametrize(
    ("option_id", "label", "expected"),
    [
        ("outro", "", True),
        ("  OTHER ", "", True),
        ("__other__", "", True),
        ("__OTHER__", "Anything", True),
        ("x", "Outro (descreva)", True),
        ("x", "other", True),
        ("x", "  Other  ", True),
        ("x", "B) Outro", True),
        ("x", "e)  other thing", True),
        ("x", "Other(please say)", True),
        ("x", "Otherwise", False),
        ("x", "Another", False),
        ("x", "Outros", False),
        ("x", "Python", False),
        ("x", "", False),
        ("others", "", False),
    ],
)
def test_other_option_is_recognized_by_id_or_label(
    option_id: str, label: str, expected: bool
) -> None:
    assert is_other_option(option_id, label) is expected


def test_other_option_label_defaults_to_blank() -> None:
    assert is_other_option("x") is False


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Other (describe)", True),
        ("Outro (descreva)", True),
        ("Outra [especifique]", True),
        ("Custom — explain", True),
        ("Custom – detalhe", True),
        ("Custom -- specify", True),
        ("Custom: elaborate", True),
        ("Por favor, descreva:", True),
        ("Please informe:", True),
        ("Describe the bug", False),
        ("Explain:", True),
        ("Explanation", False),
        ("Python", False),
        ("Ends with colon:", False),
    ],
)
def test_option_requires_description_only_when_a_free_text_verb_is_asked_for(
    label: str, expected: bool
) -> None:
    assert option_requires_description(label) is expected


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Aprovar o plano?", True),
        ("Do you APPROVE this plan?", True),
        ("Aprovado?", False),
        ("Approved already", False),
        ("Which stack?", False),
    ],
)
def test_approval_prompt_needs_the_whole_word(prompt: str, expected: bool) -> None:
    assert is_approval_prompt(prompt) is expected


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Outro — my own answer", True),
        ("  outro — lower case", True),
        ("OUTRO —x", True),
        ("Outro", False),
        ("Outro - hyphen", False),
        ("A) Python", False),
    ],
)
def test_free_text_answer_starts_with_the_other_prefix(answer: str, expected: bool) -> None:
    assert is_free_text_answer(answer) is expected


def test_multi_select_prompt_adds_the_hint_on_its_own_line() -> None:
    assert multi_select_prompt("Pick stacks") == f"Pick stacks\n{wording.MULTI_SELECT_HINT}"


# --- the implicit "Other" option --------------------------------------------


@pytest.mark.parametrize(
    "labels",
    [
        ["Python", "Outro"],
        ["Python", "Cancelar"],
        ["Python", "CANCEL run"],
        ["Aprovar", "Ajustar"],
        ["Approve", "Adjust"],
        ["Python", "approval needed"],
    ],
)
def test_other_option_is_not_added_beside_other_cancel_or_approve(labels: list[str]) -> None:
    assert should_add_other_option(prompt="Which one?", option_labels=labels) is False


@pytest.mark.parametrize(
    "prompt",
    [
        "Revisar E AVANÇAR?",
        "Como deseja prosseguir agora?",
        "O app funciona como esperado?",
        "Funciona ou não funciona (descreva o erro)?",
    ],
)
def test_other_option_is_not_added_to_a_closed_prompt(prompt: str) -> None:
    assert should_add_other_option(prompt=prompt, option_labels=["Sim", "Não"]) is False


@pytest.mark.parametrize(
    ("prompt", "labels"),
    [
        ("Which stack?", ["Python", "Go"]),
        ("Avançar?", ["Sim", "Ajustar"]),
        ("", []),
    ],
)
def test_other_option_is_added_to_an_open_question(prompt: str, labels: list[str]) -> None:
    assert should_add_other_option(prompt=prompt, option_labels=labels) is True


def test_choices_letter_options_and_append_other_to_an_open_question() -> None:
    options = [QuestionOption("py", "Python"), QuestionOption("go", "Go")]

    assert build_question_choices(options, prompt="Which stack?") == [
        ("py", "A) Python"),
        ("go", "B) Go"),
        (OTHER_OPTION_ID, f"C) {_OTHER}"),
    ]


def test_choices_without_a_prompt_still_offer_other() -> None:
    assert build_question_choices([QuestionOption("y", "Yes")]) == [
        ("y", "A) Yes"),
        (OTHER_OPTION_ID, f"B) {_OTHER}"),
    ]


def test_choices_replace_the_agents_other_option_in_place() -> None:
    options = [
        QuestionOption("py", "Python"),
        QuestionOption("x", "Outro (qual?)"),
        QuestionOption("go", "Go"),
    ]

    assert build_question_choices(options, prompt="Which stack?") == [
        ("py", "A) Python"),
        (OTHER_OPTION_ID, f"B) {_OTHER}"),
        ("go", "C) Go"),
    ]


def test_choices_keep_an_other_id_whose_label_does_not_say_other() -> None:
    options = [QuestionOption("other", "Something else"), QuestionOption("go", "Go")]

    assert build_question_choices(options, prompt="Which stack?") == [
        (OTHER_OPTION_ID, f"A) {_OTHER}"),
        ("go", "B) Go"),
    ]


def test_choices_for_a_closed_question_add_nothing() -> None:
    options = [QuestionOption("ok", "Aprovar"), QuestionOption("fix", "Ajustar")]

    assert build_question_choices(options, prompt="Aprovar o plano?") == [
        ("ok", "A) Aprovar"),
        ("fix", "B) Ajustar"),
    ]


def test_choices_without_options_are_empty() -> None:
    """No options is a free-text question: an `Other` alone would be a fake choice."""
    assert build_question_choices([], prompt="Which stack?") == []


@given(labels=st.lists(st.sampled_from(["Python", "Go", "Rust", "Java"]), max_size=5))
def test_choices_keep_every_ordinary_option_in_order(labels: list[str]) -> None:
    options = [QuestionOption(f"id{index}", label) for index, label in enumerate(labels)]

    choices = build_question_choices(options, prompt="Which stack?")

    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    expected = [(f"id{index}", f"{letters[index]}) {label}") for index, label in enumerate(labels)]
    if labels:
        expected.append((OTHER_OPTION_ID, f"{letters[len(labels)]}) {_OTHER}"))
    assert choices == expected


# --- plan approval ----------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        (
            {"name": "  Refactor  ", "overview": "  Split modules  ", "plan": "  1. a\n2. b  "},
            "Refactor\nSplit modules\n\n1. a\n2. b",
        ),
        ({"name": "Refactor"}, "Refactor"),
        ({"name": "Refactor", "plan": "Steps"}, "Refactor\n\nSteps"),
        ({"name": "Refactor", "overview": "Why"}, "Refactor\nWhy"),
        ({}, wording.PLAN_FALLBACK_NAME),
        ({"name": "", "overview": None, "plan": 0}, wording.PLAN_FALLBACK_NAME),
        ({"name": "   "}, ""),
        ({"overview": "   ", "plan": "  "}, wording.PLAN_FALLBACK_NAME),
    ],
)
def test_plan_prompt_shows_name_overview_and_plan(params: dict[str, object], expected: str) -> None:
    assert plan_prompt_text(params) == expected


def test_plan_prompt_truncates_the_plan_to_the_preview_size() -> None:
    plan = "x" * PLAN_PREVIEW_CHARS + "TAIL"

    assert plan_prompt_text({"name": "P", "plan": plan}) == "P\n\n" + "x" * 1200


def test_plan_prompt_keeps_a_plan_that_fits_the_preview() -> None:
    plan = "y" * 1199 + "Z"

    assert plan_prompt_text({"name": "P", "plan": plan}) == f"P\n\n{plan}"
