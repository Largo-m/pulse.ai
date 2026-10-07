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
    client = TestClient(app, base_url="http://127.0.0.1")
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["ok"] is True
    assert status.json()["protocol"] >= 2
    workflows = client.get("/api/workflows")
    assert workflows.status_code == 200
    listed = workflows.json()["workflows"]
    ids = {item["id"] for item in listed}
    assert ids >= {"default", "new-issue", "quick-fix", "review"}
    pipeline = next(item for item in listed if item["id"] == "new-issue")
    assert [step["agent"] for step in pipeline["steps"]] == [
        "prd",
        "techspec",
        "tasks",
        "implement",
        "review",
        "review-fix",
    ]


def test_doctor_endpoint():
    app = create_app(RunManager())
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.get("/api/doctor")
    assert response.status_code == 200
    assert "checks" in response.json()


def test_start_run_and_prompt_correlator(monkeypatch):
    manager = RunManager()
    app = create_app(manager)
    client = TestClient(app, base_url="http://127.0.0.1")
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
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.post("/api/workflows/nope/runs", json={"prompt": "x"})
    assert response.status_code == 404


def test_resume_carries_the_previous_run_into_the_flow(monkeypatch):
    """Resuming is a new run over the same record; the flow receives the id."""
    manager = RunManager()
    app = create_app(manager)
    client = TestClient(app, base_url="http://127.0.0.1")
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
    assert "restart" not in seen, "there is no restart from scratch, only resume"


def test_stop_ends_the_run_as_stopped_not_failed(monkeypatch):
    manager = RunManager()
    app = create_app(manager)
    client = TestClient(app, base_url="http://127.0.0.1")
    entered = threading.Event()

    def fake_run_workflow(**kwargs):
        control = kwargs["control"]
        entered.set()
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
            assert payload["status"] == "stopped", "stopping is not failing"
            return
        time.sleep(0.05)
    raise AssertionError("run did not finish after stop")


def test_control_endpoints_404_for_unknown_run():
    client = TestClient(create_app(RunManager()), base_url="http://127.0.0.1")
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
    client = TestClient(create_app(RunManager()), base_url="http://127.0.0.1")

    removed = client.delete("/api/history/run-api", params={"workspace": str(tmp_path)})
    assert removed.status_code == 200
    assert run_store.load_run("run-api") is None

    again = client.delete("/api/history/run-api", params={"workspace": str(tmp_path)})
    assert again.status_code == 404


def test_the_run_has_one_id_on_the_api_and_in_the_database(monkeypatch):
    """`RunState.id` is the SQLite id; without that, "reopen run X" is a guess."""
    manager = RunManager()
    client = TestClient(create_app(manager), base_url="http://127.0.0.1")
    seen: dict[str, object] = {}
    entered = threading.Event()

    def fake_run_workflow(**kwargs):
        seen.update(kwargs)
        entered.set()
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)
    run_id = client.post("/api/workflows/default/runs", json={"prompt": "x"}).json()["id"]
    assert entered.wait(timeout=5)
    assert seen["run_id"] == run_id


def test_listing_runs_shows_what_is_alive_and_what_it_waits_for(monkeypatch):
    manager = RunManager()
    client = TestClient(create_app(manager), base_url="http://127.0.0.1")
    asking = threading.Event()
    release = threading.Event()

    def fake_run_workflow(**kwargs):
        asking.set()
        release.wait(timeout=5)
        kwargs["prompt_handler"].ask_text("e agora?")
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)
    run_id = client.post(
        "/api/workflows/default/runs", json={"prompt": "tarefa"}
    ).json()["id"]
    assert asking.wait(timeout=5)

    listed = client.get("/api/runs").json()["runs"]
    assert [item["id"] for item in listed] == [run_id]
    assert listed[0]["active"] is True
    assert listed[0]["awaiting_prompt"] is False
    assert listed[0]["status"] == "running"
    assert listed[0]["awaiting_since"] is None
    assert listed[0]["prompt"] == "tarefa"

    release.set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        listed = client.get("/api/runs").json()["runs"]
        if listed[0]["awaiting_prompt"]:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("the run never showed up awaiting an answer")

    assert listed[0]["status"] == "awaiting_input"
    assert listed[0]["awaiting_since"] is not None

    state = manager.get(run_id)
    assert state is not None and state.correlator is not None
    pending = state.correlator.pending()
    assert len(pending) == 1
    manager.answer_prompt(pending[0].id, "ok")


