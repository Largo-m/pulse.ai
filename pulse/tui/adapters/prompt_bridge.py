from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from enum import Enum
from queue import Empty, Queue
from typing import Any

from pulse.prompts.ask_question import (
    DEFAULT_QUESTIONNAIRE_TITLE,
    FREE_TEXT_ANSWER_PREFIX,
    OTHER_OPTION_ID,
    PLAN_APPROVAL_TITLE,
    build_ask_question_answers,
    build_ask_question_cancelled,
    build_question_choices,
    multi_select_prompt,
    parse_ask_question_params,
    parse_questionnaire_meta,
    plan_prompt_text,
    resolve_question_progress,
)
from pulse.prompts.approval import answer_needs_description
from pulse.prompts.permission import (
    PermissionPolicy,
    build_permission_choices,
    decide_permission,
    permission_cancelled,
    permission_prompt_text,
    permission_selected,
)
from pulse.prompts.text_questionnaire import (
    TextQuestion,
    TextQuestionnaire,
    format_questionnaire_answers,
    parse_text_questionnaire,
)


class PromptKind(str, Enum):
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    TEXT = "text"
    CONFIRM = "confirm"


@dataclass
class PromptRequest:
    kind: PromptKind
    title: str
    prompt: str
    choices: list[tuple[str, str]]
    default: str | bool | None = None
    future: Future[Any] | None = None


def format_prompt_reply(request: PromptRequest, result: object | None) -> str:
    if result is None:
        return "Cancelado"
    if request.kind == PromptKind.CONFIRM:
        return "Sim" if result else "Não"
    if request.kind == PromptKind.TEXT:
        text = str(result).strip()
        return text or "—"
    lookup = {str(option_id): label for option_id, label in request.choices}
    if request.kind == PromptKind.MULTI_SELECT:
        selected = result if isinstance(result, list) else []
        labels = [lookup.get(str(item), str(item)) for item in selected]
        return ", ".join(labels) if labels else "—"
    return lookup.get(str(result), str(result))


class PromptAbandoned(Exception):
    """A tela largou a pergunta sem respondê-la. Ver [PromptBridge.abandon]."""


class PromptBridge:
    def __init__(self) -> None:
        self._queue: Queue[PromptRequest] = Queue()
        self._closed = False
        #: Largada por `abandon`: ninguém mais vai responder por esta ponte.
        self._abandoned = False
        #: Futures entregues e ainda não resolvidos — inclusive o da pergunta
        #: que já saiu da fila e está na tela, que `abandon` precisa alcançar.
        self._live: list[Future[Any]] = []

    def close(self) -> None:
        """Fecha a ponte cancelando o que estiver aberto. Para run que acabou."""
        self._closed = True
        for future in self._drain():
            future.set_result(None)

    def abandon(self) -> None:
        """Larga a ponte **sem** responder nada — o usuário só saiu da tela.

        Responder `None` significa "cancelado" para o agente, o que é certo
        quando a run acabou e errado quando ela continua no daemon esperando a
        pessoa voltar. Quem está bloqueado em `request` recebe `PromptAbandoned`
        em vez de uma resposta: a thread do stream morre, a pergunta não.
        Vale também para quem perguntar **depois**: devolver `None` ali seria
        responder "cancelado" em nome de uma tela que já não existe.
        """
        self._closed = True
        self._abandoned = True
        for future in self._drain():
            future.set_exception(PromptAbandoned())

    def _drain(self) -> list[Future[Any]]:
        """Todo future ainda de pé: o da pergunta na tela e os que esperam fila."""
        pending = [future for future in self._live if not future.done()]
        self._live.clear()
        while True:
            try:
                request = self._queue.get_nowait()
            except Empty:
                break
            if request.future is not None and not request.future.done():
                if request.future not in pending:
                    pending.append(request.future)
        return pending

    def poll(self) -> PromptRequest | None:
        try:
            return self._queue.get_nowait()
        except Empty:
            return None

    def request(
        self,
        kind: PromptKind,
        *,
        title: str,
        prompt: str,
        choices: list[tuple[str, str]] | None = None,
        default: str | bool | None = None,
        timeout: float | None = None,
    ) -> Any:
        if self._abandoned:
            raise PromptAbandoned()
        if self._closed:
            return None
        future: Future[Any] = Future()
        request = PromptRequest(
            kind=kind,
            title=title,
            prompt=prompt,
            choices=list(choices or []),
            default=default,
            future=future,
        )
        self._live.append(future)
        self._queue.put(request)
        try:
            return future.result(timeout=timeout)
        finally:
            if future in self._live:
                self._live.remove(future)

    def select(
        self,
        prompt: str,
        choices: list[tuple[str, str]],
        *,
        title: str = "",
    ) -> str | None:
        return self.request(
            PromptKind.SELECT,
            title=title,
            prompt=prompt,
            choices=choices,
        )

    def multi_select(
        self,
        prompt: str,
        choices: list[tuple[str, str]],
        *,
        title: str = "",
    ) -> list[str] | None:
        return self.request(
            PromptKind.MULTI_SELECT,
            title=title,
            prompt=prompt,
            choices=choices,
        )

    def text(self, prompt: str, *, title: str = "", default: str = "") -> str | None:
        return self.request(
            PromptKind.TEXT,
            title=title,
            prompt=prompt,
            default=default,
        )

    def confirm(self, prompt: str, *, title: str = "", default: bool = True) -> bool | None:
        return self.request(
            PromptKind.CONFIRM,
            title=title,
            prompt=prompt,
            default=default,
        )


