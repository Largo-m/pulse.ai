"""Properties of the parsers that read agent payloads.

ACP JSON and the agent's text are untrusted: whatever the agent sends, parsing
must not crash the run, and must never turn into a decision the policy did not
take. Well-formed input, on the other hand, must come through intact, or the
user answers a question the agent did not ask.
"""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from pulse.replies.acp_payloads import (
    AskQuestionRequest,
    PermissionRequest,
    QuestionOption,
)
from pulse.replies.ask_question import (
    OTHER_OPTION_ID,
    build_question_choices,
    is_other_option,
    plan_prompt_text,
)
from pulse.replies.permission import (
    PermissionPolicy,
    build_permission_choices,
    decide_permission,
    permission_prompt_text,
)
from pulse.replies.text_questionnaire import (
    TextQuestion,
    TextQuestionnaire,
    format_questionnaire_answers,
    parse_text_questionnaire,
    questionnaire_from_payload,
    serialize_questionnaire,
    split_questionnaire_answers,
)

_KNOWN_KEYS = (
    "questions",
    "options",
    "permission",
    "toolCall",
    "kind",
    "title",
    "description",
    "prompt",
    "id",
    "label",
    "name",
    "optionId",
    "allow_multiple",
    "allowMultiple",
    "index",
    "questionIndex",
    "totalQuestions",
    "total_questions",
    "question_index",
    "raw",
    "letter",
    "overview",
    "plan",
)

_scalars = st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=12)
_keys = st.sampled_from(_KNOWN_KEYS) | st.text(max_size=8)
json_values = st.recursive(
    _scalars,
    lambda children: st.lists(children, max_size=4) | st.dictionaries(_keys, children, max_size=5),
    max_leaves=25,
)
json_objects = st.dictionaries(_keys, json_values, max_size=6)

_POLICIES: tuple[PermissionPolicy, ...] = ("ask", "auto_approve", "deny_writes")
_TERMINAL_KINDS = st.sampled_from(["terminal", "shell", "bash", "run_command", "Bash"])
_word = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10)
_phrase = st.lists(_word, min_size=1, max_size=5).map(" ".join)
_permission_kinds = st.sampled_from(
    ["allow_once", "allow_always", "reject_once", "reject_always", "other"]
)


@given(json_objects)
def test_any_json_reads_as_a_well_typed_ask_question(params: dict[str, object]) -> None:
    """A garbled `AskQuestion` must become a typed request, never a crash in the run."""
    request = AskQuestionRequest.parse(params)

    for question in request.questions:
        assert isinstance(question.id, str)
        assert question.prompt == question.prompt.strip()
        assert isinstance(question.allow_multiple, bool)
        assert question.index is None or question.index > 0
        assert question.total is None or question.total > 0
        for option in question.options or ():
            assert isinstance(option.id, str)
            assert isinstance(option.label, str)
        build_question_choices(question.options or (), prompt=question.prompt)
    assert request.meta.index is None or request.meta.index > 0
    assert request.meta.total is None or request.meta.total > 0
    assert isinstance(plan_prompt_text(params), str)


@given(json_objects)
def test_any_json_reads_as_a_permission_with_choices_to_show(params: dict[str, object]) -> None:
    """Even an unreadable permission must still offer the user something to pick."""
    request = PermissionRequest.parse(params)

    assert request.kind == request.kind.lower()
    assert permission_prompt_text(request)
    choices = build_permission_choices(request.options)
    assert choices
    assert all(option_id for option_id, _ in choices)


@given(json_objects, st.sampled_from(_POLICIES), st.booleans())
def test_any_json_gets_either_no_decision_or_a_selected_option(
    params: dict[str, object], policy: PermissionPolicy, allow_terminal: bool
) -> None:
    """The policy answer is always a well-formed ACP `selected` outcome, or a question."""
    decided = decide_permission(params, policy=policy, allow_terminal=allow_terminal)

    if decided is not None:
        outcome = decided["outcome"]
        assert isinstance(outcome, dict)
        assert outcome["outcome"] == "selected"
        assert isinstance(outcome["optionId"], str)
        assert outcome["optionId"]


