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
    ids = {item["id"] for item in workflows.json()["workflows"]}
    # Só o que está no banco: o Pulse não tem catálogo em código.
    assert ids == {"default"}


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


def test_pause_resume_and_stop_reach_the_running_flow(monkeypatch):
    """A tecla no cockpit vira HTTP, e o flow enxerga pausa/parada de verdade."""
    manager = RunManager()
    app = create_app(manager)
    client = TestClient(app)
    seen: dict[str, object] = {}
    entered = threading.Event()
    release = threading.Event()

    def fake_run_workflow(**kwargs):
        control = kwargs["control"]
        seen["control"] = control
        entered.set()
        # Como o flow real: uma barreira entre cada step, não uma só.
        while not release.is_set():
            if not control.checkpoint():
                return RUN_STOPPED
            time.sleep(0.01)
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)

    run_id = client.post(
        "/api/workflows/default/runs",
        json={"prompt": "x", "workspace": "/tmp"},
    ).json()["id"]
    assert entered.wait(timeout=5)
    control = seen["control"]

    assert client.post(f"/api/runs/{run_id}/pause").status_code == 200
    assert control.paused is True
    assert control.interrupted is True
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "paused"

    assert client.post(f"/api/runs/{run_id}/resume").status_code == 200
    assert control.paused is False
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "running"

    release.set()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        payload = client.get(f"/api/runs/{run_id}").json()
        if payload.get("exit_code") is not None:
            assert payload["exit_code"] == 0, "retomar leva a run até o fim"
            return
        time.sleep(0.05)
    raise AssertionError("run não encerrou depois de retomar")


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

    client.post(f"/api/runs/{run_id}/pause")
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
    for action in ("pause", "resume", "cancel"):
        assert client.post(f"/api/runs/nao-existe/{action}").status_code == 404
