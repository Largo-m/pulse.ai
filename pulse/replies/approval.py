"""Reading of the approval the agent returns in the ` ```text ` block.

Pulse only interprets the approval questionnaire outcome (approve, adjust, skip
or cancel) to decide whether the next agent may run.
"""

from __future__ import annotations

from enum import StrEnum

from pulse.replies.ask_question import (
    ADJUST_WORDS,
    APPROVE_WORDS,
    CANCEL_WORDS,
    NEGATIVE_WORDS,
    SKIP_WORDS,
    is_approval_prompt,
    is_free_text_answer,
    option_requires_description,
)

SUMMARY_MAX_CHARS = 8_000


class ApprovalOutcome(StrEnum):
    """What the user's answer to an approval gate means for the next agent."""

    APPROVE = "approve"
    ADJUST = "adjust"
    SKIP = "skip"
    CANCEL = "cancel"
    CONTINUE = "continue"
    UNKNOWN = "unknown"


def format_summary(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= SUMMARY_MAX_CHARS:
        return cleaned
    return cleaned[:SUMMARY_MAX_CHARS].rstrip() + "\n\n[… summary truncated …]"


def picked_answers(answers_text: str) -> list[str]:
    result: list[str] = []
    for raw in answers_text.splitlines():
        line = raw.strip()
        if line.startswith("→"):
            answer = line.lstrip("→").strip()
            if answer:
                result.append(answer)
    return result


def chosen_options(answers_text: str) -> list[str]:
    """What the user chose, without what they typed.

    Free text ("Outro — …") and option details (`B) Ajustar — …`) are guidance
    for the agent and must not be read as skip/approve decisions.
    """
    chosen: list[str] = []
    for raw in picked_answers(answers_text):
        if is_free_text_answer(raw):
            continue
        chosen.append(raw.split(" — ", 1)[0].lower())
    return chosen


def is_positive(answers_text: str) -> bool:
    for answer in chosen_options(answers_text):
        if any(token in answer for token in NEGATIVE_WORDS):
            continue
        if any(token in answer for token in APPROVE_WORDS):
            return True
    return False


def classify_outcome(answers_text: str) -> ApprovalOutcome:
    if not picked_answers(answers_text):
        return ApprovalOutcome.UNKNOWN
    picked = chosen_options(answers_text)
    if any(word in answer for answer in picked for word in CANCEL_WORDS):
        return ApprovalOutcome.CANCEL
    if any(word in answer for answer in picked for word in SKIP_WORDS):
        return ApprovalOutcome.SKIP
    if is_positive(answers_text):
        return ApprovalOutcome.APPROVE
    if any(word in answer for answer in picked for word in ADJUST_WORDS):
        return ApprovalOutcome.ADJUST
    return ApprovalOutcome.CONTINUE


def answer_needs_description(*, prompt: str, label: str) -> bool:
    """Whether the choice opens the free-text field.

    True when the label asks for it (`(descreva)`, `[describe]`, `— especifique`),
    or when it is an approval gate and the choice does not approve, skip or
    cancel, so the agent learns *what* to change. Uses the same
    `classify_outcome` as the engine so UI and engine cannot disagree.
    """
    if option_requires_description(label):
        return True
    if not is_approval_prompt(prompt):
        return False
    return classify_outcome(f"→ {label}") in {ApprovalOutcome.ADJUST, ApprovalOutcome.CONTINUE}
