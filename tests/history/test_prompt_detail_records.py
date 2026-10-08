"""The question / answer bubbles rebuilt from a logged prompt-port call.

The history screen only has the raw call (`name`, arguments, result), so these
pairs must name the answer exactly as the live dock showed it.
"""

from __future__ import annotations

from pulse.domain import ui_text
from pulse.history.prompt_detail import CANCELLED, EMPTY, build_prompt_qa
from pulse.replies.text_questionnaire import TextQuestion, TextQuestionnaire

ASK = "respond_to_ask_question"


def _answered(*pairs: tuple[str, list[object]]) -> dict[str, object]:
    return {
        "outcome": {
            "outcome": "answered",
            "answers": [{"questionId": qid, "selectedOptionIds": ids} for qid, ids in pairs],
        }
    }


def _stack(**extra: object) -> dict[str, object]:
    return {
        "id": "stack",
        "prompt": "Qual stack?",
        "options": [{"id": "py", "label": "Python"}, {"id": "go", "label": "Go"}],
        **extra,
    }


def test_an_unknown_call_is_not_a_question():
    assert build_prompt_qa("respond_to_anything", ({},), {}, None) == []


# --- AskQuestion --------------------------------------------------------------


def test_ask_question_names_the_picked_option_with_its_letter():
    params = {"questions": [_stack()]}
    assert build_prompt_qa(ASK, (params,), {}, _answered(("stack", ["go"]))) == [
        ("Qual stack?", "B) Go")
    ]


def test_ask_question_params_may_come_as_a_keyword():
    params = {"questions": [_stack()]}
    result = _answered(("stack", ["py"]))
    assert build_prompt_qa(ASK, (), {"params": params}, result) == [("Qual stack?", "A) Python")]


def test_ask_question_without_readable_params_or_questions_is_not_a_question():
    assert build_prompt_qa(ASK, ("not a mapping",), {}, None) == []
    assert build_prompt_qa(ASK, ({"questions": []},), {}, None) == []


def test_multi_select_shows_the_hint_and_joins_every_label():
    params = {"questions": [_stack(allowMultiple=True)]}
    result = _answered(("stack", ["py", "go"]))
    assert build_prompt_qa(ASK, (params,), {}, result) == [
        (f"Qual stack?\n{ui_text.MULTI_SELECT_HINT}", "A) Python, B) Go")
    ]


def test_a_detail_after_the_separator_is_shown_after_the_label():
    params = {"questions": [_stack()]}
    result = _answered(("stack", ["go::  com generics  "]))
    assert build_prompt_qa(ASK, (params,), {}, result) == [("Qual stack?", "B) Go — com generics")]


def test_a_blank_detail_shows_only_the_label():
    params = {"questions": [_stack()]}
    result = _answered(("stack", ["go::   "]))
    assert build_prompt_qa(ASK, (params,), {}, result) == [("Qual stack?", "B) Go")]


def test_free_text_answers_are_shown_as_typed():
    params = {"questions": [{"id": "name", "prompt": "Nome?"}]}
    result = _answered(("name", ["  pulse  "]))
    assert build_prompt_qa(ASK, (params,), {}, result) == [("Nome?", "pulse")]


def test_an_empty_selection_shows_a_dash():
    params = {"questions": [_stack()]}
    assert build_prompt_qa(ASK, (params,), {}, _answered(("stack", ["  "]))) == [
        ("Qual stack?", EMPTY)
    ]


def test_a_cancelled_answer_marks_the_first_question_and_stops():
    """Later questions were never shown, so the history must not invent them."""
    params = {"questions": [_stack(), {"id": "name", "prompt": "Nome?"}]}
    result = {"outcome": {"outcome": "cancelled"}}
    assert build_prompt_qa(ASK, (params,), {}, result) == [("Qual stack?", CANCELLED)]


def test_a_result_without_an_outcome_reads_as_cancelled():
    params = {"questions": [_stack()]}
    assert build_prompt_qa(ASK, (params,), {}, "garbage") == [("Qual stack?", CANCELLED)]