def test_a_run_with_nobody_watching_does_not_stop_on_a_policy_permission(monkeypatch):
    """With the cockpit closed, a run may only stop on what needs a person.

    `deny_writes` rejects writes on its own; when that decision lived in the
    client, a run with no client attached waited forever on a prompt nobody
    had to answer.
    """
    manager = RunManager()
    client = TestClient(create_app(manager), base_url="http://127.0.0.1")
    decided: list = []
    done = threading.Event()

    def fake_run_workflow(**kwargs):
        decided.append(
            kwargs["prompt_handler"].respond_to_permission(
                {
                    "permission": {"title": "Editar app.py", "kind": "edit"},
                    "toolCall": {"kind": "edit", "rawInput": {"path": "/repo/app.py"}},
                    "options": [
                        {"optionId": "allow-once", "kind": "allow_once"},
                        {"optionId": "reject-once", "kind": "reject_once"},
                    ],
                },
                policy="deny_writes",
            )
        )
        done.set()
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)
    run_id = client.post(
        "/api/workflows/default/runs", json={"prompt": "tarefa"}
    ).json()["id"]

    assert done.wait(timeout=5), "the run hung on a permission the policy resolves"
    assert decided[0]["outcome"]["optionId"] == "reject-once"

    state = manager.get(run_id)
    assert state is not None and state.correlator is not None
    assert state.correlator.pending() == []
    listed = client.get("/api/runs").json()["runs"]
    assert listed[0]["awaiting_prompt"] is False


def test_cancelling_a_run_that_is_waiting_for_an_answer_frees_it(monkeypatch):
    """Stopping a run blocked on a question must wake the waiter.

    The engine waits for the answer with no timeout, so `stop` alone left the
    thread stuck in the question's `wait` and the run never finished.
    """
    manager = RunManager()
    client = TestClient(create_app(manager), base_url="http://127.0.0.1")
    asked = threading.Event()
    answer: list[object] = []

    def fake_run_workflow(**kwargs):
        asked.set()
        answer.append(kwargs["prompt_handler"].ask_text("e agora?"))
        return RUN_STOPPED

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)
    run_id = client.post(
        "/api/workflows/default/runs", json={"prompt": "tarefa"}
    ).json()["id"]
    assert asked.wait(timeout=5)

    state = manager.get(run_id)
    assert state is not None and state.correlator is not None
    deadline = time.monotonic() + 5
    while not state.correlator.pending() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert state.correlator.pending()

    assert client.post(f"/api/runs/{run_id}/cancel").json() == {"ok": True}

    deadline = time.monotonic() + 5
    while state.is_active() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not state.is_active()
    assert answer == [None]


def test_resuming_a_run_that_is_still_running_is_refused(monkeypatch):
    """Same id, same run: two threads over it is not allowed."""
    manager = RunManager()
    client = TestClient(create_app(manager), base_url="http://127.0.0.1")
    entered = threading.Event()
    release = threading.Event()

    def fake_run_workflow(**kwargs):
        entered.set()
        release.wait(timeout=5)
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)
    run_id = client.post("/api/workflows/default/runs", json={"prompt": "x"}).json()["id"]
    assert entered.wait(timeout=5)

    again = client.post(
        "/api/workflows/default/runs",
        json={"prompt": "x", "resume_run_id": run_id},
    )
    assert again.status_code == 409
    release.set()


def test_attaching_replays_the_run_and_marks_where_the_past_ends(monkeypatch):
    from pulse.daemon.protocol import REPLAY_END

    manager = RunManager()
    client = TestClient(create_app(manager), base_url="http://127.0.0.1")
    streamed = threading.Event()
    release = threading.Event()

    def fake_run_workflow(**kwargs):
        kwargs["stream"].begin_phase("Um")
        kwargs["stream"].info("andando")
        streamed.set()
        release.wait(timeout=5)
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_workflow", fake_run_workflow)
    run_id = client.post("/api/workflows/default/runs", json={"prompt": "x"}).json()["id"]
    assert streamed.wait(timeout=5)

    state = manager.get(run_id)
    assert state is not None
    replayed = []
    for event in state.bus.subscribe():
        replayed.append(event["type"])
        if event["type"] == REPLAY_END:
            break
    assert replayed[:3] == ["run.started", "phase.begin", "phase.info"]
    assert replayed[-1] == REPLAY_END

    resumed = []
    for event in state.bus.subscribe(after=2):
        resumed.append(event["type"])
        if event["type"] == REPLAY_END:
            break
    assert resumed == ["phase.info", REPLAY_END]
    release.set()


def test_finished_runs_stay_attachable_for_a_while_then_go(monkeypatch):
    from pulse.daemon import runs as runs_module

    manager = RunManager()
    client = TestClient(create_app(manager), base_url="http://127.0.0.1")
    monkeypatch.setattr("pulse.daemon.runs.run_workflow", lambda **kwargs: 0)

    first = client.post("/api/workflows/default/runs", json={"prompt": "a"}).json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and manager.get(first).finished_at is None:
        time.sleep(0.02)
    assert manager.get(first).finished_at is not None

    assert first in {item["id"] for item in manager.list_runs()}

    manager.get(first).finished_at -= runs_module.FINISHED_TTL + 1
    client.post("/api/workflows/default/runs", json={"prompt": "b"})
    assert manager.get(first) is None


def test_foreign_host_is_rejected() -> None:
    client = TestClient(create_app(), base_url="http://attacker.example:8787")
    response = client.post("/api/workflows/feature/runs", json={"prompt": "x", "workspace": "/"})
    assert response.status_code == 400
