"""Leitura da aprovação que o agente devolve no bloco ` ```text `.

O Pulse não interpreta o conteúdo do que o agente produziu — só o desfecho do
questionário de aprovação: seguir, ajustar, pular ou cancelar. É a única coisa
que ele precisa saber para decidir se o próximo agente pode rodar.
"""

from __future__ import annotations

from pulse.prompts.ask_question import is_free_text_answer

#: Resumo de um step injetado no prompt do seguinte. Sem teto, um step que
#: despeja um arquivo inteiro estoura o contexto do próximo.
SUMMARY_MAX_CHARS = 8_000

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
    for line in answers_text.splitlines():
        if line.strip().startswith("→"):
            answer = line.lstrip("→").strip()
            if answer:
                result.append(answer)
    return result


def is_positive(answers_text: str) -> bool:
    picked = picked_answers(answers_text)
    if not picked:
        return False
    for raw in picked:
        # Texto livre é orientação, não escolha: "revise o fluxo de aprovação"
        # não pode aprovar o step só porque contém "aprov".
        if is_free_text_answer(raw):
            continue
        answer = raw.lower()
        if any(token in answer for token in ("não", "nao", "ajuste", "cancel", "pular")):
            continue
        if "aprov" in answer:
            return True
    return False


def classify_outcome(answers_text: str) -> str:
    picked = [answer.lower() for answer in picked_answers(answers_text)]
    if not picked:
        return UNKNOWN
    if any("cancelar" in answer for answer in picked):
        return CANCEL
    if any("pular" in answer for answer in picked):
        return SKIP
    if is_positive(answers_text):
        return APPROVE
    if any("ajuste" in answer for answer in picked):
        return ADJUST
    return CONTINUE