def test_questions_without_a_prompt_are_skipped():
    params = {"questions": [{"id": "blank", "prompt": "  "}, _stack()]}
    result = _answered(("blank", ["x"]), ("stack", ["py"]))
    assert build_prompt_qa(ASK, (params,), {}, result) == [("Qual stack?", "A) Python")]


def test_answers_without_a_matching_id_are_matched_by_position():
    params = {"questions": [{"prompt": "Primeira?"}, {"id": "q2", "prompt": "Segunda?"}]}
    result = _answered(("other", ["um"]), ("unknown", ["dois"]))
    assert build_prompt_qa(ASK, (params,), {}, result) == [
        ("Primeira?", "um"),
        ("Segunda?", "dois"),
    ]


def test_an_answer_without_a_selection_list_reads_as_cancelled_for_its_question():
    params = {"questions": [_stack()]}
    result = {
        "outcome": {
            "outcome": "answered",
            "answers": [{"questionId": "stack", "selectedOptionIds": "py"}],
        }
    }
    assert build_prompt_qa(ASK, (params,), {}, result) == [("Qual stack?", CANCELLED)]


# --- Questionnaires -------------------------------------------------------------

QUESTIONNAIRE = TextQuestionnaire(
    title="Preciso de algumas informações antes de continuar.",
    questions=(
        TextQuestion(id="q1", prompt="1. Qual banco?", options=(("A", "Postgres"),)),
        TextQuestion(id="q2", prompt="2. Prazo?", options=(("A", "Curto"),)),
    ),
)
ANSWERS = "Respostas:\n\n1. Qual banco?\n→ A) Postgres\n\n2. Prazo?\n→ Outro — amanhã\n"


def test_parsed_questionnaire_pairs_each_question_with_its_answer():
    assert build_prompt_qa("run_parsed_questionnaire", (QUESTIONNAIRE,), {}, ANSWERS) == [
        ("1. Qual banco?", "A) Postgres"),
        ("2. Prazo?", "Outro — amanhã"),
    ]


def test_a_cancelled_questionnaire_marks_its_first_question():
    assert build_prompt_qa(
        "run_parsed_questionnaire", (), {"questionnaire": QUESTIONNAIRE}, None
    ) == [("1. Qual banco?", CANCELLED)]


def test_a_cancelled_questionnaire_without_questions_has_no_bubbles():
    empty = TextQuestionnaire(title="t", questions=())
    assert build_prompt_qa("run_parsed_questionnaire", (empty,), {}, None) == []


def test_a_questionnaire_argument_of_the_wrong_type_is_not_a_question():
    assert build_prompt_qa("run_parsed_questionnaire", ({"title": "x"},), {}, ANSWERS) == []


TEXT_BLOCK = "```text\n1. Qual banco?\nA) Postgres\nB) SQLite\n```\n"


def test_text_questionnaire_is_parsed_from_the_agent_text():
    result = "1. Qual banco?\n→ B) SQLite\n"
    assert build_prompt_qa("run_text_questionnaire", (TEXT_BLOCK,), {}, result) == [
        ("1. Qual banco?", "B) SQLite")
    ]
    assert build_prompt_qa("run_text_questionnaire", (), {"text": TEXT_BLOCK}, None) == [
        ("1. Qual banco?", CANCELLED)
    ]


def test_text_without_a_questionnaire_is_not_a_question():
    assert build_prompt_qa("run_text_questionnaire", ("Só texto.",), {}, None) == []
    assert build_prompt_qa("run_text_questionnaire", (None,), {}, None) == []


# --- Permission -----------------------------------------------------------------

PERMISSION = {
    "permission": {"title": "Editar app.py", "kind": "edit"},
    "options": [
        {"optionId": "allow-once", "kind": "allow_once"},
        {"optionId": "reject-once", "kind": "reject_once"},
    ],
}


def _selected(option_id: str) -> dict[str, object]:
    return {"outcome": {"outcome": "selected", "optionId": option_id}}


def test_an_asked_permission_shows_the_picked_option_label():
    result = build_prompt_qa(
        "respond_to_permission", (PERMISSION,), {"policy": "ask"}, _selected("reject-once")
    )
    assert result == [("Editar app.py", f"B) {ui_text.REJECT_ONCE}")]


