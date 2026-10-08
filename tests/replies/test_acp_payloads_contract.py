"""The exact contract of the ACP payload parsers.

ACP JSON is untrusted: a field Pulse cannot read must come out absent (and so
lead to asking a person), while a field the agent spelled either way ACP allows
must come through exactly, or the user answers a question the agent never asked.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pulse.domain import ui_text
from pulse.replies.acp_payloads import (
    AskQuestionRequest,
    PermissionOption,
    PermissionRequest,
    Question,
    QuestionAnswer,
    QuestionnaireMeta,
    QuestionOption,
    first_present,
    items_of,
    mapping_of,
    positive_int,
    text_of,
    truthy_text,
)

# --- scalar readers ---------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"a": 1}, {"a": 1}),
        ([("a", 1)], {}),
        ("text", {}),
        (None, {}),
    ],
)
def test_mapping_of_keeps_only_json_objects(value: object, expected: dict[str, object]) -> None:
    assert dict(mapping_of(value)) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([1, 2], [1, 2]),
        ((1, 2), [1, 2]),
        ("ab", []),
        ({"a": 1}, []),
        (None, []),
    ],
)
def test_items_of_keeps_only_json_arrays(value: object, expected: list[object]) -> None:
    """A string is iterable but is not a list of entries."""
    assert list(items_of(value)) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, ""), ("", ""), ("x", "x"), (0, "0"), (False, "False"), (3, "3")],
)
def test_text_of_reads_only_null_as_blank(value: object, expected: str) -> None:
    assert text_of(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, ""), ("", ""), (0, ""), (False, ""), ("x", "x"), (3, "3"), (True, "True")],
)
def test_truthy_text_reads_every_falsy_value_as_blank(value: object, expected: str) -> None:
    assert truthy_text(value) == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"a": 1, "b": 2}, 1),
        ({"b": 2}, 2),
        ({"a": None, "b": 2}, None),
        ({"c": 3}, None),
        ({}, None),
    ],
)
def test_first_present_returns_the_first_key_the_payload_has(
    payload: dict[str, object], expected: object
) -> None:
    """A key present with `null` still wins: presence, not truthiness, decides."""
    assert first_present(payload, "a", "b") == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, 1),
        (7, 7),
        (0, None),
        (-1, None),
        (True, None),
        (False, None),
        ("3", None),
        (2.0, None),
        (None, None),
    ],
)
def test_positive_int_accepts_only_integers_from_one(value: object, expected: int | None) -> None:
    assert positive_int(value) == expected


# --- AskQuestion ------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"id": "a", "label": "Alpha"}, QuestionOption(id="a", label="Alpha")),
        ({"label": "Alpha"}, QuestionOption(id="Alpha", label="Alpha")),
        ({"id": "a"}, QuestionOption(id="a", label="a")),
        ({"id": None, "label": "Alpha"}, QuestionOption(id="", label="Alpha")),
        ({"id": 2, "label": None}, QuestionOption(id="2", label="")),
        ({}, QuestionOption(id="", label="")),
    ],
)
def test_question_option_reads_id_and_label_with_each_as_the_others_fallback(
    raw: dict[str, object], expected: QuestionOption
) -> None:
    assert QuestionOption.parse(raw) == expected


@pytest.mark.parametrize("raw", ["a", 1, None, ["a", "b"]])
def test_question_option_that_is_not_an_object_is_dropped(raw: object) -> None:
    assert QuestionOption.parse(raw) is None


def test_question_reads_every_field_in_snake_case() -> None:
    raw = {
        "id": "q1",
        "prompt": "  Which stack?  ",
        "options": [{"id": "py", "label": "Python"}, "junk", {"id": "go", "label": "Go"}],
        "allow_multiple": True,
        "index": 2,
        "total_questions": 5,
    }

    assert Question.parse(raw) == Question(
        id="q1",
        prompt="Which stack?",
        options=(QuestionOption("py", "Python"), QuestionOption("go", "Go")),
        allow_multiple=True,
        index=2,
        total=5,
    )


def test_question_reads_every_field_in_camel_case() -> None:
    raw = {
        "id": "q1",
        "prompt": "Which stack?",
        "allowMultiple": True,
        "questionIndex": 3,
        "totalQuestions": 4,
    }

    assert Question.parse(raw) == Question(
        id="q1", prompt="Which stack?", options=None, allow_multiple=True, index=3, total=4
    )


def test_question_without_fields_is_a_blank_single_choice_free_text_question() -> None:
    assert Question.parse({}) == Question(
        id="", prompt="", options=None, allow_multiple=False, index=None, total=None
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"allow_multiple": False, "allowMultiple": True}, False),
        ({"allow_multiple": True, "allowMultiple": False}, True),
        ({"allowMultiple": 0}, False),
        ({"allowMultiple": "yes"}, True),
    ],
)
def test_question_snake_case_multi_select_flag_wins_over_camel_case(
    raw: dict[str, object], expected: bool
) -> None:
    assert Question.parse(raw).allow_multiple is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"index": 1, "questionIndex": 9}, 1),
        ({"questionIndex": 9}, 9),
        ({"index": 0}, None),
        ({"index": True}, None),
    ],
)
def test_question_index_prefers_index_and_rejects_non_counters(
    raw: dict[str, object], expected: int | None
) -> None:
    assert Question.parse(raw).index == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"totalQuestions": 2, "total_questions": 9}, 2),
        ({"total_questions": 9}, 9),
        ({"totalQuestions": -3}, None),
    ],
)
def test_question_total_prefers_camel_case_and_rejects_non_counters(
    raw: dict[str, object], expected: int | None
) -> None:
    assert Question.parse(raw).total == expected


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        (None, None),
        ([], None),
        ("A, B", None),
        (["junk", 3], ()),
        ([{"label": "Yes"}], (QuestionOption("Yes", "Yes"),)),
    ],
)
def test_question_options_distinguish_no_list_from_an_unreadable_list(
    options: object, expected: tuple[QuestionOption, ...] | None
) -> None:
    """No list means free text; a list Pulse cannot read means nothing to pick."""
    assert Question.parse({"options": options}).options == expected


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({}, QuestionnaireMeta(title="", total=None, index=None)),
        (
            {"title": "  Setup  ", "totalQuestions": 3, "questionIndex": 2},
            QuestionnaireMeta(title="Setup", total=3, index=2),
        ),
        (
            {"title": None, "total_questions": 4, "question_index": 1},
            QuestionnaireMeta(title="", total=4, index=1),
        ),
        (
            {"totalQuestions": 3, "total_questions": 8, "questionIndex": 2, "question_index": 7},
            QuestionnaireMeta(title="", total=3, index=2),
        ),
        (
            {"totalQuestions": 0, "questionIndex": False},
            QuestionnaireMeta(title="", total=None, index=None),
        ),
    ],
)
def test_questionnaire_meta_reads_title_and_counters_in_both_spellings(
    params: dict[str, object], expected: QuestionnaireMeta
) -> None:
    assert QuestionnaireMeta.parse(params) == expected


def test_questionnaire_meta_defaults_are_blank() -> None:
    assert QuestionnaireMeta() == QuestionnaireMeta(title="", total=None, index=None)


def test_ask_question_request_keeps_only_object_questions_in_order() -> None:
    params = {
        "title": "Setup",
        "totalQuestions": 2,
        "questions": [
            {"id": "q1", "prompt": "First?"},
            "not a question",
            None,
            {"id": "q2", "prompt": "Second?", "options": [{"id": "y", "label": "Yes"}]},
        ],
    }

    assert AskQuestionRequest.parse(params) == AskQuestionRequest(
        questions=(
            Question(id="q1", prompt="First?"),
            Question(id="q2", prompt="Second?", options=(QuestionOption("y", "Yes"),)),
        ),
        meta=QuestionnaireMeta(title="Setup", total=2, index=None),
    )


@pytest.mark.parametrize("questions", [None, "q1", {"id": "q1"}, []])
def test_ask_question_request_without_a_question_list_has_no_questions(
    questions: object,
) -> None:
    assert AskQuestionRequest.parse({"questions": questions}).questions == ()


@pytest.mark.parametrize(
    ("answer", "wire"),
    [
        (
            QuestionAnswer("q1", ("a", "b")),
            {"questionId": "q1", "selectedOptionIds": ["a", "b"]},
        ),
        (QuestionAnswer("q2", ()), {"questionId": "q2", "selectedOptionIds": []}),
    ],
)
def test_question_answer_goes_on_the_wire_in_acp_camel_case(
    answer: QuestionAnswer, wire: dict[str, object]
) -> None:
    assert answer.to_wire() == wire


# --- session/request_permission ---------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            {
                "optionId": "ok",
                "id": "other",
                "kind": "allow_once",
                "name": " Allow ",
                "label": "L",
            },
            PermissionOption(option_id="ok", choice_id="ok", kind="allow_once", name="Allow"),
        ),
        (
            {"id": "alt", "kind": "reject_once", "label": "  Deny  "},
            PermissionOption(option_id="", choice_id="alt", kind="reject_once", name="Deny"),
        ),
        (
            {"optionId": "", "id": "alt", "name": "", "label": "Fallback"},
            PermissionOption(option_id="", choice_id="alt", kind="", name="Fallback"),
        ),
        ({}, PermissionOption(option_id="", choice_id="", kind="", name="")),
        (
            {"optionId": 0, "kind": None, "name": 0},
            PermissionOption(option_id="0", choice_id="", kind="", name=""),
        ),
    ],
)
def test_permission_option_reads_acp_and_non_standard_spellings(
    raw: dict[str, object], expected: PermissionOption
) -> None:
    """Only `optionId` is the id policy may pick; `id` is only for a person's choice."""
    assert PermissionOption.parse(raw) == expected


