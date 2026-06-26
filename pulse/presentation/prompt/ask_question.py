from __future__ import annotations

from typing import Any

OTHER_OPTION_ID = "__other__"
DEFAULT_QUESTIONNAIRE_TITLE = "Preciso de algumas informações antes de continuar."
_OPTION_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def parse_ask_question_params(params: dict[str, Any]) -> list[dict[str, Any]]:
    questions = params.get("questions", [])
    if not isinstance(questions, list):
        return []
    return [question for question in questions if isinstance(question, dict)]


def parse_questionnaire_meta(params: dict[str, Any]) -> dict[str, Any]:
    title = str(params.get("title", "")).strip()
    total_raw = params.get("totalQuestions", params.get("total_questions"))
    index_raw = params.get("questionIndex", params.get("question_index"))
    total = int(total_raw) if isinstance(total_raw, int) and total_raw > 0 else None
    index = int(index_raw) if isinstance(index_raw, int) and index_raw > 0 else None
    return {"title": title, "total": total, "index": index}


def resolve_question_progress(
    *,
    question: dict[str, Any],
    position: int,
    batch_size: int,
    meta: dict[str, Any],
) -> tuple[int | None, int | None]:
    index = meta.get("index")
    total = meta.get("total")
    if isinstance(index, int) and index > 0:
        resolved_index = index
    elif batch_size > 1:
        resolved_index = position
    else:
        resolved_index = None

    if isinstance(total, int) and total > 0:
        resolved_total = total
    elif batch_size > 1:
        resolved_total = batch_size
    else:
        resolved_total = None

    question_index = question.get("index", question.get("questionIndex"))
    question_total = question.get("totalQuestions", question.get("total_questions"))
    if isinstance(question_index, int) and question_index > 0:
        resolved_index = question_index
    if isinstance(question_total, int) and question_total > 0:
        resolved_total = question_total

    return resolved_index, resolved_total


def format_option_label(index: int, label: str) -> str:
    letter = _OPTION_LETTERS[index] if index < len(_OPTION_LETTERS) else str(index + 1)
    stripped = label.strip()
    if stripped.upper().startswith(f"{letter})"):
        return stripped
    return f"{letter}) {stripped}"


def is_other_option(option_id: str, label: str = "") -> bool:
    normalized_id = option_id.strip().lower()
    normalized_label = label.strip().lower()
    return normalized_id in {"outro", "other", "__other__"} or normalized_label in {
        "outro",
        "other",
    }


def build_ask_question_answer(
    question_id: str,
    selected_option_ids: list[str],
) -> dict[str, Any]:
    return build_ask_question_answers(
        [{"questionId": question_id, "selectedOptionIds": selected_option_ids}]
    )


def build_ask_question_answers(answers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "outcome": {
            "outcome": "answered",
            "answers": answers,
        }
    }


def build_ask_question_cancelled() -> dict[str, Any]:
    return {"outcome": {"outcome": "cancelled"}}
