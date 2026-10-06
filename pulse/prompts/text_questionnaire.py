from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pulse.prompts.ask_question import DEFAULT_QUESTIONNAIRE_TITLE

_HEADER_PATTERN = re.compile(
    r"(?:^|\n)(Preciso de algumas informações[^\n]*|I need some information[^\n]*)",
    re.IGNORECASE,
)
_FENCED_BLOCK = re.compile(r"```(?:text)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_QUESTION_LINE = re.compile(r"^(\d+)\.\s+(.+)$")
_OPTION_LINE = re.compile(r"^([A-Z])\)\s+(.+)$")
#: Onde a fala do agente vira questionário: cerca `text`, ou cerca sem nome cuja
#: primeira linha já é pergunta. Qualquer cerca valia antes, e o bloco
#: `pulse:outcome` — ou um trecho de código citado — escondia o resto da fala
#: atrás de um "Questionário interativo" que não existia. A tela viva e o log
#: gravado cortam aqui, e só aqui, para mostrarem a mesma fala.
QUESTIONNAIRE_START = re.compile(
    r"```text"
    r"|```[ \t]*\n[ \t]*(?:\d+\.[ \t]|Preciso de algumas informações|I need some information)"
    r"|Preciso de algumas informações|I need some information before continuing"
    r"|Apresentando todas as perguntas",
    re.IGNORECASE,
)
#: A linha que a tela põe no lugar do bloco de perguntas. O cockpit nunca mostra
#: o questionário cru — ele vira dock — e o log gravado faz o mesmo.
QUESTIONNAIRE_NOTICE = "Questionário interativo"
#: Como [format_questionnaire_answers] marca a resposta de cada pergunta.
_ANSWER_MARK = "→ "


@dataclass(frozen=True)
class TextQuestion:
    id: str
    prompt: str
    options: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TextQuestionnaire:
    title: str
    questions: tuple[TextQuestion, ...]
    raw: str = ""


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


def strip_questionnaire_block(text: str) -> tuple[str, bool]:
    """A fala do agente sem o questionário, e se havia um.

    O bloco de perguntas não é fala: ele vira dock na tela e balões de
    Pergunta/Você no log. Gravá-lo cru fazia a run reaberta mostrar as mesmas
    perguntas duas vezes — uma no balão do assistente, outra no diálogo.
    """
    start = QUESTIONNAIRE_START.search(text)
    if start is None:
        return text.strip(), False
    return text[: start.start()].strip(), True


def split_questionnaire_answers(
    questionnaire: TextQuestionnaire,
    answers_text: str,
) -> list[tuple[str, str]]:
    """Desfaz [format_questionnaire_answers] em pares (pergunta, resposta).

    O cliente coleta pergunta a pergunta e devolve ao motor um texto só; quem
    grava o log está do lado do daemon e só tem esse texto para reconstruir o
    diálogo que a pessoa viu.
    """
    replies = [
        line.strip()[len(_ANSWER_MARK) :].strip()
        for line in str(answers_text or "").splitlines()
        if line.strip().startswith(_ANSWER_MARK)
    ]
    pairs: list[tuple[str, str]] = []
    for index, question in enumerate(questionnaire.questions):
        if index >= len(replies):
            break
        pairs.append((question.prompt, replies[index]))
    return pairs


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
    return TextQuestionnaire(title=title, questions=tuple(questions), raw=block)


def serialize_questionnaire(questionnaire: TextQuestionnaire) -> dict[str, Any]:
    return {
        "title": questionnaire.title,
        "raw": questionnaire.raw,
        "questions": [
            {
                "id": question.id,
                "prompt": question.prompt,
                "options": [
                    {"id": letter, "label": label}
                    for letter, label in question.options
                ],
            }
            for question in questionnaire.questions
        ],
    }


def questionnaire_from_payload(payload: dict[str, Any]) -> TextQuestionnaire | None:
    raw = str(payload.get("raw") or "")
    if raw:
        parsed = parse_text_questionnaire(raw)
        if parsed is not None:
            return parsed
    items = payload.get("questions") or []
    questions: list[TextQuestion] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        options: list[tuple[str, str]] = []
        for option in item.get("options") or []:
            if isinstance(option, dict):
                letter = str(option.get("id") or option.get("letter") or "").strip()
                label = str(option.get("label") or "").strip()
                if letter and label:
                    options.append((letter, label))
            elif isinstance(option, (list, tuple)) and len(option) >= 2:
                options.append((str(option[0]), str(option[1])))
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            continue
        questions.append(
            TextQuestion(
                id=str(item.get("id") or f"q{len(questions) + 1}"),
                prompt=prompt,
                options=tuple(options),
            )
        )
    if not questions:
        return None
    title = str(payload.get("title") or DEFAULT_QUESTIONNAIRE_TITLE).strip()
    return TextQuestionnaire(title=title or DEFAULT_QUESTIONNAIRE_TITLE, questions=tuple(questions), raw=raw)


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
        "Se ainda faltarem campos, invoque a ferramenta `AskQuestion` (uma pergunta por vez)."
    )
    return "\n".join(lines)


def _has_question_structure(block: str) -> bool:
    has_question = any(_QUESTION_LINE.match(line.strip()) for line in block.splitlines())
    has_option = any(_OPTION_LINE.match(line.strip()) for line in block.splitlines())
    return has_question and has_option