@pytest.mark.parametrize("raw", ["allow", None, 1, ["optionId", "ok"]])
def test_permission_option_that_is_not_an_object_is_dropped(raw: object) -> None:
    assert PermissionOption.parse(raw) is None


@pytest.mark.parametrize(
    ("name", "kind", "expected"),
    [
        ("Run it", "allow_once", "Run it"),
        ("", "allow_once", ui_text.PERMISSION_KIND_LABELS["allow_once"]),
        ("", "ALLOW-ALWAYS", ui_text.PERMISSION_KIND_LABELS["allow_always"]),
        ("", "Reject-Once", ui_text.PERMISSION_KIND_LABELS["reject_once"]),
        ("", "reject_always", ui_text.PERMISSION_KIND_LABELS["reject_always"]),
        ("", "Edit-File_Now", "edit file now"),
        ("", "_trim_", "trim"),
        ("", "", ui_text.OPTION_FALLBACK),
        ("", "_", ui_text.OPTION_FALLBACK),
        ("", "--", ui_text.OPTION_FALLBACK),
    ],
)
def test_permission_option_label_falls_back_from_name_to_kind_to_a_generic_label(
    name: str, kind: str, expected: str
) -> None:
    option = PermissionOption(option_id="x", choice_id="x", kind=kind, name=name)

    assert option.label() == expected


