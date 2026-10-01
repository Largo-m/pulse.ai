"""Pergunta e resposta como a tela viva as mostrou.

Irmão de [pulse.history.tool_detail]: lá um tool-call vira `Read pulse/x.py`, aqui
uma chamada ao prompt port vira o par de balões `Pergunta` / `Você` que o cockpit
desenha quando alguém responde um dock.

Quem grava o log está do lado do daemon, e lá só passa a chamada crua — os
`params` do `AskQuestion` e o `selectedOptionIds` que voltou. Reconstruir o texto
é o que faz o histórico dizer "A) Produto / plataforma" em vez de `__other__`.

Puro: nada aqui lê banco nem toca tela.
"""

from __future__ import annotations

from typing import Any

from pulse.prompts.ask_question import (
    build_question_choices,
    parse_ask_question_params,
)
from pulse.prompts.permission import (
    build_permission_choices,
    decide_permission,
    permission_prompt_text,
)
from pulse.prompts.text_questionnaire import (
    TextQuestionnaire,
    parse_text_questionnaire,
    split_questionnaire_answers,
)

#: Resposta de quem fechou a pergunta sem responder. É o mesmo texto que
#: `format_prompt_reply` põe no balão quando o dock devolve `None`.
CANCELLED = "Cancelado"
#: Sem escolha nenhuma — multi-select vazio, texto em branco.
EMPTY = "—"
#: O que separa a opção escolhida do complemento que a pessoa escreveu. O cliente
#: devolve os dois num id só (`id::detalhe`), e ao vivo isso foram dois docks.
_DETAIL_SEP = "::"

#: (pergunta, resposta), na ordem em que apareceram na tela.
QA = tuple[str, str]


def build_prompt_qa(
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
) -> list[QA]:
    """O diálogo de uma chamada ao prompt port. Vazio = não foi pergunta.

    Não foi pergunta é o caso da permissão que a política resolve sozinha: ela
    atravessa o port como qualquer outra, mas ninguém a viu.
    """
    builder = _BUILDERS.get(name)
    if builder is None:
        return []
    return builder(args, kwargs, result)


def _arg(args: tuple[Any, ...], kwargs: dict[str, Any], index: int, key: str) -> Any:
    if len(args) > index:
        return args[index]
    return kwargs.get(key)


def _ask_question_qa(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
) -> list[QA]:
    params = _arg(args, kwargs, 0, "params")
    if not isinstance(params, dict):
        return []
    questions = parse_ask_question_params(params)
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
            # A pessoa fechou o questionário aqui: o que vinha depois nunca
            # chegou a ser perguntado, então não entra no log.
            pairs.append((prompt, CANCELLED))
            break
        choices = build_question_choices(question.get("options") or [], prompt=prompt)
        pairs.append((prompt, _selected_label(choices, selected)))
    return pairs


def _question_prompt(question: dict[str, Any]) -> str:
    prompt = str(question.get("prompt", "")).strip()
    if not prompt:
        return ""
    multiple = bool(question.get("allow_multiple", question.get("allowMultiple", False)))
    # O mesmo acréscimo que o dock faz no texto da pergunta.
    return f"{prompt}\n(escolha uma ou mais)" if multiple else prompt


def _answers_by_question(result: Any) -> dict[str, list[str]] | None:
    """As respostas indexadas por `questionId`. `None` = cancelado."""
    outcome = result.get("outcome") if isinstance(result, dict) else None
    if not isinstance(outcome, dict) or outcome.get("outcome") != "answered":
        return None
    collected: dict[str, list[str]] = {}
    for index, answer in enumerate(outcome.get("answers") or []):
        if not isinstance(answer, dict):
            continue
        selected = answer.get("selectedOptionIds")
        if not isinstance(selected, list):
            continue
        # A posição entra como chave reserva: há agente que devolve a resposta
        # sem repetir o `questionId` que mandou.
        collected[str(answer.get("questionId", ""))] = [str(item) for item in selected]
        collected.setdefault(f"#{index}", [str(item) for item in selected])
    return collected


def _selected_ids(
    answers: dict[str, list[str]] | None,
    question: dict[str, Any],
    position: int,
) -> list[str] | None:
    if answers is None:
        return None
    question_id = str(question.get("id", ""))
    if question_id and question_id in answers:
        return answers[question_id]
    return answers.get(f"#{position}")


def _selected_label(choices: list[tuple[str, str]], selected: list[str]) -> str:
    labels = [_option_label(choices, str(item)) for item in selected]
    labels = [label for label in labels if label]
    return ", ".join(labels) if labels else EMPTY


