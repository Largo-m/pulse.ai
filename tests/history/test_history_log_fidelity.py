"""History must show the same thing the live session showed.

The recorded log goes through the same labels as the cockpit
([pulse.history.tool_detail.build_tool_labels]), and reloading maps each line back
to its kind. Storing `kind="Tool"` with the raw ACP `title` turned a reopened run
into a row of "v Tool" entries that hid what the agent read, ran or wrote.

Dialogue follows the same rule: every question asked to the user goes through the
prompt port proxy and becomes `Pergunta`/`Você` bubbles
([pulse.history.prompt_detail.build_prompt_qa]); otherwise the questionnaire that
steered the run vanished on reopen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pulse.acp.session_runner import AcpSessionRunner
from pulse.domain.run import StepRecord, StepStatus
from pulse.history.events import LogKind
from pulse.history.log_wording import QUESTIONNAIRE_NOTICE
from pulse.history.models import HistoryItem, HistoryStatus, HistoryStep
from pulse.history.session_log import RecordedSessionLog
from pulse.replies.acp_payloads import QuestionAnswer
from pulse.replies.ask_question import build_ask_question_answers
from pulse.replies.permission import permission_selected
from pulse.replies.text_questionnaire import (
    format_questionnaire_answers,
    parse_text_questionnaire,
)
from pulse.runtimes import get_runtime
from pulse.store import runs as run_store
from pulse.tui.hydrate import hydrate_history_item
from tests.conftest import make_workflow, served_log

# The screen reads the stored run through the daemon's route, as the TUI does.
pytestmark = pytest.mark.usefixtures("in_process_daemon")


def _runner(
    workspace: Path,
    run_id: str = "run-1",
    step_id: str = "plan",
    port: object | None = None,
) -> AcpSessionRunner:
    log = RecordedSessionLog()
    runner = AcpSessionRunner(
        ["agent", "acp"],
        cwd=str(workspace),
        prompt_handler=port,
        runtime=get_runtime("cursor"),
        session_log=log,
    )
    runner.bind_run(run_id)
    runner._enter_phase(step_id)
    log.enter_session("sess-1", pulse_session_id="pulse-1", cwd=str(workspace), agent_id=None)
    return runner


def _run(workspace: Path, run_id: str = "run-1") -> str:
    make_workflow("demo", steps=[("plan", "Planejar")])
    record = run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt="fazer algo",
        steps=[StepRecord(step_id="plan", position=1, label="Planejar")],
    )
    return record.id


def _update(**fields) -> dict:
    return {"update": {"sessionUpdate": "tool_call", "toolCallId": "t-1", **fields}}


def _hydrated(workspace: Path, run_id: str = "run-1"):
    item = HistoryItem(
        run_id=run_id,
        workflow_id="demo",
        workflow_label="Demo",
        title="demo",
        prompt="fazer algo",
        status=HistoryStatus.DONE,
        updated_at="2026-09-30T10:00:00+00:00",
        steps=[HistoryStep(id="plan", label="Planejar", status=StepStatus.DONE)],
    )
    return hydrate_history_item(item, workspace, served_log(run_id))


def test_each_tool_stores_the_kind_the_screen_showed(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._log.update(
        _update(title="Read File", kind="read", rawInput={"path": str(tmp_path / "a.py")})
    )
    runner._log.update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "t-2",
                "title": "Shell",
                "kind": "execute",
                "rawInput": {"command": "pytest -q"},
            }
        }
    )

    events = run_store.list_events(run_id)
    assert [(event["kind"], event["title"]) for event in events] == [
        ("Read", "a.py"),
        ("Shell", "pytest -q"),
    ]


def test_history_reopens_with_kinds_instead_of_generic_tool(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    runner._log.update(
        _update(title="Read File", kind="read", rawInput={"path": str(tmp_path / "a.py")})
    )

    state = _hydrated(tmp_path, run_id)

    assert [(entry.kind, entry.title) for entry in state.entries] == [(LogKind.READ, "a.py")]


def test_agent_speech_comes_back_whole_in_the_bubble(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    speech = "linha um. " * 400

    _speak(runner, speech)
    runner._log.flush()

    state = _hydrated(tmp_path, run_id)
    entry = state.entries[0]
    assert entry.kind == LogKind.ASSISTANT
    assert entry.body == speech.strip()


def test_the_step_header_stays_in_the_log(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._begin_phase("Planejar")

    state = _hydrated(tmp_path, run_id)
    assert [(entry.kind, entry.title) for entry in state.entries] == [(LogKind.INFO, "Planejar")]


def test_a_late_update_does_not_erase_the_tool_label(tmp_path: Path):
    """`rawOutput` arrives in another event; the line already had the file."""
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._log.update(
        _update(title="Write File", kind="write", rawInput={"path": str(tmp_path / "PRD.md")})
    )
    runner._log.update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "t-1",
                "status": "completed",
            }
        }
    )

    events = run_store.list_events(run_id)
    assert [(event["kind"], event["title"]) for event in events] == [("Write", "PRD.md")]


def _dialogue(run_id: str) -> list[tuple[str, str]]:
    """The log's question/answer lines, in order."""
    return [
        (event["kind"], event["detail"])
        for event in run_store.list_events(run_id)
        if event["kind"] in {"Question", "Answer"}
    ]


