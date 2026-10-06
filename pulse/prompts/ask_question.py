from __future__ import annotations

import re
from typing import Any

OTHER_OPTION_ID = "__other__"
DEFAULT_QUESTIONNAIRE_TITLE = "Preciso de algumas informações antes de continuar."
_OPTION_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
#: Verbos que pedem ao usuário para escrever algo. Radical, não palavra inteira:
#: o agente conjuga ("descreva", "descrever", "descrição") e às vezes escreve em
#: inglês, porque os playbooks de fábrica são em inglês.
_FREE_TEXT_VERB = re.compile(
    r"descrev|descri[çc][ãa]|especifi|detalh|expliqu|explicar|informe|informar"
    r"|describe|specify|explain|elaborate",
    re.IGNORECASE,
)
#: Uma instrução ao usuário **abre** a anotação: logo depois de parêntese,
#: colchete, travessão ou dois-pontos — "(descreva…)", "— especifique…". Bastar o
#: verbo em qualquer ponto da anotação marcava como campo a explicação de uma
#: opção comum: "Sim: busca no título e na descrição".
_TEXT_REQUEST = re.compile(
    rf"(?:[(\[—–:]|--)\s*(?:{_FREE_TEXT_VERB.pattern})",
    re.IGNORECASE,
)
#: Perguntas em que o Pulse decide o rumo da run pela resposta. É o portão de
#: aprovação de step — não o "Como deseja prosseguir?", que é escolha fechada.
_APPROVAL_PROMPT = re.compile(r"\baprovar\b|\bapprove\b", re.IGNORECASE)

#: O vocabulário do portão de aprovação, nos dois idiomas em que ele aparece: os
#: playbooks de fábrica são em inglês e mandam escrever o bloco em português, e o
#: agente nem sempre obedece. Radicais, porque ele conjuga e pluraliza.
#: Moram aqui, e não em [pulse.prompts.approval], porque `approval` importa este
#: módulo — o contrário fecharia o ciclo.
APPROVE_WORDS = ("aprov", "approv")
CANCEL_WORDS = ("cancelar", "cancel")
SKIP_WORDS = ("pular", "skip")
ADJUST_WORDS = ("ajust", "adjust", "change")
#: Marcas de que a resposta **não** é um sim. Um rótulo que traga qualquer uma
#: delas não aprova o step, mesmo que também diga "aprovar".
NEGATIVE_WORDS = ("não", "nao", "no,", "not ", *ADJUST_WORDS, *CANCEL_WORDS, *SKIP_WORDS)
_OTHER_LABEL = re.compile(
    r"^(?:[a-z0-9]+\)\s*)?(?:outro|other)(?:\s|\(|$)",
    re.IGNORECASE,
)


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
    if normalized_id in {"outro", "other", "__other__"}:
        return True
    return bool(_OTHER_LABEL.match(label.strip()))


def option_requires_description(label: str) -> bool:
    r"""O rótulo pede que o usuário escreva algo?

    Antes isto era `\(descreva` e mais três variantes fixas: bastava o agente
    escrever `[descreva]`, `— describe` ou `Descreva:` para o campo não abrir e a
    escolha voltar ao agente sem dizer o que mudar.
    """
    text = label.strip()
    if _TEXT_REQUEST.search(text):
        return True
    # "Descreva:" no fim não deixa cauda nenhuma — os dois-pontos são o convite.
    return text.endswith(":") and bool(_FREE_TEXT_VERB.search(text))


def is_approval_prompt(prompt: str) -> bool:
    """Pergunta que decide se a run avança — onde "não" precisa vir com o motivo."""
    return bool(_APPROVAL_PROMPT.search(prompt))


#: Prefixo da resposta digitada à mão em "Outro". O que vem depois é frase do
#: usuário, não rótulo de opção — sem essa marca os classificadores de fase
#: fazem match de substring no texto livre e uma orientação que só menciona
#: "aprovação" é lida como aprovação da fase.
FREE_TEXT_ANSWER_PREFIX = "Outro — "


def is_free_text_answer(answer: str) -> bool:
    return answer.strip().lower().startswith(FREE_TEXT_ANSWER_PREFIX.strip().lower())


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
        # Aprovação de step é decisão fechada: seguir, ajustar ou cancelar. Um
        # "Outro" aqui vira texto livre onde o motor espera uma das três.
        "e avançar?",
        "como deseja prosseguir",
        "funciona como esperado",
        "não funciona (descreva",
    )
    return not any(marker in prompt_lower for marker in closed_prompt_markers)


def build_question_choices(
    options: list[Any],
    *,
    prompt: str = "",
) -> list[tuple[str, str]]:
    """As opções como o dock as mostra: `(id, "A) rótulo")`, na ordem.

    Mora aqui, e não na TUI, porque o log gravado precisa nomear a resposta
    exatamente como a tela a nomeou — uma numeração que divergisse faria o
    histórico mostrar "Produto" onde a pessoa escolheu "A) Produto".
    """
    choices: list[tuple[str, str]] = []
    has_other = False
    option_index = 0
    option_labels: list[str] = []

    for option in options:
        if not isinstance(option, dict):
            continue
        option_id = str(option.get("id", option.get("label", "")))
        label = str(option.get("label", option_id))
        option_labels.append(label)
        if is_other_option(option_id, label):
            has_other = True
            option_id = OTHER_OPTION_ID
            label = format_option_label(option_index, "Outro (descreva)")
            option_index += 1
        else:
            label = format_option_label(option_index, label)
            option_index += 1
        choices.append((option_id, label))

    if choices and not has_other and should_add_other_option(
        prompt=prompt,
        option_labels=option_labels,
    ):
        other_label = format_option_label(option_index, "Outro (descreva)")
        choices.append((OTHER_OPTION_ID, other_label))

    return choices


def multi_select_prompt(prompt: str) -> str:
    """O texto da pergunta de múltipla escolha como o dock o mostra."""
    return f"{prompt}\n(escolha uma ou mais)"


PLAN_APPROVAL_TITLE = "Aprovar plano?"
#: Teto do plano no dock de aprovação — o resto não cabe na tela.
PLAN_PREVIEW_CHARS = 1200


def plan_prompt_text(params: dict[str, Any]) -> str:
    """O corpo do dock de aprovação de plano (`cursor/create_plan`)."""
    name = str(params.get("name") or "Plano").strip()
    overview = str(params.get("overview") or "").strip()
    plan = str(params.get("plan") or "").strip()
    body = name
    if overview:
        body = f"{body}\n{overview}"
    if plan:
        body = f"{body}\n\n{plan[:PLAN_PREVIEW_CHARS]}"
    return body


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
