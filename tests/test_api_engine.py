from __future__ import annotations

import json
import threading
import time

from pathlib import Path

from fastapi.testclient import TestClient

from pulse.api.app import create_app
from pulse.daemon.runs import RunManager
from pulse.runcontrol import RUN_STOPPED


def test_status_and_workflows():
    app = create_app(RunManager())
    client = TestClient(app)
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["ok"] is True
    assert status.json()["protocol"] >= 2
    workflows = client.get("/api/workflows")
    assert workflows.status_code == 200
    listed = workflows.json()["workflows"]
    ids = {item["id"] for item in listed}
    # Só o que está no banco: o Pulse não tem catálogo em código.
    assert ids >= {"default", "new-issue", "quick-fix"}
    pipeline = next(item for item in listed if item["id"] == "new-issue")
    assert [step["agent"] for step in pipeline["steps"]] == [
        "prd",
        "techspec",
        "tasks",
        "implement",
    ]


def test_doctor_endpoint():
    app = create_app(RunManager())
    client = TestClient(app)
    response = client.get("/api/doctor")
    assert response.status_code == 200
    assert "checks" in response.json()


def test_start_run_and_prompt_correlator(monkeypatch):
    manager = RunManager()
    app = create_app(manager)
    client = TestClient(app)
    captured: dict[str, object] = {}

    def fake_run_workflow(**kwargs):
        captured["workspace"] = kwargs.get("workspace")
        stream = kwargs["stream"]
        prompt_handler = kwargs["prompt_handler"]
        stream.begin_phase("Test")
        stream.handle_update(
            {
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": "hi"},
                }
            }
        )
        answer = prompt_handler.respond_to_ask_question(
            {
                "questions": [
                    {
                        "id": "q1",
                        "prompt": "ok?",
                        "options": [{"id": "y", "label": "yes"}],
                    }
                ]
            }
        )
        assert answer["outcome"]["outcome"] == "selected"
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)

    created = client.post(
        "/api/workflows/default/runs",
        json={"prompt": "x", "workspace": "/tmp"},
    )
    assert created.status_code == 200
    run_id = created.json()["id"]
    state = manager.get(run_id)
    assert state is not None

    prompt_id: dict[str, str] = {}

    def watch_and_answer() -> None:
        for event in state.bus.subscribe():
            if event.get("type") == "prompt.request":
                prompt_id["id"] = str(event["id"])
                assert manager.answer_prompt(
                    str(event["id"]),
                    {"outcome": {"outcome": "selected", "optionId": "y"}},
                )
            if event.get("type") == "run.finished":
                break

    watcher = threading.Thread(target=watch_and_answer, daemon=True)
    watcher.start()
    watcher.join(timeout=5)
    assert watcher.is_alive() is False
    assert "id" in prompt_id

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        payload = client.get(f"/api/runs/{run_id}").json()
        if payload.get("exit_code") is not None:
            assert payload["exit_code"] == 0
            assert captured["workspace"] == Path("/tmp")
            return
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_unknown_workflow_returns_404():
    app = create_app(RunManager())
    client = TestClient(app)
    response = client.post("/api/workflows/nope/runs", json={"prompt": "x"})
    assert response.status_code == 404


def test_resume_carries_the_previous_run_into_the_flow(monkeypatch):
    """Retomar é uma run nova sobre o mesmo registro — o flow recebe o id."""
    manager = RunManager()
    app = create_app(manager)
    client = TestClient(app)
    seen: dict[str, object] = {}
    entered = threading.Event()

    def fake_run_workflow(**kwargs):
        seen.update(kwargs)
        entered.set()
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)

    client.post(
        "/api/workflows/default/runs",
        json={"prompt": "x", "workspace": "/tmp", "resume_run_id": "run-anterior"},
    )
    assert entered.wait(timeout=5)

    assert seen["resume_run_id"] == "run-anterior"
    assert "restart" not in seen, "não há refazer do zero: só retomar"


def test_stop_ends_the_run_as_stopped_not_failed(monkeypatch):
    manager = RunManager()
    app = create_app(manager)
    client = TestClient(app)
    entered = threading.Event()

    def fake_run_workflow(**kwargs):
        control = kwargs["control"]
        entered.set()
        # Só sai quando o usuário parar: é o cancel que encerra esta run.
        while True:
            if not control.checkpoint():
                return RUN_STOPPED
            time.sleep(0.01)

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)

    run_id = client.post(
        "/api/workflows/default/runs",
        json={"prompt": "x", "workspace": "/tmp"},
    ).json()["id"]
    assert entered.wait(timeout=5)

    assert client.post(f"/api/runs/{run_id}/cancel").status_code == 200

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        payload = client.get(f"/api/runs/{run_id}").json()
        if payload.get("exit_code") is not None:
            assert payload["exit_code"] == RUN_STOPPED
            assert payload["status"] == "stopped", "parar não é falhar"
            return
        time.sleep(0.05)
    raise AssertionError("run não encerrou depois do stop")


def test_control_endpoints_404_for_unknown_run():
    client = TestClient(create_app(RunManager()))
    assert client.post("/api/runs/nao-existe/cancel").status_code == 404


def test_history_delete_endpoint(tmp_path: Path):
    from pulse.store import runs as run_store
    from pulse.store.runs import StepRecord

    run_store.create_run(
        run_id="run-api",
        workflow_id="default",
        workspace=tmp_path,
        user_prompt="algo",
        steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
    )
    client = TestClient(create_app(RunManager()))

    removed = client.delete("/api/history/run-api", params={"workspace": str(tmp_path)})
    assert removed.status_code == 200
    assert run_store.load_run("run-api") is None

    again = client.delete("/api/history/run-api", params={"workspace": str(tmp_path)})
    assert again.status_code == 404
