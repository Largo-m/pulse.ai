from __future__ import annotations

import json
import threading
import time

from fastapi.testclient import TestClient

from pulse.api.app import create_app
from pulse.daemon.runs import RunManager


def test_status_and_workflows():
    app = create_app(RunManager())
    client = TestClient(app)
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["ok"] is True
    workflows = client.get("/api/workflows")
    assert workflows.status_code == 200
    ids = {item["id"] for item in workflows.json()["workflows"]}
    assert "spec" in ids
    assert "new-issue" not in ids
    assert "fix-bug" not in ids


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

    def fake_run_plan(**kwargs):
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

    monkeypatch.setattr("pulse.daemon.runs.run_plan", fake_run_plan)

    created = client.post(
        "/api/workflows/spec/runs",
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
            return
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_unknown_workflow_returns_404():
    app = create_app(RunManager())
    client = TestClient(app)
    response = client.post("/api/workflows/nope/runs", json={"prompt": "x"})
    assert response.status_code == 404
    for workflow_id in ("new-issue", "fix-bug"):
        rejected = client.post(f"/api/workflows/{workflow_id}/runs", json={"prompt": "x"})
        assert rejected.status_code == 404
