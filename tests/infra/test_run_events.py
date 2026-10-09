"""How the ACP session degrades when recording the run log fails.

The log is incidental to the run: a broken classifier, a failing database or a
prompt handler that raises must leave a trace (or at least not end the agent's
session), never kill the ACP read loop.
"""

from __future__ import annotations

import json
import sqlite3
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config.project_config import init_project_config, load_project_config
from pulse.domain.ports import NullRuntimeDialect
from pulse.domain.run import StepRecord
from pulse.history.session_log import RecordedSessionLog
from pulse.store import runs as run_store
from pulse.store.db import connect, default_db_path
from tests.conftest import make_workflow


def _run(workspace: Path) -> str:
    make_workflow("demo", steps=[("plan", "Plan")])
    record = run_store.create_run(
        run_id="run-1",
        workflow_id="demo",
        workspace=workspace,
        user_prompt="do something",
        steps=[StepRecord(step_id="plan", position=1, label="Plan")],
    )
    return record.id


def _runner(workspace: Path, run_id: str, port: object | None = None) -> AcpSessionRunner:
    """A runner inside an open session, as the engine leaves it before a turn."""
    log = RecordedSessionLog(project_root=workspace)
    runner = AcpSessionRunner(
        ["agent", "acp"],
        cwd=str(workspace),
        prompt_handler=port,
        runtime=NullRuntimeDialect(),
        session_log=log,
    )
    runner.bind_run(run_id)
    runner._enter_phase("plan")
    log.enter_session("sess-1", pulse_session_id="pulse-1", cwd=str(workspace), agent_id=None)
    return runner


def _events(run_id: str) -> list[tuple[str, str, str]]:
    return [
        (event["kind"], event["title"], event["detail"]) for event in run_store.list_events(run_id)
    ]


def _write_update(path: Path) -> dict:
    return {
        "update": {
            "sessionUpdate": "tool_call",
            "toolCallId": "t-1",
            "kind": "edit",
            "title": "Write",
            "rawInput": {"path": str(path)},
        }
    }


def _broken_store(*_args: object, **_kwargs: object) -> None:
    raise sqlite3.OperationalError("database is locked")


def test_a_classifier_failure_falls_back_to_the_raw_title_and_leaves_a_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A tool payload the classifier chokes on still shows up, and history says why."""
    run_id = _run(tmp_path)

    def _broken(*_args: object, **_kwargs: object) -> None:
        raise KeyError("content")

    monkeypatch.setattr("pulse.history.session_log.build_tool_labels", _broken)
    runner = _runner(tmp_path, run_id)

    runner._log.update(
        {"update": {"sessionUpdate": "tool_call", "toolCallId": "t-1", "title": "Grep"}}
    )

    assert _events(run_id) == [
        ("Info", "Tool call not labeled", "KeyError: 'content'"),
        ("Tool", "Grep", ""),
    ]


def test_an_artifact_the_database_refuses_is_reported_in_the_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A lost artifact must be visible in history instead of silently missing."""
    run_id = _run(tmp_path)
    monkeypatch.setattr("pulse.store.runs.record_artifact", _broken_store)
    runner = _runner(tmp_path, run_id)

    runner._log.update(_write_update(tmp_path / "notes.md"))

    assert run_store.list_artifacts(run_id) == []
    assert ("Info", "Artifact not recorded", "notes.md: OperationalError: database is locked") in (
        _events(run_id)
    )


def test_a_failing_run_log_does_not_end_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """With the database down there is nowhere to write; the update is still handled."""
    run_id = _run(tmp_path)
    monkeypatch.setattr("pulse.store.runs.record_event", _broken_store)
    monkeypatch.setattr("pulse.store.runs.record_artifact", _broken_store)
    runner = _runner(tmp_path, run_id)

    runner._log.update(_write_update(tmp_path / "notes.md"))

    assert run_store.list_events(run_id) == []


def test_the_user_answer_reaches_the_agent_even_when_the_log_is_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Recording the dialog is incidental; losing the answer would block the agent."""
    run_id = _run(tmp_path)
    monkeypatch.setattr("pulse.store.runs.record_event", _broken_store)

    class _Port:
        def ask_text(self, prompt: str, *, title: str = "") -> str:
            return "start with the signup"

    runner = _runner(tmp_path, run_id, port=_Port())

    assert runner._prompt_handler.ask_text("Where to start?") == "start with the signup"


def test_a_failing_agent_request_gets_a_json_rpc_error_and_a_log_row(tmp_path: Path):
    """The agent waits on the request id, so a failure must still answer it."""
    run_id = _run(tmp_path)

    class _Port:
        def respond_to_ask_question(self, params: dict) -> dict:
            raise RuntimeError("screen closed")

    runner = _runner(tmp_path, run_id, port=_Port())
    stdin = StringIO()
    runner._process = SimpleNamespace(stdin=stdin)  # type: ignore[assignment]  # only stdin is written

    runner._handle_agent_request(
        {"jsonrpc": "2.0", "id": 7, "method": "cursor/ask_question", "params": {}}
    )

    assert json.loads(stdin.getvalue()) == {
        "jsonrpc": "2.0",
        "id": 7,
        "error": {"code": -32603, "message": "screen closed"},
    }
    assert ("Info", "Agent request failed", "cursor/ask_question: RuntimeError: screen closed") in (
        _events(run_id)
    )


def test_a_runtime_session_the_database_refuses_is_reported_in_the_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Without the session row the run cannot be resumed; history must say so."""
    run_id = _run(tmp_path)
    init_project_config(tmp_path)
    runner = _runner(tmp_path, run_id)
    monkeypatch.setattr("pulse.history.session_log.persist_runtime_session", _broken_store)

    runner._activate_session("sess-2")

    assert runner.last_session_id == "sess-2"
    assert _events(run_id) == [
        ("Info", "Runtime session not recorded", "OperationalError: database is locked")
    ]


def test_a_session_in_the_runs_worktree_is_recorded_under_its_project(tmp_path: Path):
    """The worktree lives under `~/.pulse/worktrees`, outside the project (invariant 10).

    Resolving the project from the session's `cwd` found none there, so every
    agent session of an isolated run went unrecorded without a trace.
    """
    project_root = tmp_path / "repo"
    worktree = tmp_path / "worktrees" / "run-1"
    worktree.mkdir(parents=True)
    init_project_config(project_root)
    project = load_project_config(project_root)
    assert project is not None
    log = RecordedSessionLog(project_root=project_root)

    log.enter_session("sess-1", pulse_session_id="pulse-1", cwd=str(worktree), agent_id="tester")

    connection = connect(default_db_path())
    rows = connection.execute(
        "SELECT project_id, acp_session_id, agent_id FROM agent_sessions"
    ).fetchall()
    connection.close()
    assert [tuple(row) for row in rows] == [(project.project_id, "sess-1", "tester")]