def test_a_permission_without_a_policy_is_treated_as_asked():
    result = build_prompt_qa("respond_to_permission", (), {"params": PERMISSION}, _selected("x"))
    assert result == [("Editar app.py", "x")]


def test_a_cancelled_permission_is_shown_as_cancelled():
    result = build_prompt_qa(
        "respond_to_permission", (PERMISSION,), {"policy": "ask"}, {"outcome": {}}
    )
    assert result == [("Editar app.py", CANCELLED)]


def test_a_permission_the_policy_decided_was_never_shown():
    """Policy is not a question: the history must not show a dialog that never happened."""
    assert (
        build_prompt_qa(
            "respond_to_permission",
            (PERMISSION,),
            {"policy": "auto_approve"},
            _selected("allow-once"),
        )
        == []
    )
    terminal = {**PERMISSION, "permission": {"title": "rm", "kind": "terminal"}}
    assert build_prompt_qa("respond_to_permission", (terminal,), {"policy": "ask"}, None) == []


def test_a_terminal_permission_allowed_by_config_is_asked_under_ask():
    terminal = {**PERMISSION, "permission": {"title": "Rodar ls", "kind": "terminal"}}
    result = build_prompt_qa(
        "respond_to_permission",
        (terminal,),
        {"policy": "ask", "allow_terminal": True},
        _selected("allow-once"),
    )
    assert result == [("Rodar ls", f"A) {ui_text.ALLOW_ONCE}")]


def test_permission_params_of_the_wrong_type_are_not_a_question():
    assert build_prompt_qa("respond_to_permission", ([],), {"policy": "ask"}, None) == []


# --- Plan, text and choice ------------------------------------------------------


def test_create_plan_records_yes_no_or_cancelled():
    params = {"name": "Plano X", "overview": "Resumo"}
    prompt = f"{ui_text.PLAN_APPROVAL_TITLE}\nPlano X\nResumo"
    for decision, answer in (
        ("accepted", ui_text.ANSWER_YES),
        ("rejected", ui_text.ANSWER_NO),
        ("cancelled", CANCELLED),
    ):
        result = {"outcome": {"outcome": decision}}
        assert build_prompt_qa("respond_to_create_plan", (params,), {}, result) == [
            (prompt, answer)
        ]


def test_create_plan_params_of_the_wrong_type_are_not_a_question():
    assert build_prompt_qa("respond_to_create_plan", ("plan",), {}, None) == []


def test_ask_text_records_the_trimmed_answer():
    assert build_prompt_qa("ask_text", ("  O quê?  ",), {}, "  isso  ") == [("O quê?", "isso")]
    assert build_prompt_qa("ask_text", (), {"prompt": "O quê?"}, "   ") == [("O quê?", EMPTY)]
    assert build_prompt_qa("ask_text", ("O quê?",), {}, None) == [("O quê?", CANCELLED)]


def test_ask_text_without_a_prompt_is_not_a_question():
    assert build_prompt_qa("ask_text", ("   ",), {}, "x") == []


def test_select_choice_records_the_label_of_the_chosen_value():
    choices = [("Refazer", "retry"), (" Parar ", "stop")]
    assert build_prompt_qa("select_choice", ("E agora?", choices), {}, "stop") == [
        ("E agora?", "Parar")
    ]
    assert build_prompt_qa(
        "select_choice", (), {"prompt": "E agora?", "choices": choices}, "retry"
    ) == [("E agora?", "Refazer")]


def test_select_choice_falls_back_to_the_raw_value_or_a_dash():
    choices = [("Refazer", "retry"), ("incomplete",)]
    assert build_prompt_qa("select_choice", ("E agora?", choices), {}, " other ") == [
        ("E agora?", "other")
    ]
    assert build_prompt_qa("select_choice", ("E agora?", choices), {}, "") == [("E agora?", EMPTY)]


def test_select_choice_cancelled_or_without_prompt():
    assert build_prompt_qa("select_choice", ("E agora?", []), {}, None) == [("E agora?", CANCELLED)]
    assert build_prompt_qa("select_choice", ("",), {}, "x") == []