def test_the_agent_question_and_the_answer_stay_in_the_log(tmp_path: Path):
    """`AskQuestion` is where the user steers the run.

    If it vanished from history, only the agent's speech would remain, without its reason.
    """
    run_id = _run(tmp_path)

    class _Port:
        def respond_to_ask_question(self, params):
            return build_ask_question_answers([QuestionAnswer("q1", ("B",))])

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.respond_to_ask_question(
        {
            "questions": [
                {
                    "id": "q1",
                    "prompt": "1. O que você está construindo?",
                    "options": [
                        {"id": "A", "label": "Produto / plataforma"},
                        {"id": "B", "label": "API / serviço backend"},
                    ],
                }
            ]
        }
    )

    assert _dialogue(run_id) == [
        ("Question", "1. O que você está construindo?"),
        ("Answer", "B) API / serviço backend"),
    ]


def test_free_text_written_in_other_goes_into_the_answer(tmp_path: Path):
    run_id = _run(tmp_path)

    class _Port:
        def respond_to_ask_question(self, params):
            return build_ask_question_answers(
                [QuestionAnswer("q1", ("B::Falta o acesso ao banco",))]
            )

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.respond_to_ask_question(
        {
            "questions": [
                {
                    "id": "q1",
                    "prompt": "1. Aprovar a Techspec e avançar?",
                    "options": [
                        {"id": "A", "label": "Sim, aprovar"},
                        {"id": "B", "label": "Não, preciso de ajustes (descreva)"},
                    ],
                }
            ]
        }
    )

    assert _dialogue(run_id)[1] == (
        "Answer",
        "B) Não, preciso de ajustes (descreva) — Falta o acesso ao banco",
    )


def test_text_questionnaire_becomes_one_pair_per_question(tmp_path: Path):
    run_id = _run(tmp_path)
    questionnaire = parse_text_questionnaire(
        "Preciso de algumas informações antes de continuar.\n"
        "1. O que você está construindo?\n"
        "A) Produto\n"
        "B) Biblioteca\n"
        "2. Quem usa?\n"
        "A) Time interno\n"
        "B) Cliente final\n"
    )

    class _Port:
        def run_parsed_questionnaire(self, parsed):
            return format_questionnaire_answers(
                parsed,
                [
                    (parsed.questions[0], "A) Produto"),
                    (parsed.questions[1], "B) Cliente final"),
                ],
            )

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.run_parsed_questionnaire(questionnaire)

    assert _dialogue(run_id) == [
        ("Question", "1. O que você está construindo?"),
        ("Answer", "A) Produto"),
        ("Question", "2. Quem usa?"),
        ("Answer", "B) Cliente final"),
    ]


def _permission_params(kind: str = "edit") -> dict:
    return {
        "permission": {"title": "Editar app.py", "kind": kind},
        "toolCall": {"kind": kind, "title": "Write app.py"},
        "options": [
            {"optionId": "allow-once", "kind": "allow_once"},
            {"optionId": "reject-once", "kind": "reject_once"},
        ],
    }


def test_a_permission_resolved_by_policy_does_not_become_a_line(tmp_path: Path):
    """A rule is not a question: nobody saw that decision, so it is not dialogue."""
    run_id = _run(tmp_path)

    class _Port:
        def respond_to_permission(self, params, *, policy, allow_terminal=False):
            return permission_selected("allow-once")

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.respond_to_permission(_permission_params(), policy="auto_approve")

    assert _dialogue(run_id) == []


def test_a_permission_decided_by_the_user_stays_in_the_log(tmp_path: Path):
    run_id = _run(tmp_path)

    class _Port:
        def respond_to_permission(self, params, *, policy, allow_terminal=False):
            return permission_selected("reject-once")

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.respond_to_permission(_permission_params(), policy="ask")

    assert _dialogue(run_id) == [
        ("Question", "Editar app.py\nWrite app.py"),
        ("Answer", "B) Recusar"),
    ]