def _permission_params(kind: str, options: list[tuple[str, str]]) -> dict[str, object]:
    return {
        "toolCall": {"kind": kind},
        "options": [
            {"optionId": option_id, "kind": option_kind} for option_id, option_kind in options
        ],
    }


_option_lists = st.lists(st.tuples(_word, _permission_kinds), max_size=5)


@given(_TERMINAL_KINDS, _option_lists, st.sampled_from(_POLICIES))
def test_a_terminal_is_never_allowed_unless_the_step_allows_it(
    kind: str, options: list[tuple[str, str]], policy: PermissionPolicy
) -> None:
    """A kind naming a terminal or shell is vetoed under any policy unless `allow_terminal`."""
    decided = decide_permission(_permission_params(kind, options), policy=policy)

    assert decided is not None
    outcome = decided["outcome"]
    assert isinstance(outcome, dict)
    rejecting = {
        option_id for option_id, option_kind in options if option_kind.startswith("reject")
    }
    assert outcome["optionId"] in rejecting | {"reject-once"}


@given(_option_lists, st.sampled_from(_POLICIES))
def test_execute_runs_alone_only_under_auto_approve(
    options: list[tuple[str, str]], policy: PermissionPolicy
) -> None:
    """`execute` is the agent's own shell (Claude's Bash), not a terminal Pulse runs.

    Only `auto_approve` lets it run unasked; `ask` and `deny_writes` leave it to
    a person, since only whoever reads the command knows whether it writes.
    """
    decided = decide_permission(_permission_params("execute", options), policy=policy)

    if policy != "auto_approve":
        assert decided is None
        return
    assert decided is not None
    outcome = decided["outcome"]
    assert isinstance(outcome, dict)
    allowing = {option_id for option_id, option_kind in options if option_kind.startswith("allow")}
    assert outcome["optionId"] in allowing | {"allow-once"}


@given(_word, _option_lists)
def test_ask_never_decides_for_the_user(kind: str, options: list[tuple[str, str]]) -> None:
    """Under `ask` with the terminal allowed, every request reaches a person."""
    params = _permission_params(kind, options)

    assert decide_permission(params, policy="ask", allow_terminal=True) is None


@given(_word, _option_lists)
def test_deny_writes_asks_when_the_kind_does_not_say_it_is_safe(
    kind: str, options: list[tuple[str, str]]
) -> None:
    """Deny by default when unsure: an unknown kind under `deny_writes` is a question."""
    known = {"read", "search", "fetch", "think", "edit", "delete", "move"}
    markers = ("write", "terminal", "shell", "bash", "command")
    assume(kind not in known and not any(marker in kind for marker in markers))

    assert decide_permission(_permission_params(kind, options), policy="deny_writes") is None


@given(_option_lists)
def test_permission_options_come_back_in_order(options: list[tuple[str, str]]) -> None:
    """The dock must offer exactly the options the agent sent, in the agent's order."""
    request = PermissionRequest.parse(_permission_params("edit", options))

    assert [(option.option_id, option.kind) for option in request.options] == options
    if options:
        assert [option_id for option_id, _ in build_permission_choices(request.options)] == [
            option_id for option_id, _ in options
        ]


@given(st.lists(st.tuples(_word, _phrase), min_size=1, max_size=6))
def test_ask_question_options_come_back_with_their_ids_and_order(
    options: list[tuple[str, str]],
) -> None:
    """The answer names an option id; a reordered or renamed option answers the wrong thing."""
    params = {
        "questions": [
            {
                "id": "q1",
                "prompt": "Which one?",
                "options": [{"id": option_id, "label": label} for option_id, label in options],
            }
        ]
    }
    question = AskQuestionRequest.parse(params).questions[0]

    assert question.options == tuple(QuestionOption(id=i, label=label) for i, label in options)
    choices = build_question_choices(question.options or (), prompt=question.prompt)
    expected = [
        OTHER_OPTION_ID if is_other_option(option_id, label) else option_id
        for option_id, label in options
    ]
    assert [option_id for option_id, _ in choices][: len(options)] == expected