class TextualPromptHandler:
    def __init__(self, bridge: PromptBridge) -> None:
        self._bridge = bridge

    def respond_to_ask_question(self, params: dict[str, Any]) -> dict[str, Any]:
        questions = parse_ask_question_params(params)
        if not questions:
            return build_ask_question_cancelled()

        meta = parse_questionnaire_meta(params)
        answers: list[dict[str, Any]] = []
        batch_size = len(questions)

        for position, question in enumerate(questions, start=1):
            result = self._ask_single_question(
                question,
                meta=meta,
                position=position,
                batch_size=batch_size,
            )
            if result is None:
                return build_ask_question_cancelled()
            answers.append(result)

        return build_ask_question_answers(answers)

    def run_text_questionnaire(self, text: str) -> str | None:
        questionnaire = parse_text_questionnaire(text)
        if questionnaire is None:
            return None
        return self.run_parsed_questionnaire(questionnaire)

    def run_parsed_questionnaire(self, questionnaire: TextQuestionnaire) -> str | None:
        meta = {"title": questionnaire.title}
        total = len(questionnaire.questions)
        collected: list[tuple[TextQuestion, str]] = []

        for position, question in enumerate(questionnaire.questions, start=1):
            question_payload = {
                "id": question.id,
                "prompt": question.prompt,
                "options": [
                    {"id": letter, "label": label}
                    for letter, label in question.options
                ],
            }
            result = self._ask_single_question(
                question_payload,
                meta=meta,
                position=position,
                batch_size=total,
            )
            if result is None:
                return None
            answer = self._format_answer(question, result)
            collected.append((question, answer))

        return format_questionnaire_answers(questionnaire, collected)

    def _format_answer(self, question: TextQuestion, result: dict[str, Any]) -> str:
        selected = result.get("selectedOptionIds", [])
        if not selected:
            return ""
        value = str(selected[0])
        if "::" in value:
            letter, detail = value.split("::", 1)
            for option_letter, label in question.options:
                if letter == option_letter:
                    return f"{letter}) {label} — {detail}"
            return f"{value.replace('::', ' — ')}"
        for letter, label in question.options:
            if value == letter:
                return f"{letter}) {label}"
        # Não casou com nenhuma letra: é o texto que o usuário escreveu em
        # "Outro". Marcado para não ser confundido com rótulo de opção.
        return f"{FREE_TEXT_ANSWER_PREFIX}{value}"

    def respond_to_create_plan(self, params: dict[str, Any]) -> dict[str, Any]:
        approved = self._bridge.confirm(
            plan_prompt_text(params),
            title=PLAN_APPROVAL_TITLE,
            default=True,
        )
        if approved is None:
            return {"outcome": {"outcome": "cancelled"}}
        if approved:
            return {"outcome": {"outcome": "accepted"}}
        return {"outcome": {"outcome": "rejected"}}

    def respond_to_permission(
        self,
        params: dict[str, Any],
        *,
        policy: PermissionPolicy,
        allow_terminal: bool = False,
    ) -> dict[str, Any]:
        permission = params.get("permission", {})
        if not isinstance(permission, dict):
            permission = {}
        options = params.get("options", [])
        if not isinstance(options, list):
            options = []

        # A política decide sozinha quando dá: a mesma função que o daemon usa
        # antes de publicar a pergunta. Aqui ela cobre o caminho direto (CLI,
        # teste) e o dock que reabre uma pergunta que sobrou de antes.
        decided = decide_permission(params, policy=policy, allow_terminal=allow_terminal)
        if decided is not None:
            return decided

        tool_call = params.get("toolCall", {})
        if not isinstance(tool_call, dict):
            tool_call = {}

        choices = build_permission_choices(options)
        selected = self._bridge.select(
            permission_prompt_text(permission, tool_call),
            choices,
            title="Permissão",
        )
        if selected is None:
            return permission_cancelled()
        return permission_selected(str(selected))

    def ask_text(self, prompt: str, *, title: str = "") -> str | None:
        answer = self._bridge.text(prompt, title=title)
        if answer is None:
            return None
        text = str(answer).strip()
        return text or None

    def select_choice(
        self,
        prompt: str,
        choices: list[tuple[str, Any]],
        *,
        title: str = "",
    ) -> Any | None:
        mapped = [(str(i), label) for i, (label, _) in enumerate(choices)]
        values = [value for _, value in choices]
        selected = self._bridge.select(prompt, mapped, title=title)
        if selected is None:
            return None
        try:
            index = int(selected)
        except ValueError:
            return None
        if index < 0 or index >= len(values):
            return None
        return values[index]

    def _ask_single_question(
        self,
        question: dict[str, Any],
        *,
        meta: dict[str, Any],
        position: int,
        batch_size: int,
    ) -> dict[str, Any] | None:
        question_id = str(question.get("id", ""))
        prompt = str(question.get("prompt", "Pergunta")).strip()
        options = question.get("options", [])
        allow_multiple = bool(
            question.get("allow_multiple", question.get("allowMultiple", False))
        )
        index, total = resolve_question_progress(
            question=question,
            position=position,
            batch_size=batch_size,
            meta=meta,
        )
        title = str(meta.get("title") or "").strip() or DEFAULT_QUESTIONNAIRE_TITLE
        if index is not None and total is not None:
            title = f"{title} · {index}/{total}"

        if not isinstance(options, list) or not options:
            free_text = self._bridge.text(prompt, title=title)
            if free_text is None:
                return None
            return {
                "questionId": question_id,
                "selectedOptionIds": [free_text.strip()],
            }

        choices = build_question_choices(options, prompt=prompt)
        if not choices:
            return None

        select_prompt = prompt
        if allow_multiple:
            select_prompt = multi_select_prompt(prompt)
            selected_ids = self._bridge.multi_select(select_prompt, choices, title=title)
            if selected_ids is None:
                return None
            if OTHER_OPTION_ID in selected_ids:
                custom = self._prompt_other_text(prompt, title=title)
                if custom is None:
                    return None
                selected_ids = [
                    custom if item == OTHER_OPTION_ID else item for item in selected_ids
                ]
            if not selected_ids:
                return self._ask_single_question(
                    question,
                    meta=meta,
                    position=position,
                    batch_size=batch_size,
                )
            return {"questionId": question_id, "selectedOptionIds": selected_ids}

        selected = self._bridge.select(select_prompt, choices, title=title)
        if selected is None:
            return None

        if str(selected) == OTHER_OPTION_ID:
            custom = self._prompt_other_text(prompt, title=title)
            if custom is None:
                return None
            return {"questionId": question_id, "selectedOptionIds": [custom]}

        selected_id = str(selected)
        selected_label = self._choice_label(choices, selected_id)
        if selected_label and answer_needs_description(
            prompt=prompt, label=selected_label
        ):
            custom = self._prompt_follow_up_text(prompt, selected_label, title=title)
            if custom is None:
                return None
            return {
                "questionId": question_id,
                "selectedOptionIds": [f"{selected_id}::{custom}"],
            }

        return {"questionId": question_id, "selectedOptionIds": [selected_id]}

    @staticmethod
    def _choice_label(choices: list[tuple[str, str]], selected_id: str) -> str | None:
        for option_id, label in choices:
            if option_id == selected_id:
                return label
        return None

    def _prompt_follow_up_text(self, prompt: str, option_label: str, *, title: str) -> str | None:
        value = self._bridge.text(f"{prompt}\n[{option_label}]", title=title)
        if value is None:
            return None
        value = value.strip()
        if not value:
            return self._prompt_follow_up_text(prompt, option_label, title=title)
        return value

    def _prompt_other_text(self, prompt: str, *, title: str) -> str | None:
        value = self._bridge.text(f"{prompt}\n[Outro — descreva]", title=title)
        if value is None:
            return None
        value = value.strip()
        if not value:
            return self._prompt_other_text(prompt, title=title)
        return value
