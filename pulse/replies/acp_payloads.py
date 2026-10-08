"""The ACP request payloads Pulse reads, parsed once at the boundary.

ACP JSON comes from the agent, so it is untrusted input. Each parser takes the
raw object, keeps only the fields Pulse understands and drops or defaults the
rest, so the code that decides what to show or answer never touches an
unchecked `dict`. A parser never raises on malformed input: a field it cannot
read is absent, and absent fields always lead to the safer answer (ask a person).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pulse.domain import ui_text
from pulse.domain.ports import JsonObject

_EMPTY: Mapping[str, object] = {}


def mapping_of(value: object) -> Mapping[str, object]:
    """`value` when it is a JSON object, else an empty one."""
    return value if isinstance(value, Mapping) else _EMPTY


def items_of(value: object) -> Sequence[object]:
    """`value` when it is a JSON array, else an empty one."""
    return value if isinstance(value, (list, tuple)) else ()


def text_of(value: object) -> str:
    """A JSON scalar as text; `null` and a missing field read as blank."""
    return "" if value is None else str(value)


def truthy_text(value: object) -> str:
    """Like `text_of`, but any falsy value (`0`, `false`, `""`) is blank too."""
    return str(value) if value else ""


def first_present(payload: Mapping[str, object], *keys: str) -> object:
    """The value of the first key the payload has, for fields ACP spells two ways."""
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def positive_int(value: object) -> int | None:
    """A 1-based counter. `true` is not a number here, even though Python says it is."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


@dataclass(frozen=True)
class QuestionOption:
    id: str
    label: str

    @classmethod
    def parse(cls, raw: object) -> QuestionOption | None:
        if not isinstance(raw, Mapping):
            return None
        option_id = text_of(first_present(raw, "id", "label"))
        label = text_of(raw["label"]) if "label" in raw else option_id
        return cls(id=option_id, label=label)


@dataclass(frozen=True)
class Question:
    """One `AskQuestion` question.

    `options is None` means the agent offered no list, so the answer is free
    text; an empty tuple means it sent a list Pulse could not read.
    """

    id: str
    prompt: str
    options: tuple[QuestionOption, ...] | None = None
    allow_multiple: bool = False
    index: int | None = None
    total: int | None = None

    @classmethod
    def parse(cls, raw: Mapping[str, object]) -> Question:
        return cls(
            id=text_of(raw.get("id")),
            prompt=text_of(raw.get("prompt")).strip(),
            options=_parse_question_options(raw.get("options")),
            allow_multiple=bool(first_present(raw, "allow_multiple", "allowMultiple")),
            index=positive_int(first_present(raw, "index", "questionIndex")),
            total=positive_int(first_present(raw, "totalQuestions", "total_questions")),
        )


def _parse_question_options(raw: object) -> tuple[QuestionOption, ...] | None:
    entries = items_of(raw)
    if not entries:
        return None
    parsed = (QuestionOption.parse(entry) for entry in entries)
    return tuple(option for option in parsed if option is not None)


@dataclass(frozen=True)
class QuestionnaireMeta:
    """Where a question sits in the agent's questionnaire, for the dock title."""

    title: str = ""
    total: int | None = None
    index: int | None = None

    @classmethod
    def parse(cls, params: Mapping[str, object]) -> QuestionnaireMeta:
        return cls(
            title=text_of(params.get("title")).strip(),
            total=positive_int(first_present(params, "totalQuestions", "total_questions")),
            index=positive_int(first_present(params, "questionIndex", "question_index")),
        )


@dataclass(frozen=True)
class AskQuestionRequest:
    questions: tuple[Question, ...]
    meta: QuestionnaireMeta

    @classmethod
    def parse(cls, params: Mapping[str, object]) -> AskQuestionRequest:
        questions = tuple(
            Question.parse(entry)
            for entry in items_of(params.get("questions"))
            if isinstance(entry, Mapping)
        )
        return cls(questions=questions, meta=QuestionnaireMeta.parse(params))


@dataclass(frozen=True)
class QuestionAnswer:
    question_id: str
    selected_option_ids: tuple[str, ...]

    def to_wire(self) -> JsonObject:
        return {"questionId": self.question_id, "selectedOptionIds": list(self.selected_option_ids)}


@dataclass(frozen=True)
class PermissionOption:
    """One option of `session/request_permission`.

    `option_id` is the ACP `optionId`, the only id policy picks on its own;
    `choice_id` also accepts `id`, so a person still sees and can pick an
    option an agent named the non-standard way.
    """

    option_id: str
    choice_id: str
    kind: str
    name: str

    @classmethod
    def parse(cls, raw: object) -> PermissionOption | None:
        if not isinstance(raw, Mapping):
            return None
        return cls(
            option_id=text_of(raw.get("optionId")),
            choice_id=truthy_text(raw.get("optionId") or raw.get("id")),
            kind=text_of(raw.get("kind")),
            name=truthy_text(raw.get("name") or raw.get("label")).strip(),
        )

    def label(self) -> str:
        if self.name:
            return self.name
        kind = self.kind.lower().replace("-", "_")
        return ui_text.PERMISSION_KIND_LABELS.get(
            kind, kind.replace("_", " ").strip() or ui_text.OPTION_FALLBACK
        )


@dataclass(frozen=True)
class PermissionRequest:
    """What the agent wants to do (`kind`, as ACP names it) and the options it offers."""

    kind: str
    options: tuple[PermissionOption, ...]
    title: str
    description: str
    tool_title: str

    @classmethod
    def parse(cls, params: Mapping[str, object]) -> PermissionRequest:
        permission = mapping_of(params.get("permission"))
        tool_call = mapping_of(params.get("toolCall"))
        parsed = (PermissionOption.parse(entry) for entry in items_of(params.get("options")))
        return cls(
            kind=text_of(permission.get("kind")).lower() or text_of(tool_call.get("kind")).lower(),
            options=tuple(option for option in parsed if option is not None),
            title=truthy_text(permission.get("title")).strip(),
            description=truthy_text(permission.get("description")).strip(),
            tool_title=truthy_text(tool_call.get("title")).strip(),
        )
