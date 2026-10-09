from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from enum import StrEnum
from queue import Empty, Queue

from pulse.domain.ports import Choice, JsonObject
from pulse.replies.acp_payloads import (
    AskQuestionRequest,
    PermissionRequest,
    Question,
    QuestionAnswer,
    QuestionnaireMeta,
    QuestionOption,
)
from pulse.replies.approval import answer_needs_description
from pulse.replies.ask_question import (
    OTHER_OPTION_ID,
    build_ask_question_answers,
    build_ask_question_cancelled,
    build_question_choices,
    multi_select_prompt,
    plan_prompt_text,
    resolve_question_progress,
)
from pulse.replies.permission import (
    build_permission_choices,
    decide_permission,
    parse_policy,
    permission_cancelled,
    permission_prompt_text,
    permission_selected,
)
from pulse.replies.text_questionnaire import (
    TextQuestion,
    TextQuestionnaire,
    format_questionnaire_answers,
    parse_text_questionnaire,
)
from pulse.replies.wording import (
    DEFAULT_QUESTIONNAIRE_TITLE,
    FREE_TEXT_ANSWER_PREFIX,
    PLAN_APPROVAL_TITLE,
)
from pulse.tui import strings


class PromptKind(StrEnum):
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
    future: Future[object] | None = None


def format_prompt_reply(request: PromptRequest, result: object | None) -> str:
    if result is None:
        return strings.CANCELLED
    if request.kind == PromptKind.CONFIRM:
        return strings.YES if result else strings.NO
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
    """The screen dropped the question without answering it. See [PromptBridge.abandon]."""


class PromptBridge:
    def __init__(self) -> None:
        self._queue: Queue[PromptRequest] = Queue()
        self._closed = False
        self._abandoned = False
        self._live: list[Future[object]] = []

    def close(self) -> None:
        """Close the bridge, cancelling anything open. Used when the run has ended."""
        self._closed = True
        for future in self._drain():
            future.set_result(None)

    def abandon(self) -> None:
        """Drop the bridge **without** answering; the user only left the screen.

        Answering `None` means "cancelled" to the agent, which is wrong while the
        run keeps waiting in the daemon. Callers blocked in `request` (now or
        later) get `PromptAbandoned` instead, so the stream thread dies but the
        question survives.
        """
        self._closed = True
        self._abandoned = True
        for future in self._drain():
            future.set_exception(PromptAbandoned())

    def _drain(self) -> list[Future[object]]:
        """Every pending future: the on-screen question and those still queued."""
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

    def poll(self, timeout: float | None = None) -> PromptRequest | None:
        """The next queued question; with `timeout`, wait up to that long for one."""
        try:
            return self._queue.get(block=timeout is not None, timeout=timeout)
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
    ) -> object:
        if self._abandoned:
            raise PromptAbandoned()
        if self._closed:
            return None
        future: Future[object] = Future()
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
        answer = self.request(
            PromptKind.SELECT,
            title=title,
            prompt=prompt,
            choices=choices,
        )
        return None if answer is None else str(answer)

    def multi_select(
        self,
        prompt: str,
        choices: list[tuple[str, str]],
        *,
        title: str = "",
    ) -> list[str] | None:
        answer = self.request(
            PromptKind.MULTI_SELECT,
            title=title,
            prompt=prompt,
            choices=choices,
        )
        return [str(item) for item in answer] if isinstance(answer, list) else None

    def text(self, prompt: str, *, title: str = "", default: str = "") -> str | None:
        answer = self.request(
            PromptKind.TEXT,
            title=title,
            prompt=prompt,
            default=default,
        )
        return None if answer is None else str(answer)

    def confirm(self, prompt: str, *, title: str = "", default: bool = True) -> bool | None:
        answer = self.request(
            PromptKind.CONFIRM,
            title=title,
            prompt=prompt,
            default=default,
        )
        return None if answer is None else bool(answer)


def _as_question(question: TextQuestion) -> Question:
    """A question of the text block, asked through the same dock as `AskQuestion`."""
    options = tuple(QuestionOption(id=letter, label=label) for letter, label in question.options)
    return Question(id=question.id, prompt=question.prompt, options=options or None)


def _first_label(question: TextQuestion, letter: str) -> str | None:
    return next((label for option, label in question.options if option == letter), None)