def test_permission_request_reads_kind_texts_and_options() -> None:
    params = {
        "permission": {"kind": "EDIT", "title": "  Edit file  ", "description": "  a.py  "},
        "toolCall": {"kind": "execute", "title": "  Write a.py  "},
        "options": [{"optionId": "ok", "kind": "allow_once", "name": "Allow"}, "junk", 3],
    }

    assert PermissionRequest.parse(params) == PermissionRequest(
        kind="edit",
        options=(PermissionOption("ok", "ok", "allow_once", "Allow"),),
        title="Edit file",
        description="a.py",
        tool_title="Write a.py",
    )


@pytest.mark.parametrize(
    ("params", "expected_kind"),
    [
        ({"toolCall": {"kind": "Execute"}}, "execute"),
        ({"permission": {"kind": ""}, "toolCall": {"kind": "READ"}}, "read"),
        ({"permission": {"kind": None}, "toolCall": {"kind": "Fetch"}}, "fetch"),
        ({"permission": "edit", "toolCall": ["kind", "edit"]}, ""),
        ({}, ""),
    ],
)
def test_permission_request_kind_falls_back_to_the_tool_call_lowercased(
    params: dict[str, object], expected_kind: str
) -> None:
    assert PermissionRequest.parse(params).kind == expected_kind


def test_permission_request_with_nothing_readable_is_blank() -> None:
    params = {"permission": {"title": 0, "description": None}, "toolCall": {"title": ""}}

    assert PermissionRequest.parse(params) == PermissionRequest(
        kind="", options=(), title="", description="", tool_title=""
    )


_TEXT = st.text(max_size=12)


@given(option_id=_TEXT, label=_TEXT)
def test_any_option_with_both_fields_keeps_them_verbatim(option_id: str, label: str) -> None:
    raw: Mapping[str, object] = {"id": option_id, "label": label}

    assert QuestionOption.parse(raw) == QuestionOption(id=option_id, label=label)


@given(title=_TEXT, description=_TEXT)
def test_any_permission_texts_come_through_stripped(title: str, description: str) -> None:
    params = {"permission": {"title": title, "description": description}}

    parsed = PermissionRequest.parse(params)

    assert (parsed.title, parsed.description) == (title.strip(), description.strip())
