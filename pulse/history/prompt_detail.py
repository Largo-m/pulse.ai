"""Question and answer pairs as the live screen showed them.

Sibling of [pulse.history.tool_detail]: a prompt-port call becomes the
question / answer bubbles the cockpit draws when someone answers a dock. The
daemon only logs the raw call (`params`, `selectedOptionIds`), so the text is
rebuilt here. Pure: no database or UI access.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from pulse.history import log_wording
from pulse.replies import wording
from pulse.replies.acp_payloads import (
    AskQuestionRequest,
    PermissionRequest,
    Question,
    items_of,
    mapping_of,
    text_of,
)
from pulse.replies.ask_question import (
    build_question_choices,
    multi_select_prompt,
    plan_prompt_text,
)
from pulse.replies.permission import (
    build_permission_choices,
    decide_permission_call,
    permission_prompt_text,
)
from pulse.replies.text_questionnaire import (
    TextQuestionnaire,
    parse_text_questionnaire,
    split_questionnaire_answers,
)

CANCELLED = log_wording.ANSWER_CANCELLED
EMPTY = "—"
_DETAIL_SEP = "::"

QA = tuple[str, str]
Args = tuple[object, ...]
Kwargs = Mapping[str, object]


def build_prompt_qa(name: str, args: Args, kwargs: Kwargs, result: object) -> list[QA]:
    """The dialog of a prompt-port call. Empty means it was not a question.

    E.g. a permission resolved by policy goes through the port but was never shown.
    """
    builder = _BUILDERS.get(name)
    if builder is None:
        return []
    return builder(args, kwargs, result)


def _arg(args: Args, kwargs: Kwargs, index: int, key: str) -> object:
    if len(args) > index:
        return args[index]
    return kwargs.get(key)


def _outcome(result: object) -> Mapping[str, object]:
    """The `outcome` object of an ACP answer; empty when the answer has none."""
    return mapping_of(mapping_of(result).get("outcome"))


def _ask_question_qa(args: Args, kwargs: Kwargs, result: object) -> list[QA]:
    params = _arg(args, kwargs, 0, "params")
    if not isinstance(params, Mapping):
        return []
    questions = AskQuestionRequest.parse(params).questions
    if not questions:
        return []

    answers = _answers_by_question(result)
    pairs: list[QA] = []
    for position, question in enumerate(questions):
        prompt = _question_prompt(question)
        if not prompt:
            continue
        selected = _selected_ids(answers, question, position)
        if selected is None:
            pairs.append((prompt, CANCELLED))
            break
        choices = build_question_choices(question.options or (), prompt=prompt)
        pairs.append((prompt, _selected_label(choices, selected)))
    return pairs


def _question_prompt(question: Question) -> str:
    if not question.prompt:
        return ""
    return multi_select_prompt(question.prompt) if question.allow_multiple else question.prompt


def _answers_by_question(result: object) -> dict[str, list[str]] | None:
    """Answers indexed by `questionId`. `None` means cancelled."""
    outcome = _outcome(result)
    if outcome.get("outcome") != "answered":
        return None
    collected: dict[str, list[str]] = {}
    for index, answer in enumerate(items_of(outcome.get("answers"))):
        answer_fields = mapping_of(answer)
        selected = answer_fields.get("selectedOptionIds")
        if not isinstance(selected, list):
            continue
        selected_ids = [str(item) for item in selected]
        collected[text_of(answer_fields.get("questionId"))] = selected_ids
        collected.setdefault(f"#{index}", selected_ids)
    return collected


def _selected_ids(
    answers: dict[str, list[str]] | None,
    question: Question,
    position: int,
) -> list[str] | None:
    if answers is None:
        return None
    if question.id and question.id in answers:
        return answers[question.id]
    return answers.get(f"#{position}")


def _selected_label(choices: list[tuple[str, str]], selected: list[str]) -> str:
    labels = [_option_label(choices, str(item)) for item in selected]
    labels = [label for label in labels if label]
    return ", ".join(labels) if labels else EMPTY


def _option_label(choices: list[tuple[str, str]], selected: str) -> str:
    """The choice label, plus the free text the user typed, if any."""
    option_id, separator, detail = selected.partition(_DETAIL_SEP)
    lookup = {str(item_id): label for item_id, label in choices}
    label = lookup.get(option_id)
    if label is None:
        return selected.strip()
    if separator and detail.strip():
        return f"{label} — {detail.strip()}"
    return label


def _questionnaire_qa(args: Args, kwargs: Kwargs, result: object) -> list[QA]:
    questionnaire = _arg(args, kwargs, 0, "questionnaire")
    if not isinstance(questionnaire, TextQuestionnaire):
        return []
    if result is None:
        first = questionnaire.questions[0] if questionnaire.questions else None
        return [(first.prompt, CANCELLED)] if first is not None else []
    return split_questionnaire_answers(questionnaire, str(result))


def _text_questionnaire_qa(args: Args, kwargs: Kwargs, result: object) -> list[QA]:
    text = _arg(args, kwargs, 0, "text")
    questionnaire = parse_text_questionnaire(str(text or ""))
    if questionnaire is None:
        return []
    return _questionnaire_qa((questionnaire,), {}, result)


def _permission_qa(args: Args, kwargs: Kwargs, result: object) -> list[QA]:
    params = _arg(args, kwargs, 0, "params")
    if not isinstance(params, Mapping):
        return []
    if decide_permission_call(args, kwargs) is not None:
        return []

    request = PermissionRequest.parse(params)
    prompt = permission_prompt_text(request)
    choices = build_permission_choices(request.options)
    outcome = _outcome(result)
    if outcome.get("outcome") != "selected":
        return [(prompt, CANCELLED)]
    return [(prompt, _option_label(choices, text_of(outcome.get("optionId"))))]


def _create_plan_qa(args: Args, kwargs: Kwargs, result: object) -> list[QA]:
    params = _arg(args, kwargs, 0, "params")
    if not isinstance(params, Mapping):
        return []
    prompt = f"{wording.PLAN_APPROVAL_TITLE}\n{plan_prompt_text(params)}"

    decision = _outcome(result).get("outcome")
    if decision == "accepted":
        return [(prompt, log_wording.ANSWER_YES)]
    if decision == "rejected":
        return [(prompt, log_wording.ANSWER_NO)]
    return [(prompt, CANCELLED)]


def _text_qa(args: Args, kwargs: Kwargs, result: object) -> list[QA]:
    prompt = str(_arg(args, kwargs, 0, "prompt") or "").strip()
    if not prompt:
        return []
    if result is None:
        return [(prompt, CANCELLED)]
    return [(prompt, str(result).strip() or EMPTY)]


def _choice_qa(args: Args, kwargs: Kwargs, result: object) -> list[QA]:
    prompt = str(_arg(args, kwargs, 0, "prompt") or "").strip()
    if not prompt:
        return []
    if result is None:
        return [(prompt, CANCELLED)]
    for item in items_of(_arg(args, kwargs, 1, "choices")):
        pair = items_of(item)
        if len(pair) >= 2 and pair[1] == result:
            return [(prompt, str(pair[0]).strip())]
    return [(prompt, str(result).strip() or EMPTY)]


_BUILDERS: dict[str, Callable[[Args, Kwargs, object], list[QA]]] = {
    "respond_to_ask_question": _ask_question_qa,
    "run_parsed_questionnaire": _questionnaire_qa,
    "run_text_questionnaire": _text_questionnaire_qa,
    "respond_to_permission": _permission_qa,
    "respond_to_create_plan": _create_plan_qa,
    "ask_text": _text_qa,
    "select_choice": _choice_qa,
}