def test_the_retry_menu_and_guidance_stay_in_the_log(tmp_path: Path):
    """What the engine asks when a step fails is also the user's decision."""
    run_id = _run(tmp_path)

    class _Port:
        def select_choice(self, prompt, choices, *, title=""):
            return "guidance"

        def ask_text(self, prompt, *, title=""):
            return "Usar o endpoint novo"

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.select_choice(
        "o step quebrou",
        [("Refazer", "retry"), ("Outro — dizer o que fazer", "guidance")],
        title="Planejar",
    )
    runner._prompt_handler.ask_text("O que o agente deve fazer nesta nova tentativa?")

    assert _dialogue(run_id) == [
        ("Question", "o step quebrou"),
        ("Answer", "Outro — dizer o que fazer"),
        ("Question", "O que o agente deve fazer nesta nova tentativa?"),
        ("Answer", "Usar o endpoint novo"),
    ]


def test_the_questionnaire_block_does_not_come_back_as_agent_speech(tmp_path: Path):
    """Live, the block becomes a dock; storing it raw would show the questions twice."""
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    _speak(
        runner,
        "Antes de começar preciso entender o escopo.\n\n"
        "Preciso de algumas informações antes de continuar.\n"
        "1. O que você está construindo?\n"
        "A) Produto\n"
        "B) Biblioteca\n",
    )
    runner._log.flush()

    events = [(event["kind"], event["title"]) for event in run_store.list_events(run_id)]
    assert events == [
        ("Assistant", "Antes de começar preciso entender o escopo."),
        ("Info", QUESTIONNAIRE_NOTICE),
    ]


def test_code_fence_before_the_questionnaire_stays_in_the_speech(tmp_path: Path):
    """The log cuts where the live screen cuts: an arbitrary fence is not a questionnaire."""
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    tree = "Estrutura atual:\n```\npulse/\n  store/\n```"

    _speak(
        runner,
        f"{tree}\nPreciso de algumas informações:\n1. Qual banco usar?\nA) Postgres\nB) SQLite\n",
    )
    runner._log.flush()

    events = [(event["kind"], event["detail"]) for event in run_store.list_events(run_id)]
    assert [kind for kind, _detail in events] == ["Assistant", "Info"]
    assert "pulse/\n  store/" in events[0][1]
    assert events[1][1] == QUESTIONNAIRE_NOTICE


def test_dialogue_that_could_not_be_built_leaves_a_trace(tmp_path: Path, monkeypatch):
    """The answer still reaches the agent, and history says the dialogue is missing."""
    run_id = _run(tmp_path)

    def _broken(*_args):
        raise ValueError("payload estranho")

    monkeypatch.setattr("pulse.history.session_log.build_prompt_qa", _broken)

    class _Port:
        def ask_text(self, prompt, *, title=""):
            return "ok"

    runner = _runner(tmp_path, run_id, port=_Port())
    assert runner._prompt_handler.ask_text("Pergunta?") == "ok"

    events = [(event["kind"], event["detail"]) for event in run_store.list_events(run_id)]
    assert events == [("Info", "ask_text: ValueError: payload estranho")]


def test_history_reopens_with_question_and_answer_bubbles(tmp_path: Path):
    run_id = _run(tmp_path)

    class _Port:
        def ask_text(self, prompt, *, title=""):
            return "Começar pelo cadastro"

    runner = _runner(tmp_path, run_id, port=_Port())
    runner._prompt_handler.ask_text("Por onde começar?")

    state = _hydrated(tmp_path, run_id)
    assert [(entry.kind, entry.title, entry.body) for entry in state.entries] == [
        (LogKind.QUESTION, "Pergunta", "Por onde começar?"),
        (LogKind.ANSWER, "Você", "Começar pelo cadastro"),
    ]


def test_artifact_comes_from_the_tool_even_without_acp_kind(tmp_path: Path):
    """A runtime that only sends the tool name also yields an artifact.

    The history artifacts tab used to be empty because recording depended on the
    ACP `kind` field, which not every runtime fills in.
    """
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    (tmp_path / "PRD.md").write_text("# PRD\n", encoding="utf-8")

    runner._log.update(
        _update(title="Write", toolName="write_file", rawInput={"path": str(tmp_path / "PRD.md")})
    )

    assert [item["path"] for item in run_store.list_artifacts(run_id)] == ["PRD.md"]

    state = _hydrated(tmp_path, run_id)
    assert [(item.path, item.has_content) for item in state.artifacts] == [("PRD.md", True)]
    assert state.phase_has_artifacts(), "the tab must open for the run artifact"


def _speak(runner: AcpSessionRunner, text: str) -> None:
    """The agent's speech as the session streams it."""
    runner._log.update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": text},
            }
        }
    )
