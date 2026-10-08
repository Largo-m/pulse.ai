from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from pulse.domain import ui_text
from pulse.domain.ports import JsonObject
from pulse.replies.acp_payloads import (
    Question,
    QuestionAnswer,
    QuestionnaireMeta,
    QuestionOption,
    truthy_text,
)

OTHER_OPTION_ID = "__other__"
_OPTION_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_FREE_TEXT_VERB = re.compile(
    r"descrev|descri[çc][ãa]|especifi|detalh|expliqu|explicar|informe|informar"
    r"|describe|specify|explain|elaborate",
    re.IGNORECASE,
)
_TEXT_REQUEST = re.compile(
    rf"(?:[(\[—–:]|--)\s*(?:{_FREE_TEXT_VERB.pattern})",
    re.IGNORECASE,
)
_APPROVAL_PROMPT = re.compile(r"\baprovar\b|\bapprove\b", re.IGNORECASE)

APPROVE_WORDS = ("aprov", "approv")
CANCEL_WORDS = ("cancelar", "cancel")
SKIP_WORDS = ("pular", "skip")
ADJUST_WORDS = ("ajust", "adjust", "change")
NEGATIVE_WORDS = ("não", "nao", "no,", "not ", *ADJUST_WORDS, *CANCEL_WORDS, *SKIP_WORDS)
_OTHER_LABEL = re.compile(
    r"^(?:[a-z0-9]+\)\s*)?(?:outro|other)(?:\s|\(|$)",
    re.IGNORECASE,
)


def resolve_question_progress(
    *,
    question: Question,
    position: int,
    batch_size: int,
    meta: QuestionnaireMeta,
) -> tuple[int | None, int | None]:
    """`(index, total)` for the dock title; `(None, None)` hides the counter.

    The question's own counters win over the questionnaire's, which win over
    the position in a batch; a lone question with no counters shows none.
    """
    in_batch = batch_size > 1
    index = question.index or meta.index or (position if in_batch else None)
    total = question.total or meta.total or (batch_size if in_batch else None)
    return index, total


def format_option_label(index: int, label: str) -> str:
    letter = _OPTION_LETTERS[index] if index < len(_OPTION_LETTERS) else str(index + 1)
    stripped = label.strip()
    if stripped.upper().startswith(f"{letter})"):
        return stripped
    return f"{letter}) {stripped}"


def is_other_option(option_id: str, label: str = "") -> bool:
    normalized_id = option_id.strip().lower()
    if normalized_id in {"outro", "other", "__other__"}:
        return True
    return bool(_OTHER_LABEL.match(label.strip()))


def option_requires_description(label: str) -> bool:
    """Whether the label asks the user to type something.

    Matches free-text verbs after `(`, `[`, `—`, `:` and similar, or a label
    ending in `:` that contains one.
    """
    text = label.strip()
    if _TEXT_REQUEST.search(text):
        return True
    return text.endswith(":") and bool(_FREE_TEXT_VERB.search(text))


def is_approval_prompt(prompt: str) -> bool:
    """A question that decides whether the run advances, where "no" needs a reason."""
    return bool(_APPROVAL_PROMPT.search(prompt))


def is_free_text_answer(answer: str) -> bool:
    return answer.strip().lower().startswith(ui_text.FREE_TEXT_ANSWER_PREFIX.strip().lower())


def should_add_other_option(*, prompt: str, option_labels: list[str]) -> bool:
    prompt_lower = prompt.lower()
    labels_lower = [label.lower() for label in option_labels]

    if any(is_other_option("", label) for label in option_labels):
        return False
    if any(word in label for label in labels_lower for word in CANCEL_WORDS):
        return False
    if any(word in label for label in labels_lower for word in APPROVE_WORDS):
        return False

    closed_prompt_markers = (
        "e avançar?",
        "como deseja prosseguir",
        "funciona como esperado",
        "não funciona (descreva",
    )
    return not any(marker in prompt_lower for marker in closed_prompt_markers)


def build_question_choices(
    options: Sequence[QuestionOption],
    *,
    prompt: str = "",
) -> list[tuple[str, str]]:
    """Options as the dock shows them: `(id, "A) label")`, in order.

    Lives here, not in the TUI, so the history log names the answer exactly as
    the live screen did.
    """
    choices: list[tuple[str, str]] = []
    for index, option in enumerate(options):
        if is_other_option(option.id, option.label):
            choices.append(
                (OTHER_OPTION_ID, format_option_label(index, ui_text.OTHER_DESCRIBE_OPTION))
            )
        else:
            choices.append((option.id, format_option_label(index, option.label)))

    has_other = any(option_id == OTHER_OPTION_ID for option_id, _ in choices)
    labels = [option.label for option in options]
    if choices and not has_other and should_add_other_option(prompt=prompt, option_labels=labels):
        other_label = format_option_label(len(choices), ui_text.OTHER_DESCRIBE_OPTION)
        choices.append((OTHER_OPTION_ID, other_label))

    return choices


def multi_select_prompt(prompt: str) -> str:
    """The multi-select question text as the dock shows it."""
    return f"{prompt}\n{ui_text.MULTI_SELECT_HINT}"


PLAN_PREVIEW_CHARS = 1200


def plan_prompt_text(params: Mapping[str, object]) -> str:
    """Body of the plan approval dock (`cursor/create_plan`)."""
    name = truthy_text(params.get("name") or ui_text.PLAN_FALLBACK_NAME).strip()
    overview = truthy_text(params.get("overview")).strip()
    plan = truthy_text(params.get("plan")).strip()
    body = name
    if overview:
        body = f"{body}\n{overview}"
    if plan:
        body = f"{body}\n\n{plan[:PLAN_PREVIEW_CHARS]}"
    return body


def build_ask_question_answers(answers: Sequence[QuestionAnswer]) -> JsonObject:
    return {
        "outcome": {
            "outcome": "answered",
            "answers": [answer.to_wire() for answer in answers],
        }
    }


def build_ask_question_cancelled() -> JsonObject:
    return {"outcome": {"outcome": "cancelled"}}
