"""The run log the runner persists from `session/update`: what history shows later.

History must match what the cockpit showed live: the agent's speech as one row
per stretch, tool calls labeled like the screen, the files the agent wrote as
artifacts, and the dialogs the user answered. Rows are asserted in SQLite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pulse.acp.session_runner import AcpSessionRunner
from pulse.domain import ui_text
from pulse.domain.ports import NullPromptPort
from pulse.domain.run import StepRecord
from pulse.store import runs as run_store
from tests.conftest import make_workflow
from tests.fakes import RecordingStream

RUN_ID = "run-1"
QUESTIONNAIRE = "```text\n1. Approve?\nA) Aprovar\nB) Ajustar\n```"


class _Port(NullPromptPort):
    def ask_text(self, prompt: str, *, title: str = "") -> str:
        return "start with the signup"


@pytest.fixture
def runner(tmp_path: Path) -> AcpSessionRunner:
    make_workflow("demo", steps=[("plan", "Plan")])
    run_store.create_run(
        run_id=RUN_ID,
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[StepRecord(step_id="plan", position=1, label="Plan")],
    )
    recorder = AcpSessionRunner(
        ["agent", "acp"],
        cwd=str(tmp_path),
        enable_mcp_ask=False,
        stream=RecordingStream(),
        prompt_handler=_Port(),
    )
    recorder.bind_run(RUN_ID)
    recorder._phase_id = "plan"
    recorder._session_id = "sess-1"
    return recorder


def _events() -> list[tuple[str, str, str]]:
    return [(row["kind"], row["title"], row["detail"]) for row in run_store.list_events(RUN_ID)]


def _chunk(text: str, kind: str = "text") -> dict[str, Any]:
    return {
        "update": {"sessionUpdate": "agent_message_chunk", "content": {"type": kind, "text": text}}
    }


def _tool(update_kind: str = "tool_call", **fields: Any) -> dict[str, Any]:
    return {"update": {"sessionUpdate": update_kind, **fields}}


def test_an_unbound_runner_records_nothing(tmp_path: Path):
    """Probes and doctor runs have no run to log to."""
    unbound = AcpSessionRunner(["agent", "acp"], cwd=str(tmp_path), enable_mcp_ask=False)

    unbound._record_run_event(_chunk("hello"))
    unbound._record_run_event(_tool(toolCallId="t-1", title="Run tests", kind="execute"))
    unbound._flush_text()

    assert unbound._text_buffer == []
    assert unbound._tool_payloads == {}


def test_speech_chunks_become_one_row_when_a_tool_call_interrupts_them(runner):
    """Streaming arrives word by word; history shows the paragraph, then the tool."""
    runner._record_run_event(_chunk("Reading "))
    runner._record_run_event(_chunk("the code."))
    runner._record_run_event(_tool(toolCallId="t-1", title="Run tests", kind="execute"))

    assert _events() == [
        ("Assistant", "Reading the code.", "Reading the code."),
        ("Tool", "Run tests", ""),
    ]
    rows = run_store.list_events(RUN_ID)
    assert [row["tool_id"] for row in rows] == ["", "t-1"]
    assert {row["acp_session_id"] for row in rows} == {"sess-1"}
    assert {row["step_id"] for row in rows} == {"plan"}


def test_a_long_speech_row_has_a_short_title_and_the_full_detail(runner):
    speech = "word " * 100

    runner._record_run_event(_chunk(speech))
    runner._flush_text()

    ((kind, title, detail),) = _events()
    assert kind == "Assistant"
    assert detail == speech.strip()
    assert title == speech.strip()[:160]


def test_non_text_and_empty_chunks_are_not_speech(runner):
    runner._record_run_event(_chunk("<img>", kind="image"))
    runner._record_run_event(_chunk(""))
    runner._record_run_event({"update": {"sessionUpdate": "agent_message_chunk", "content": "x"}})
    runner._flush_text()

    assert _events() == []


@pytest.mark.parametrize(
    "params",
    [
        {"update": "not an object"},
        {"update": {"sessionUpdate": "plan", "entries": []}},
        {"update": {"sessionUpdate": "available_commands_update"}},
    ],
)
def test_updates_that_are_neither_speech_nor_tools_are_not_logged(runner, params):
    runner._record_run_event(_chunk("pending speech"))

    runner._record_run_event(params)

    assert _events() == [], "a non-tool update must not even flush the pending speech"


def test_an_unlabeled_tool_call_shows_a_placeholder_until_its_label_arrives(runner):
    runner._record_run_event(_tool(toolCallId="t-1"))
    assert _events() == [("Tool", "…", "")]

    runner._record_run_event(
        _tool("tool_call_update", toolCallId="t-1", kind="execute", title="Run tests")
    )

    assert _events() == [("Tool", "Run tests", "")]


def test_a_later_blank_update_does_not_erase_a_tool_label(runner):
    """Completion updates often carry no title; the row must keep the one it had."""
    runner._record_run_event(_tool(toolCallId="t-1", kind="execute", title="Run tests"))

    runner._record_run_event(_tool("tool_call_update", toolCallId="t-1", title="", status="done"))

    assert _events() == [("Tool", "Run tests", "")]


def test_a_tool_call_without_an_id_is_logged_on_its_own(runner):
    runner._record_run_event(_tool(kind="execute", title="Run tests"))
    runner._record_run_event(_tool(kind="execute", title="Run lint"))

    assert _events() == [("Tool", "Run tests", ""), ("Tool", "Run lint", "")]


def test_a_classifier_failure_falls_back_to_the_command_as_detail(runner, monkeypatch):
    def broken(*_args: object, **_kwargs: object) -> None:
        raise TypeError("unexpected shape")

    monkeypatch.setattr("pulse.acp.run_events.build_tool_labels", broken)

    runner._record_run_event(
        _tool(toolCallId="t-1", kind="execute", rawInput={"command": "  pytest -q  ", "path": " "})
    )

    assert _events() == [
        ("Info", "Tool call not labeled", "TypeError: unexpected shape"),
        ("Tool", "execute", "pytest -q"),
    ]


def test_a_classifier_failure_without_input_has_no_detail(runner, monkeypatch):
    def broken(*_args: object, **_kwargs: object) -> None:
        raise TypeError("unexpected shape")

    monkeypatch.setattr("pulse.acp.run_events.build_tool_labels", broken)

    runner._record_run_event(_tool(toolCallId="t-1", rawInput="not an object"))
    runner._record_run_event(_tool(toolCallId="t-2", title="Probe", rawInput={"limit": 3}))

    assert _events()[-3:] == [
        ("Tool", "tool", ""),
        ("Info", "Tool call not labeled", "TypeError: unexpected shape"),
        ("Tool", "Probe", ""),
    ]


def test_a_write_to_a_file_with_no_extension_is_still_an_artifact(runner):
    """`Makefile` does not look like a path to the labeler, but the agent wrote it."""
    runner._record_run_event(
        _tool(
            toolCallId="t-1",
            kind="edit",
            title="Edit",
            locations=[{"path": "Dockerfile"}, "loose", {"path": "  "}, {"path": "Dockerfile"}],
            rawInput={"filePath": " ", "file_path": "Makefile"},
        )
    )

    assert run_store.list_artifacts(RUN_ID) == [
        {"path": "Dockerfile", "step_id": "plan"},
        {"path": "Makefile", "step_id": "plan"},
    ]


@pytest.mark.parametrize(
    "fields",
    [
        {"locations": "Dockerfile", "rawInput": "Makefile"},
        {"locations": [], "rawInput": {"content": "body"}},
    ],
)
def test_a_write_without_a_usable_path_records_no_artifact(runner, fields):
    """A malformed payload must not invent an artifact the history tab cannot open."""
    runner._record_run_event(_tool(toolCallId="t-1", kind="edit", title="Edit", **fields))

    assert run_store.list_artifacts(RUN_ID) == []


def test_a_read_is_not_an_artifact(runner):
    runner._record_run_event(
        _tool(toolCallId="t-1", kind="read", title="Read", rawInput={"path": "src/app.py"})
    )

    assert run_store.list_artifacts(RUN_ID) == []
    assert _events() == [("Read", "src/app.py", "")]


def test_a_new_phase_flushes_the_speech_before_its_marker(runner):
    """Without the marker, history would merge consecutive turns into one block."""
    runner._record_run_event(_chunk("first turn talk"))

    runner._begin_phase("Plan — 2")

    assert _events() == [
        ("Assistant", "first turn talk", "first turn talk"),
        ("Info", "Plan — 2", "Plan — 2"),
    ]
    assert runner._stream.phases == ["Plan — 2"]


def test_speech_with_a_questionnaire_logs_the_speech_and_a_notice(runner):
    """The questions are recorded as Q/A rows; repeating the block would show them twice."""
    runner._record_run_event(_chunk("Here is the plan.\n\n" + QUESTIONNAIRE))
    runner._flush_text()

    assert _events() == [
        ("Assistant", "Here is the plan.", "Here is the plan."),
        ("Info", ui_text.QUESTIONNAIRE_NOTICE, ui_text.QUESTIONNAIRE_NOTICE),
    ]


def test_a_questionnaire_alone_logs_only_the_notice(runner):
    runner._record_run_event(_chunk(QUESTIONNAIRE))
    runner._flush_text()

    assert _events() == [("Info", ui_text.QUESTIONNAIRE_NOTICE, ui_text.QUESTIONNAIRE_NOTICE)]


def test_a_dialog_with_the_user_is_logged_as_question_and_answer(runner):
    runner._record_run_event(_chunk("Let me ask."))

    answer = runner.prompts.ask_text("Where to start?")

    assert answer == "start with the signup"
    assert _events() == [
        ("Assistant", "Let me ask.", "Let me ask."),
        ("Question", ui_text.QUESTION_TITLE, "Where to start?"),
        ("Answer", ui_text.ANSWER_TITLE, "start with the signup"),
    ]


def test_blank_questions_are_not_logged(runner, monkeypatch):
    monkeypatch.setattr(
        "pulse.acp.run_events.build_prompt_qa",
        lambda *_args: [("  ", "ignored"), ("Proceed?", "Sim")],
    )

    runner.prompts.ask_text("anything")

    assert _events() == [
        ("Question", ui_text.QUESTION_TITLE, "Proceed?"),
        ("Answer", ui_text.ANSWER_TITLE, "Sim"),
    ]


def test_a_dialog_that_cannot_be_rebuilt_leaves_a_trace_and_keeps_the_answer(runner, monkeypatch):
    """The answer must reach the agent even when history cannot show the dialog."""

    def broken(*_args: object) -> None:
        raise ValueError("odd payload")

    monkeypatch.setattr("pulse.acp.run_events.build_prompt_qa", broken)

    assert runner.prompts.ask_text("Where to start?") == "start with the signup"
    assert _events() == [("Info", "Dialog not recorded", "ask_text: ValueError: odd payload")]


def test_an_unbound_runner_does_not_log_dialogs(tmp_path: Path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "pulse.acp.run_events.build_prompt_qa", lambda name, *_args: calls.append(name) or []
    )
    unbound = AcpSessionRunner(
        ["agent", "acp"], cwd=str(tmp_path), enable_mcp_ask=False, prompt_handler=_Port()
    )

    assert unbound.prompts.ask_text("Where?") == "start with the signup"
    assert calls == []