def _option_label(choices: list[tuple[str, str]], selected: str) -> str:
    """O rótulo da escolha, com o que a pessoa escreveu quando houve texto livre."""
    option_id, separator, detail = selected.partition(_DETAIL_SEP)
    lookup = {str(item_id): label for item_id, label in choices}
    label = lookup.get(option_id)
    if label is None:
        # Id que não casa com opção nenhuma é o texto que a pessoa digitou em
        # "Outro" — o cliente o manda no lugar do id.
        return selected.strip()
    if separator and detail.strip():
        return f"{label} — {detail.strip()}"
    return label


def _questionnaire_qa(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
) -> list[QA]:
    questionnaire = _arg(args, kwargs, 0, "questionnaire")
    if not isinstance(questionnaire, TextQuestionnaire):
        return []
    if result is None:
        first = questionnaire.questions[0] if questionnaire.questions else None
        return [(first.prompt, CANCELLED)] if first is not None else []
    return split_questionnaire_answers(questionnaire, str(result))


def _text_questionnaire_qa(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
) -> list[QA]:
    text = _arg(args, kwargs, 0, "text")
    questionnaire = parse_text_questionnaire(str(text or ""))
    if questionnaire is None:
        return []
    return _questionnaire_qa((questionnaire,), {}, result)


def _permission_qa(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
) -> list[QA]:
    params = _arg(args, kwargs, 0, "params")
    if not isinstance(params, dict):
        return []
    policy = str(kwargs.get("policy") or "ask")
    allow_terminal = bool(kwargs.get("allow_terminal", False))
    if decide_permission(params, policy=policy, allow_terminal=allow_terminal) is not None:
        # Regra não é pergunta: ninguém viu esta decisão.
        return []

    permission = params.get("permission")
    tool_call = params.get("toolCall")
    prompt = permission_prompt_text(
        permission if isinstance(permission, dict) else {},
        tool_call if isinstance(tool_call, dict) else {},
    )
    options = params.get("options")
    choices = build_permission_choices(options if isinstance(options, list) else [])
    outcome = result.get("outcome") if isinstance(result, dict) else None
    if not isinstance(outcome, dict) or outcome.get("outcome") != "selected":
        return [(prompt, CANCELLED)]
    return [(prompt, _option_label(choices, str(outcome.get("optionId", ""))))]


def _create_plan_qa(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
) -> list[QA]:
    params = _arg(args, kwargs, 0, "params")
    if not isinstance(params, dict):
        return []
    # O mesmo corpo que o dock mostra em `respond_to_create_plan`.
    name = str(params.get("name") or "Plano").strip()
    overview = str(params.get("overview") or "").strip()
    plan = str(params.get("plan") or "").strip()
    prompt = name
    if overview:
        prompt = f"{prompt}\n{overview}"
    if plan:
        prompt = f"{prompt}\n\n{plan[:1200]}"

    outcome = result.get("outcome") if isinstance(result, dict) else None
    decision = outcome.get("outcome") if isinstance(outcome, dict) else ""
    if decision == "accepted":
        return [(f"Aprovar plano?\n{prompt}", "Sim")]
    if decision == "rejected":
        return [(f"Aprovar plano?\n{prompt}", "Não")]
    return [(f"Aprovar plano?\n{prompt}", CANCELLED)]


def _text_qa(args: tuple[Any, ...], kwargs: dict[str, Any], result: Any) -> list[QA]:
    prompt = str(_arg(args, kwargs, 0, "prompt") or "").strip()
    if not prompt:
        return []
    if result is None:
        return [(prompt, CANCELLED)]
    return [(prompt, str(result).strip() or EMPTY)]


def _choice_qa(args: tuple[Any, ...], kwargs: dict[str, Any], result: Any) -> list[QA]:
    prompt = str(_arg(args, kwargs, 0, "prompt") or "").strip()
    if not prompt:
        return []
    if result is None:
        return [(prompt, CANCELLED)]
    choices = _arg(args, kwargs, 1, "choices") or []
    for item in choices:
        if isinstance(item, (list, tuple)) and len(item) >= 2 and item[1] == result:
            return [(prompt, str(item[0]).strip())]
    return [(prompt, str(result).strip() or EMPTY)]


#: Cada método do prompt port e como ele vira diálogo. O que não está aqui não é
#: pergunta — `reset_capture`, `agent_text` e afins passam pelo mesmo proxy.
_BUILDERS = {
    "respond_to_ask_question": _ask_question_qa,
    "run_parsed_questionnaire": _questionnaire_qa,
    "run_text_questionnaire": _text_questionnaire_qa,
    "respond_to_permission": _permission_qa,
    "respond_to_create_plan": _create_plan_qa,
    "ask_text": _text_qa,
    "select_choice": _choice_qa,
}