class TextualPromptHandler:
    def __init__(self, bridge: PromptBridge) -> None:
        self._bridge = bridge

    def respond_to_ask_question(self, params: JsonObject) -> JsonObject:
        request = AskQuestionRequest.parse(params)
        if not request.questions:
            return build_ask_question_cancelled()

        answers: list[QuestionAnswer] = []
        batch_size = len(request.questions)
        for position, question in enumerate(request.questions, start=1):
            answer = self._ask_single_question(
                question,
                meta=request.meta,
                position=position,
                batch_size=batch_size,
            )
            if answer is None:
                return build_ask_question_cancelled()
            answers.append(answer)

        return build_ask_question_answers(answers)

    def run_text_questionnaire(self, text: str) -> str | None:
        questionnaire = parse_text_questionnaire(text)
        if questionnaire is None:
            return None
        return self.run_parsed_questionnaire(questionnaire)

    def run_parsed_questionnaire(self, questionnaire: TextQuestionnaire) -> str | None:
        meta = QuestionnaireMeta(title=questionnaire.title.strip())
        total = len(questionnaire.questions)
        collected: list[tuple[TextQuestion, str]] = []

        for position, question in enumerate(questionnaire.questions, start=1):
            answer = self._ask_single_question(
                _as_question(question),
                meta=meta,
                position=position,
                batch_size=total,
            )
            if answer is None:
                return None
            collected.append((question, self._format_answer(question, answer)))

        return format_questionnaire_answers(questionnaire, collected)

    @staticmethod
    def _format_answer(question: TextQuestion, answer: QuestionAnswer) -> str:
        if not answer.selected_option_ids:
            return ""
        value = answer.selected_option_ids[0]
        letter, separator, detail = value.partition("::")
        label = _first_label(question, letter)
        if separator:
            return value.replace("::", " — ") if label is None else f"{letter}) {label} — {detail}"
        if label is not None:
            return f"{letter}) {label}"
        return f"{FREE_TEXT_ANSWER_PREFIX}{value}"

    def respond_to_create_plan(self, params: JsonObject) -> JsonObject:
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
        params: JsonObject,
        *,
        policy: str,
        allow_terminal: bool = False,
    ) -> JsonObject:
        decided = decide_permission(
            params, policy=parse_policy(policy), allow_terminal=allow_terminal
        )
        if decided is not None:
            return decided

        request = PermissionRequest.parse(params)
        selected = self._bridge.select(
            permission_prompt_text(request),
            build_permission_choices(request.options),
            title=strings.PERMISSION_TITLE,
        )
        if selected is None:
            return permission_cancelled()
        return permission_selected(selected)

    def ask_text(self, prompt: str, *, title: str = "") -> str | None:
        answer = self._bridge.text(prompt, title=title)
        if answer is None:
            return None
        text = answer.strip()
        return text or None

    def select_choice(
        self,
        prompt: str,
        choices: list[tuple[str, Choice]],
        *,
        title: str = "",
    ) -> Choice | None:
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
        question: Question,
        *,
        meta: QuestionnaireMeta,
        position: int,
        batch_size: int,
    ) -> QuestionAnswer | None:
        prompt = question.prompt or strings.QUESTION
        index, total = resolve_question_progress(
            question=question, position=position, batch_size=batch_size, meta=meta
        )
        title = meta.title or DEFAULT_QUESTIONNAIRE_TITLE
        if index is not None and total is not None:
            title = f"{title} · {index}/{total}"

        if question.options is None:
            free_text = self._bridge.text(prompt, title=title)
            if free_text is None:
                return None
            return QuestionAnswer(question.id, (free_text.strip(),))

        choices = build_question_choices(question.options, prompt=prompt)
        if not choices:
            return None
        ask = self._ask_many if question.allow_multiple else self._ask_one
        selected = ask(prompt, choices, title=title)
        return None if selected is None else QuestionAnswer(question.id, selected)

    def _ask_many(
        self, prompt: str, choices: list[tuple[str, str]], *, title: str
    ) -> tuple[str, ...] | None:
        """Picked ids, the "Other" pick replaced by what was typed; asks again on an empty pick."""
        while True:
            selected = self._bridge.multi_select(multi_select_prompt(prompt), choices, title=title)
            if selected is None:
                return None
            if OTHER_OPTION_ID in selected:
                custom = self._prompt_other_text(prompt, title=title)
                if custom is None:
                    return None
                selected = [custom if item == OTHER_OPTION_ID else item for item in selected]
            if selected:
                return tuple(selected)

    def _ask_one(
        self, prompt: str, choices: list[tuple[str, str]], *, title: str
    ) -> tuple[str, ...] | None:
        """The picked id, `id::text` when the choice wants a description, or the typed "Other"."""
        selected = self._bridge.select(prompt, choices, title=title)
        if selected is None:
            return None
        if selected == OTHER_OPTION_ID:
            custom = self._prompt_other_text(prompt, title=title)
            return None if custom is None else (custom,)

        label = self._choice_label(choices, selected)
        if label and answer_needs_description(prompt=prompt, label=label):
            detail = self._prompt_follow_up_text(prompt, label, title=title)
            return None if detail is None else (f"{selected}::{detail}",)
        return (selected,)

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
        value = self._bridge.text(strings.OTHER_OPTION_PROMPT.format(prompt=prompt), title=title)
        if value is None:
            return None
        value = value.strip()
        if not value:
            return self._prompt_other_text(prompt, title=title)
        return value
