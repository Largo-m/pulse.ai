"""How `TextualPromptHandler` turns agent requests into dock questions and back.

A worker thread plays the agent side (the handler blocks on the bridge); the
test thread plays the screen, polling each queued question and answering it.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import pytest

from pulse.replies.ask_question import OTHER_OPTION_ID
from pulse.replies.text_questionnaire import parse_text_questionnaire, split_questionnaire_answers
from pulse.replies.wording import (
    DEFAULT_QUESTIONNAIRE_TITLE,
    FREE_TEXT_ANSWER_PREFIX,
    MULTI_SELECT_HINT,
    OTHER_DESCRIBE_OPTION,
    PLAN_APPROVAL_TITLE,
)
from pulse.tui import strings
from pulse.tui.adapters.prompt_bridge import (
    PromptAbandoned,
    PromptBridge,
    PromptKind,
    PromptRequest,
    TextualPromptHandler,
    format_prompt_reply,
)

WAIT = 2.0


def _drive(
    bridge: PromptBridge, call: Callable[[], object], answers: list[object]
) -> tuple[object, list[PromptRequest]]:
    """Run `call` on a worker and answer each question it asks, in order."""
    seen: list[PromptRequest] = []
    with ThreadPoolExecutor(max_workers=1) as pool:
        outcome = pool.submit(call)
        for answer in answers:
            request = bridge.poll(timeout=WAIT)
            assert request is not None, f"no question queued for answer {answer!r}"
            assert request.future is not None
            seen.append(request)
            request.future.set_result(answer)
        result = outcome.result(timeout=WAIT)
    assert bridge.poll() is None, "the handler asked more than the test answered"
    return result, seen


def _handler() -> tuple[PromptBridge, TextualPromptHandler]:
    bridge = PromptBridge()
    return bridge, TextualPromptHandler(bridge)


def _answered(*pairs: tuple[str, list[str]]) -> dict[str, object]:
    return {
        "outcome": {
            "outcome": "answered",
            "answers": [
                {"questionId": question_id, "selectedOptionIds": ids} for question_id, ids in pairs
            ],
        }
    }


CANCELLED = {"outcome": {"outcome": "cancelled"}}


def _stack_question(**extra: object) -> dict[str, object]:
    return {
        "id": "stack",
        "prompt": "Qual stack?",
        "options": [{"id": "py", "label": "Python"}, {"id": "go", "label": "Go"}],
        **extra,
    }


# --- PromptBridge lifecycle ---------------------------------------------------


def test_closing_the_bridge_answers_the_open_question_with_none():
    """A run that ended must release the agent thread with a cancellation."""
    bridge = PromptBridge()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(bridge.select, "Escolha", [("a", "Alpha")])
        request = bridge.poll(timeout=WAIT)
        assert request is not None
        bridge.close()
        assert pending.result(timeout=WAIT) is None
    assert request.future is not None
    assert request.future.result(timeout=0) is None


def test_a_closed_bridge_answers_none_without_queueing():
    bridge, handler = _handler()
    bridge.close()

    assert handler.respond_to_create_plan({"name": "Plano X"}) == CANCELLED
    assert bridge.poll() is None


def test_abandoning_raises_in_the_waiting_caller_and_in_later_callers():
    """Leaving the screen must not answer "cancelled": the question survives."""
    bridge = PromptBridge()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(bridge.text, "Descreva")
        assert bridge.poll(timeout=WAIT) is not None
        bridge.abandon()
        with pytest.raises(PromptAbandoned):
            pending.result(timeout=WAIT)

    with pytest.raises(PromptAbandoned):
        bridge.confirm("Ok?")
    assert bridge.poll() is None


def test_poll_without_timeout_returns_none_when_nothing_is_queued():
    assert PromptBridge().poll() is None


def test_text_and_confirm_coerce_the_screen_answer():
    bridge = PromptBridge()
    text, seen = _drive(bridge, lambda: bridge.text("Nome?", title="T", default="x"), [42])
    assert text == "42"
    assert (seen[0].kind, seen[0].title, seen[0].default) == (PromptKind.TEXT, "T", "x")

    confirmed, seen = _drive(bridge, lambda: bridge.confirm("Ok?", default=False), [1])
    assert confirmed is True
    assert (seen[0].kind, seen[0].default) == (PromptKind.CONFIRM, False)


def test_multi_select_rejects_an_answer_that_is_not_a_list():
    bridge = PromptBridge()
    picked, _ = _drive(bridge, lambda: bridge.multi_select("Quais?", [("a", "A")]), ["a"])
    assert picked is None

    picked, seen = _drive(bridge, lambda: bridge.multi_select("Quais?", [("a", "A")]), [[1, "a"]])
    assert picked == ["1", "a"]
    assert seen[0].kind == PromptKind.MULTI_SELECT


def test_format_prompt_reply_shows_a_dash_for_empty_answers_and_raw_unknown_ids():
    text = PromptRequest(kind=PromptKind.TEXT, title="", prompt="p", choices=[])
    multi = PromptRequest(kind=PromptKind.MULTI_SELECT, title="", prompt="p", choices=[("a", "A")])
    select = PromptRequest(kind=PromptKind.SELECT, title="", prompt="p", choices=[("a", "A")])

    assert format_prompt_reply(text, "   ") == "—"
    assert format_prompt_reply(multi, "not-a-list") == "—"
    assert format_prompt_reply(multi, ["a", "zz"]) == "A, zz"
    assert format_prompt_reply(select, "zz") == "zz"


# --- AskQuestion --------------------------------------------------------------


def test_ask_question_without_questions_is_cancelled_without_asking():
    bridge, handler = _handler()
    assert handler.respond_to_ask_question({"questions": []}) == CANCELLED
    assert handler.respond_to_ask_question({"questions": "nope"}) == CANCELLED
    assert bridge.poll() is None


def test_single_choice_answer_is_returned_with_the_question_id():
    bridge, handler = _handler()
    result, seen = _drive(
        bridge, lambda: handler.respond_to_ask_question({"questions": [_stack_question()]}), ["go"]
    )

    assert result == _answered(("stack", ["go"]))
    request = seen[0]
    assert request.kind == PromptKind.SELECT
    assert request.prompt == "Qual stack?"
    assert request.title == DEFAULT_QUESTIONNAIRE_TITLE
    assert request.choices == [
        ("py", "A) Python"),
        ("go", "B) Go"),
        (OTHER_OPTION_ID, f"C) {OTHER_DESCRIBE_OPTION}"),
    ]


def test_a_cancelled_pick_cancels_the_whole_ask_question():
    bridge, handler = _handler()
    result, _ = _drive(
        bridge, lambda: handler.respond_to_ask_question({"questions": [_stack_question()]}), [None]
    )
    assert result == CANCELLED


def test_picking_other_asks_for_text_and_retries_on_blank():
    """An empty "Other" text is not an answer: the agent would get nothing to act on."""
    bridge, handler = _handler()
    result, seen = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [_stack_question()]}),
        [OTHER_OPTION_ID, "   ", "  Rust  "],
    )

    assert result == _answered(("stack", ["Rust"]))
    other_prompt = strings.OTHER_OPTION_PROMPT.format(prompt="Qual stack?")
    assert [(r.kind, r.prompt) for r in seen[1:]] == [
        (PromptKind.TEXT, other_prompt),
        (PromptKind.TEXT, other_prompt),
    ]


def test_cancelling_the_other_text_cancels_the_answer():
    bridge, handler = _handler()
    result, _ = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [_stack_question()]}),
        [OTHER_OPTION_ID, None],
    )
    assert result == CANCELLED


def _adjust_question() -> dict[str, object]:
    return {
        "id": "gate",
        "prompt": "Como seguir?",
        "options": [
            {"id": "ok", "label": "Seguir"},
            {"id": "adj", "label": "Ajustar (descreva)"},
        ],
    }


def test_a_choice_that_asks_for_a_description_sends_id_and_detail():
    """`id::detail` lets the agent know both the pick and what the user typed."""
    bridge, handler = _handler()
    result, seen = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [_adjust_question()]}),
        ["adj", "", " trocar o banco "],
    )

    assert result == _answered(("gate", ["adj::trocar o banco"]))
    follow_up = "Como seguir?\n[B) Ajustar (descreva)]"
    assert [r.prompt for r in seen[1:]] == [follow_up, follow_up]


def test_a_plain_choice_does_not_ask_for_a_description():
    bridge, handler = _handler()
    result, _ = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [_adjust_question()]}),
        ["ok"],
    )
    assert result == _answered(("gate", ["ok"]))


def test_cancelling_the_description_cancels_the_answer():
    bridge, handler = _handler()
    result, _ = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [_adjust_question()]}),
        ["adj", None],
    )
    assert result == CANCELLED


def test_an_id_outside_the_choices_is_sent_as_is():
    bridge, handler = _handler()
    result, _ = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [_adjust_question()]}),
        ["mystery"],
    )
    assert result == _answered(("gate", ["mystery"]))


def test_a_question_without_options_is_answered_with_trimmed_free_text():
    bridge, handler = _handler()
    result, seen = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [{"id": "n", "prompt": ""}]}),
        ["  pulse  "],
    )

    assert result == _answered(("n", ["pulse"]))
    assert seen[0].kind == PromptKind.TEXT
    assert seen[0].prompt == strings.QUESTION


def test_cancelling_a_free_text_question_cancels_the_answer():
    bridge, handler = _handler()
    result, _ = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [{"id": "n", "prompt": "Nome?"}]}),
        [None],
    )
    assert result == CANCELLED


def test_options_pulse_cannot_read_cancel_instead_of_offering_an_empty_list():
    bridge, handler = _handler()
    params = {"questions": [{"id": "q", "prompt": "Qual?", "options": ["a", 3]}]}
    assert handler.respond_to_ask_question(params) == CANCELLED
    assert bridge.poll() is None


def test_multi_select_replaces_other_with_the_typed_text():
    bridge, handler = _handler()
    question = _stack_question(allowMultiple=True)
    result, seen = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [question]}),
        [["py", OTHER_OPTION_ID], "Elixir"],
    )

    assert result == _answered(("stack", ["py", "Elixir"]))
    assert seen[0].kind == PromptKind.MULTI_SELECT
    assert seen[0].prompt == f"Qual stack?\n{MULTI_SELECT_HINT}"


def test_an_empty_multi_select_is_asked_again():
    bridge, handler = _handler()
    question = _stack_question(allowMultiple=True)
    result, seen = _drive(
        bridge,
        lambda: handler.respond_to_ask_question({"questions": [question]}),
        [[], ["go"]],
    )
    assert result == _answered(("stack", ["go"]))
    assert [r.kind for r in seen] == [PromptKind.MULTI_SELECT, PromptKind.MULTI_SELECT]


@pytest.mark.parametrize("answers", [[None], [[OTHER_OPTION_ID], None]])
def test_cancelling_a_multi_select_or_its_other_text_cancels(answers: list[object]):
    bridge, handler = _handler()
    question = _stack_question(allowMultiple=True)
    result, _ = _drive(
        bridge, lambda: handler.respond_to_ask_question({"questions": [question]}), answers
    )
    assert result == CANCELLED


def test_a_batch_shows_progress_and_cancels_when_a_later_question_is_cancelled():
    """A half-answered batch is not an answer: the agent would act on missing fields."""
    bridge, handler = _handler()
    params = {
        "title": "Entrevista",
        "questions": [_stack_question(), {"id": "name", "prompt": "Nome?"}],
    }
    result, seen = _drive(bridge, lambda: handler.respond_to_ask_question(params), ["py", None])

    assert result == CANCELLED
    assert [r.title for r in seen] == ["Entrevista · 1/2", "Entrevista · 2/2"]


def test_a_batch_returns_every_answer_in_order():
    bridge, handler = _handler()
    params = {"questions": [_stack_question(), {"id": "name", "prompt": "Nome?"}]}
    result, _ = _drive(bridge, lambda: handler.respond_to_ask_question(params), ["py", "api"])
    assert result == _answered(("stack", ["py"]), ("name", ["api"]))


# --- Plan, permission, text and choice ----------------------------------------


@pytest.mark.parametrize(
    ("answer", "expected"),
    [(True, "accepted"), (False, "rejected"), (None, "cancelled")],
)
def test_create_plan_maps_the_confirmation_to_an_outcome(answer: object, expected: str):
    bridge, handler = _handler()
    result, seen = _drive(
        bridge,
        lambda: handler.respond_to_create_plan({"name": "Plano X", "overview": "Resumo"}),
        [answer],
    )

    assert result == {"outcome": {"outcome": expected}}
    assert seen[0].kind == PromptKind.CONFIRM
    assert seen[0].title == PLAN_APPROVAL_TITLE
    assert seen[0].default is True
    assert seen[0].prompt == "Plano X\nResumo"


def _permission_params(kind: str) -> dict[str, object]:
    return {
        "permission": {"title": "Rodar comando", "kind": kind},
        "options": [
            {"optionId": "allow-once", "kind": "allow_once"},
            {"optionId": "reject-once", "kind": "reject_once"},
        ],
    }


def test_a_cancelled_permission_question_answers_cancelled():
    bridge, handler = _handler()
    result, _ = _drive(
        bridge,
        lambda: handler.respond_to_permission(_permission_params("edit"), policy="ask"),
        [None],
    )
    assert result == {"outcome": {"outcome": "cancelled"}}


def test_an_unknown_policy_asks_the_user():
    """Asking is the only safe reading of a policy Pulse does not know."""
    bridge, handler = _handler()
    result, seen = _drive(
        bridge,
        lambda: handler.respond_to_permission(_permission_params("edit"), policy="yolo"),
        ["allow-once"],
    )
    assert result == {"outcome": {"outcome": "selected", "optionId": "allow-once"}}
    assert seen[0].title == strings.PERMISSION_TITLE


def test_deny_writes_asks_when_the_kind_does_not_say_whether_it_writes():
    bridge, handler = _handler()
    result, _ = _drive(
        bridge,
        lambda: handler.respond_to_permission(_permission_params("other"), policy="deny_writes"),
        ["reject-once"],
    )
    assert result == {"outcome": {"outcome": "selected", "optionId": "reject-once"}}


def test_terminal_is_rejected_without_asking_unless_allowed():
    bridge, handler = _handler()
    vetoed = handler.respond_to_permission(_permission_params("terminal"), policy="auto_approve")
    assert vetoed == {"outcome": {"outcome": "selected", "optionId": "reject-once"}}
    assert bridge.poll() is None

    allowed = handler.respond_to_permission(
        _permission_params("terminal"), policy="auto_approve", allow_terminal=True
    )
    assert allowed == {"outcome": {"outcome": "selected", "optionId": "allow-once"}}


@pytest.mark.parametrize(("answer", "expected"), [("  ok  ", "ok"), ("   ", None), (None, None)])
def test_ask_text_trims_and_treats_blank_as_no_answer(answer: object, expected: str | None):
    bridge, handler = _handler()
    result, seen = _drive(bridge, lambda: handler.ask_text("O quê?", title="T"), [answer])
    assert result == expected
    assert (seen[0].kind, seen[0].prompt, seen[0].title) == (PromptKind.TEXT, "O quê?", "T")


def test_select_choice_returns_the_value_behind_the_picked_label():
    bridge, handler = _handler()
    choices = [("Refazer", "retry"), ("Parar", "stop")]
    result, seen = _drive(bridge, lambda: handler.select_choice("E agora?", choices), ["1"])

    assert result == "stop"
    assert seen[0].choices == [("0", "Refazer"), ("1", "Parar")]


@pytest.mark.parametrize("answer", [None, "abc", "7", "-1"])
def test_select_choice_returns_none_for_cancelled_or_out_of_range_picks(answer: object):
    bridge, handler = _handler()
    choices = [("Refazer", "retry"), ("Parar", "stop")]
    result, _ = _drive(bridge, lambda: handler.select_choice("E agora?", choices), [answer])
    assert result is None


# --- Text questionnaire -------------------------------------------------------

QUESTIONNAIRE = """Antes de seguir:

```text
Preciso de algumas informações antes de continuar.

1. Qual banco?
A) Postgres
B) Outro (descreva)

2. Aprovar o escopo?
A) Aprovar
B) Ajustar (descreva)

3. Algum comentário?
```
"""


def test_text_without_a_questionnaire_asks_nothing():
    bridge, handler = _handler()
    assert handler.run_text_questionnaire("Só um texto qualquer.") is None
    assert bridge.poll() is None


def test_text_questionnaire_formats_each_kind_of_answer():
    """Letter picks, details and free text must reach the agent in readable form."""
    bridge, handler = _handler()
    result, seen = _drive(
        bridge,
        lambda: handler.run_text_questionnaire(QUESTIONNAIRE),
        ["A", "B", "mudar o prazo", "nada a declarar"],
    )

    assert isinstance(result, str)
    title = "Preciso de algumas informações antes de continuar."
    assert [r.title for r in seen] == [
        f"{title} · 1/3",
        f"{title} · 2/3",
        f"{title} · 2/3",
        f"{title} · 3/3",
    ]
    assert [r.kind for r in seen] == [
        PromptKind.SELECT,
        PromptKind.SELECT,
        PromptKind.TEXT,
        PromptKind.TEXT,
    ]
    parsed = _pairs(result)
    assert parsed == [
        ("1. Qual banco?", "A) Postgres"),
        ("2. Aprovar o escopo?", "B) Ajustar (descreva) — mudar o prazo"),
        ("3. Algum comentário?", f"{FREE_TEXT_ANSWER_PREFIX}nada a declarar"),
    ]


def test_text_questionnaire_other_text_with_separator_keeps_both_parts():
    bridge, handler = _handler()
    result, _ = _drive(
        bridge,
        lambda: handler.run_text_questionnaire(QUESTIONNAIRE),
        [OTHER_OPTION_ID, "x::y", "A", "-"],
    )

    assert isinstance(result, str)
    assert _pairs(result)[0] == ("1. Qual banco?", "x — y")


def test_cancelling_any_questionnaire_question_returns_none():
    bridge, handler = _handler()
    result, seen = _drive(
        bridge, lambda: handler.run_text_questionnaire(QUESTIONNAIRE), ["A", None]
    )
    assert result is None
    assert len(seen) == 2


def _pairs(answers_text: str) -> list[tuple[str, str]]:
    questionnaire = parse_text_questionnaire(QUESTIONNAIRE)
    assert questionnaire is not None
    return split_questionnaire_answers(questionnaire, answers_text)
