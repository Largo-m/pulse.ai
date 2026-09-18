from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from enum import Enum
from queue import Empty, Queue
from typing import Any

from rich.console import Console

from pulse.presentation.prompt.ask_question import (
    DEFAULT_QUESTIONNAIRE_TITLE,
    OTHER_OPTION_ID,
    build_ask_question_answers,
    build_ask_question_cancelled,
    format_option_label,
    is_other_option,
    option_requires_description,
    parse_ask_question_params,
    parse_questionnaire_meta,
    resolve_question_progress,
    should_add_other_option,
)
from pulse.presentation.prompt.handler import (
    PermissionPolicy,
    _permission_cancelled,
    _permission_selected,
    _pick_permission_option,
)
from pulse.presentation.prompt.text_questionnaire import (
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


_PERMISSION_KIND_LABELS = {
    "allow_once": "Permitir esta vez",
    "allow_always": "Sempre permitir",
    "reject_once": "Recusar",
    "reject_always": "Sempre recusar",
}


def _permission_choice_label(option: dict[str, Any]) -> str:
    name = str(option.get("name") or option.get("label") or "").strip()
    if name:
        return name
    kind = str(option.get("kind", "")).lower().replace("-", "_")
    return _PERMISSION_KIND_LABELS.get(kind, kind.replace("_", " ").strip() or "Opção")


def build_permission_choices(options: list[Any]) -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    index = 0
    for option in options:
        if not isinstance(option, dict):
            continue
        option_id = str(option.get("optionId") or option.get("id") or "")
        if not option_id:
            continue
        label = format_option_label(index, _permission_choice_label(option))
        choices.append((option_id, label))
        index += 1
    if not choices:
        return [
            ("allow-once", format_option_label(0, "Permitir esta vez")),
            ("reject-once", format_option_label(1, "Recusar")),
        ]
    return choices


def _permission_prompt_text(permission: dict[str, Any], tool_call: dict[str, Any]) -> str:
    title = str(permission.get("title") or "").strip()
    description = str(permission.get("description") or "").strip()
    tool_title = str(tool_call.get("title") or "").strip()
    parts: list[str] = []
    for part in (title, description, tool_title):
        if part and part not in parts:
            parts.append(part)
    if not parts:
        return "O agente pede permissão para continuar."
    return "\n".join(parts)


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


class PromptBridge:
    def __init__(self) -> None:
        self._queue: Queue[PromptRequest] = Queue()
        self._closed = False

    def close(self) -> None:
        self._closed = True
        while True:
            try:
                request = self._queue.get_nowait()
            except Empty:
                break
            if request.future is not None and not request.future.done():
                request.future.set_result(None)

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
        self._queue.put(request)
        return future.result(timeout=timeout)

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
    def __init__(self, bridge: PromptBridge, *, console: Console | None = None) -> None:
        self._bridge = bridge
        self._console = console or Console(highlight=False, soft_wrap=True)

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
        return value

    def respond_to_create_plan(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "Plano").strip()
        overview = str(params.get("overview") or "").strip()
        plan = str(params.get("plan") or "").strip()
        body = name
        if overview:
            body = f"{body}\n{overview}"
        if plan:
            body = f"{body}\n\n{plan[:1200]}"
        approved = self._bridge.confirm(body, title="Aprovar plano?", default=True)
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

        kind = str(permission.get("kind", "")).lower()
        tool_call = params.get("toolCall", {})
        if not isinstance(tool_call, dict):
            tool_call = {}
        kind = kind or str(tool_call.get("kind", "")).lower()

        if not allow_terminal and (
            "terminal" in kind or "shell" in kind or "bash" in kind or "command" in kind
        ):
            option_id = _pick_permission_option(options, prefer="reject") or "reject-once"
            return _permission_selected(option_id)

        if policy == "auto_approve":
            option_id = _pick_permission_option(options, prefer="allow") or "allow-once"
            return _permission_selected(option_id)

        if policy == "deny_writes":
            if "write" in kind or "edit" in kind:
                option_id = _pick_permission_option(options, prefer="reject") or "reject-once"
                return _permission_selected(option_id)
            option_id = _pick_permission_option(options, prefer="allow") or "allow-once"
            return _permission_selected(option_id)

        choices = build_permission_choices(options)
        selected = self._bridge.select(
            _permission_prompt_text(permission, tool_call),
            choices,
            title="Permissão",
        )
        if selected is None:
            return _permission_cancelled()
        return _permission_selected(str(selected))

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

        choices = self._build_choices(options, prompt=prompt)
        if not choices:
            return None

        select_prompt = prompt
        if allow_multiple:
            select_prompt = f"{prompt}\n(escolha uma ou mais)"
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
        if selected_label and option_requires_description(selected_label):
            custom = self._prompt_follow_up_text(prompt, selected_label, title=title)
            if custom is None:
                return None
            return {
                "questionId": question_id,
                "selectedOptionIds": [f"{selected_id}::{custom}"],
            }

        return {"questionId": question_id, "selectedOptionIds": [selected_id]}

    def _build_choices(self, options: list[Any], *, prompt: str = "") -> list[tuple[str, str]]:
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