@given(st.text(max_size=400))
def test_any_text_parses_to_nothing_or_to_numbered_questions(text: str) -> None:
    """The agent's free speech must never crash the parser nor invent unnumbered questions."""
    questionnaire = parse_text_questionnaire(text)

    if questionnaire is not None:
        assert questionnaire.questions
        for question in questionnaire.questions:
            number = question.id.removeprefix("q")
            assert number.isdigit()
            assert question.prompt.startswith(f"{number}. ")


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ABC)\n`", max_size=400))
def test_text_without_numbered_lines_is_not_a_questionnaire(text: str) -> None:
    """With no `1.` line there is nothing to ask, whatever else the text looks like."""
    assert parse_text_questionnaire(text) is None


_letters = "ABCDEFGHIJ"
_questions = st.lists(
    st.tuples(_phrase, st.lists(_phrase, min_size=1, max_size=len(_letters))),
    min_size=1,
    max_size=5,
)


def _block(questions: list[tuple[str, list[str]]]) -> str:
    lines = ["```text", "Preciso de algumas informações antes de continuar."]
    for number, (prompt, labels) in enumerate(questions, start=1):
        lines.append(f"{number}. {prompt}")
        lines.extend(f"{_letters[i]}) {label}" for i, label in enumerate(labels))
    lines.append("```")
    return "Some speech first.\n\n" + "\n".join(lines)


def _expected(questions: list[tuple[str, list[str]]]) -> tuple[TextQuestion, ...]:
    return tuple(
        TextQuestion(
            id=f"q{number}",
            prompt=f"{number}. {prompt}",
            options=tuple((_letters[i], label) for i, label in enumerate(labels)),
        )
        for number, (prompt, labels) in enumerate(questions, start=1)
    )


@given(_questions)
def test_a_well_formed_block_keeps_every_question_and_option(
    questions: list[tuple[str, list[str]]],
) -> None:
    """A dropped or merged question would let the run advance on an answer never given."""
    questionnaire = parse_text_questionnaire(_block(questions))

    assert questionnaire is not None
    assert questionnaire.questions == _expected(questions)


@given(_questions)
def test_a_questionnaire_survives_the_trip_to_the_client(
    questions: list[tuple[str, list[str]]],
) -> None:
    """The daemon serializes the questionnaire; the client must rebuild the same questions."""
    original = TextQuestionnaire(title="Title", questions=_expected(questions))
    payload = serialize_questionnaire(original)
    payload.pop("raw")

    restored = questionnaire_from_payload(payload)

    assert restored is not None
    assert restored.questions == original.questions
    assert restored.title == "Title"


@given(json_objects)
def test_any_json_payload_rebuilds_a_questionnaire_or_nothing(payload: dict[str, object]) -> None:
    """A garbled questionnaire payload must fall back to the agent text, not crash the client."""
    restored = questionnaire_from_payload(payload)

    if restored is not None:
        assert restored.title
        assert all(question.prompt for question in restored.questions)


@given(_questions, st.data())
def test_answers_split_back_into_their_questions(
    questions: list[tuple[str, list[str]]], data: st.DataObject
) -> None:
    """The history rebuilds each Q/A pair from the combined answer text."""
    questionnaire = TextQuestionnaire(title="Title", questions=_expected(questions))
    answers = [data.draw(_phrase) for _ in questionnaire.questions]

    text = format_questionnaire_answers(
        questionnaire, list(zip(questionnaire.questions, answers, strict=True))
    )

    assert split_questionnaire_answers(questionnaire, text) == [
        (question.prompt, answer)
        for question, answer in zip(questionnaire.questions, answers, strict=True)
    ]
