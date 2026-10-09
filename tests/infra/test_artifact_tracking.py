"""An artifact is whatever the agent wrote, discovered via ACP tool calls.

There is no folder or extension convention: Pulse stores only the path the
runtime reported, and that is what the pane and history show.
"""

from __future__ import annotations

from pulse.acp.session_runner import AcpSessionRunner
from pulse.domain.run import StepRecord
from pulse.history.session_log import RecordedSessionLog
from pulse.runtimes import get_runtime
from pulse.store import runs as run_store


def _runner(run_id: str = "run-1", step_id: str = "one") -> AcpSessionRunner:
    """A runner inside an open session, as the engine leaves it before a turn."""
    log = RecordedSessionLog()
    runner = AcpSessionRunner(
        ["agent", "acp"],
        cwd="/repo",
        runtime=get_runtime("cursor"),
        session_log=log,
    )
    runner.bind_run(run_id)
    runner._enter_phase(step_id)
    log.enter_session("sess-1", pulse_session_id="pulse-1", cwd="/repo", agent_id=None)
    return runner


def _run(tmp_path, run_id: str = "run-1") -> None:
    run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[StepRecord(step_id="one", position=1, label="Um")],
    )


def _write_call(**extra) -> dict:
    return {
        "update": {
            "sessionUpdate": "tool_call",
            "toolCallId": "t-1",
            "title": "Write File",
            "kind": "write",
            **extra,
        }
    }


def test_a_write_tool_call_records_the_artifact(tmp_path):
    _run(tmp_path)
    runner = _runner()

    runner._log.update(_write_call(locations=[{"path": "/repo/docs/PLANO.md"}]))

    assert run_store.list_artifacts("run-1") == [{"path": "docs/PLANO.md", "step_id": "one"}]


def test_the_path_can_come_from_raw_input(tmp_path):
    """Each runtime reports the file differently; both paths are accepted."""
    _run(tmp_path)
    runner = _runner()

    runner._log.update(_write_call(rawInput={"file_path": "/repo/src/main.rs"}))

    assert [item["path"] for item in run_store.list_artifacts("run-1")] == ["src/main.rs"]


def test_the_same_file_written_twice_is_one_artifact(tmp_path):
    _run(tmp_path)
    runner = _runner()

    runner._log.update(_write_call(locations=[{"path": "/repo/docs/PLANO.md"}]))
    runner._log.update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "t-2",
                "title": "Edit File",
                "kind": "edit",
                "locations": [{"path": "/repo/docs/PLANO.md"}],
            }
        }
    )

    assert len(run_store.list_artifacts("run-1")) == 1


def test_reads_and_searches_are_not_artifacts(tmp_path):
    _run(tmp_path)
    runner = _runner()

    runner._log.update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "t-read",
                "title": "Read File",
                "kind": "read",
                "rawInput": {"path": "/repo/docs/PLANO.md"},
            }
        }
    )

    assert run_store.list_artifacts("run-1") == []


def test_an_unbound_runner_records_nothing(tmp_path):
    """Without `bind_run` there is no run to attribute the artifact to, and nothing breaks."""
    runner = AcpSessionRunner(
        ["agent", "acp"],
        cwd="/repo",
        runtime=get_runtime("cursor"),
        session_log=RecordedSessionLog(),
    )

    runner._log.update(_write_call(locations=[{"path": "/repo/docs/PLANO.md"}]))

    assert run_store.list_artifacts("run-1") == []


def test_tool_calls_also_land_in_the_run_log(tmp_path):
    _run(tmp_path)
    runner = _runner()

    runner._log.update(_write_call(locations=[{"path": "/repo/docs/PLANO.md"}]))

    events = run_store.list_events("run-1")
    assert [(event["kind"], event["step_id"]) for event in events] == [("Write", "one")]
    assert events[0]["title"] == "docs/PLANO.md"
