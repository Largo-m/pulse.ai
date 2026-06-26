from __future__ import annotations

import re
from dataclasses import dataclass, field

from pulse.presentation.prompt.ask_question import DEFAULT_QUESTIONNAIRE_TITLE

_HEADER_PATTERN = re.compile(
    r"(?:^|\n)(Preciso de algumas informações[^\n]*|I need some information[^\n]*)",
    re.IGNORECASE,
)
_FENCED_BLOCK = re.compile(r"```(?:text)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_QUESTION_LINE = re.compile(r"^(\d+)\.\s+(.+)$")
_OPTION_LINE = re.compile(r"^([A-Z])\)\s+(.+)$")


@dataclass(frozen=True)
class TextQuestion:
    id: str
    prompt: str
    options: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TextQuestionnaire:
    title: str
    questions: tuple[TextQuestion, ...]


def _strip_resposta_footer(block: str) -> str:
    return re.sub(r"\nResposta:\s*$", "", block.strip(), flags=re.IGNORECASE).strip()


def extract_questionnaire_block(text: str) -> str | None:
    if not text.strip():
        return None

    fenced = _FENCED_BLOCK.search(text)
    if fenced:
        block = _strip_resposta_footer(fenced.group(1).strip())
        if _has_question_structure(block):
            return block

    header = _HEADER_PATTERN.search(text)
    if not header:
        return None

    start = header.start(1)
    tail = text[start:]
    resposta_index = re.search(r"\nResposta:\s*(?:\n|$)", tail, re.IGNORECASE)
    if resposta_index:
        block = tail[: resposta_index.start()].strip()
    else:
        block = tail.strip()

    block = _strip_resposta_footer(block)
    if _has_question_structure(block):
        return block
    return None


def parse_text_questionnaire(text: str) -> TextQuestionnaire | None:
    block = extract_questionnaire_block(text)
    if not block:
        return None

    title = DEFAULT_QUESTIONNAIRE_TITLE
    title_match = _HEADER_PATTERN.search(block)
    if title_match:
        title = title_match.group(1).strip()

    questions: list[TextQuestion] = []
    current_number: str | None = None
    current_prompt_lines: list[str] = []
    current_options: list[tuple[str, str]] = []

    def flush_question() -> None:
        nonlocal current_number, current_prompt_lines, current_options
        if current_number is None or not current_prompt_lines:
            current_number = None
            current_prompt_lines = []
            current_options = []
            return
        prompt = " ".join(line.strip() for line in current_prompt_lines if line.strip())
        if not prompt:
            current_number = None
            current_prompt_lines = []
            current_options = []
            return
        question_id = f"q{current_number}"
        questions.append(
            TextQuestion(
                id=question_id,
                prompt=f"{current_number}. {prompt}",
                options=tuple(current_options),
            )
        )
        current_number = None
        current_prompt_lines = []
        current_options = []

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _HEADER_PATTERN.match(line):
            continue
        if line.lower().startswith("resposta:"):
            break

        question_match = _QUESTION_LINE.match(line)
        if question_match:
            flush_question()
            current_number = question_match.group(1)
            current_prompt_lines = [question_match.group(2).strip()]
            continue

        option_match = _OPTION_LINE.match(line)
        if option_match and current_number is not None:
            current_options.append((option_match.group(1), option_match.group(2).strip()))
            continue

        if current_number is not None and not current_options:
            current_prompt_lines.append(line)

    flush_question()

    if not questions:
        return None
    return TextQuestionnaire(title=title, questions=tuple(questions))


def format_questionnaire_answers(
    questionnaire: TextQuestionnaire,
    answers: list[tuple[TextQuestion, str]],
) -> str:
    lines = [
        "Respostas coletadas via questionário interativo do Pulse:",
        "",
    ]
    for question, answer in answers:
        lines.append(question.prompt)
        lines.append(f"→ {answer}")
        lines.append("")
    lines.append(
        "Continue o fluxo com base nestas respostas. "
        "Se ainda faltarem campos, invoque `cursor/ask_question` (uma pergunta por vez)."
    )
    return "\n".join(lines)


def _has_question_structure(block: str) -> bool:
    has_question = any(_QUESTION_LINE.match(line.strip()) for line in block.splitlines())
    has_option = any(_OPTION_LINE.match(line.strip()) for line in block.splitlines())
    return has_question and has_option
