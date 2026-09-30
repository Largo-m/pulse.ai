"""Leitura da aprovação que o agente devolve no bloco ` ```text `.

O Pulse não interpreta o conteúdo do que o agente produziu — só o desfecho do
questionário de aprovação: seguir, ajustar, pular ou cancelar. É a única coisa
que ele precisa saber para decidir se o próximo agente pode rodar.
"""

from __future__ import annotations

from pulse.prompts.ask_question import (
    ADJUST_WORDS,
    APPROVE_WORDS,
    CANCEL_WORDS,
    NEGATIVE_WORDS,
    SKIP_WORDS,
    is_approval_prompt,
    is_free_text_answer,
    option_requires_description,
)

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
        if any(token in answer for token in NEGATIVE_WORDS):
            continue
        if any(token in answer for token in APPROVE_WORDS):
            return True
    return False


def classify_outcome(answers_text: str) -> str:
    picked = [answer.lower() for answer in picked_answers(answers_text)]
    if not picked:
        return UNKNOWN
    if any(word in answer for answer in picked for word in CANCEL_WORDS):
        return CANCEL
    if any(word in answer for answer in picked for word in SKIP_WORDS):
        return SKIP
    if is_positive(answers_text):
        return APPROVE
    if any(word in answer for answer in picked for word in ADJUST_WORDS):
        return ADJUST
    return CONTINUE


def answer_needs_description(*, prompt: str, label: str) -> bool:
    """A escolha abre o campo de texto?

    Duas razões, e a segunda é a que não depende de como o agente escreveu:

    1. O rótulo pede — `(descreva)`, `[describe]`, `— especifique`.
    2. É um portão de aprovação e a escolha **não** aprova, pula nem cancela.
       Tudo que sobra volta ao agente como "o usuário quer mudanças", e sem texto
       isso não diz *o que* mudar: o agente refaz o mesmo turno no escuro. Vale
       para qualquer agente e qualquer step, mesmo que o rótulo seja um "Não"
       seco, porque quem decide aqui é o desfecho, não a redação.

    Classifica pelo mesmo `classify_outcome` que o motor usa depois — assim a
    pergunta que a tela faz e a leitura que o motor faz não podem discordar.
    """
    if option_requires_description(label):
        return True
    if not is_approval_prompt(prompt):
        return False
    return classify_outcome(f"→ {label}") in {ADJUST, CONTINUE}
