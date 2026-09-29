"""Artefato é o que o agente escreveu — descoberto pelos tool-calls do ACP.

Não há convenção de pasta nem de extensão: o Pulse guarda só o caminho que o
runtime reportou, e é isso que o painel e o histórico mostram.
"""

from __future__ import annotations

from pulse.acp.session_runner import AcpSessionRunner
from pulse.store import runs as run_store
from pulse.store.runs import StepRecord


def _runner(run_id: str = "run-1", step_id: str = "one") -> AcpSessionRunner:
    runner = AcpSessionRunner(["agent", "acp"], cwd="/repo", enable_mcp_ask=False)
    runner.bind_run(run_id)
    runner._phase_id = step_id
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

    runner._record_run_event(_write_call(locations=[{"path": "/repo/docs/PLANO.md"}]))

    assert run_store.list_artifacts("run-1") == [
        {"path": "/repo/docs/PLANO.md", "step_id": "one"}
    ]


def test_the_path_can_come_from_raw_input(tmp_path):
    """Cada runtime reporta o arquivo de um jeito; os dois caminhos valem."""
    _run(tmp_path)
    runner = _runner()

    runner._record_run_event(_write_call(rawInput={"file_path": "/repo/src/main.rs"}))

    assert [item["path"] for item in run_store.list_artifacts("run-1")] == [
        "/repo/src/main.rs"
    ]


def test_the_same_file_written_twice_is_one_artifact(tmp_path):
    _run(tmp_path)
    runner = _runner()

    runner._record_run_event(_write_call(locations=[{"path": "/repo/docs/PLANO.md"}]))
    runner._record_run_event(
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

    runner._record_run_event(
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
    """Sem `bind_run`, não há run a que atribuir o artefato — e nada quebra."""
    runner = AcpSessionRunner(["agent", "acp"], cwd="/repo", enable_mcp_ask=False)

    runner._record_run_event(_write_call(locations=[{"path": "/repo/docs/PLANO.md"}]))

    assert run_store.list_artifacts("run-1") == []


def test_tool_calls_also_land_in_the_run_log(tmp_path):
    _run(tmp_path)
    runner = _runner()

    runner._record_run_event(_write_call(locations=[{"path": "/repo/docs/PLANO.md"}]))

    events = run_store.list_events("run-1")
    assert [(event["kind"], event["step_id"]) for event in events] == [("Tool", "one")]
