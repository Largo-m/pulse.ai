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


def test_the_run_has_one_id_on_the_api_and_in_the_database(monkeypatch):
    """`RunState.id` é o id do SQLite — sem isso "reabrir a run X" é chute."""
    manager = RunManager()
    client = TestClient(create_app(manager))
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
    client = TestClient(create_app(manager))
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
    assert listed[0]["prompt"] == "tarefa"

    release.set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        listed = client.get("/api/runs").json()["runs"]
        if listed[0]["awaiting_prompt"]:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("a run nunca apareceu esperando resposta")

    state = manager.get(run_id)
    assert state is not None and state.correlator is not None
    pending = state.correlator.pending()
    assert len(pending) == 1
    manager.answer_prompt(pending[0].id, "ok")


def test_resuming_a_run_that_is_still_running_is_refused(monkeypatch):
    """Mesmo id, mesma run: duas threads sobre ela é que não dá."""
    manager = RunManager()
    client = TestClient(create_app(manager))
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
    client = TestClient(create_app(manager))
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
    # Quem chega depois recebe o passado inteiro e só então o marcador.
    replayed = []
    for event in state.bus.subscribe():
        replayed.append(event["type"])
        if event["type"] == REPLAY_END:
            break
    assert replayed[:3] == ["run.started", "phase.begin", "phase.info"]
    assert replayed[-1] == REPLAY_END

    # `after` pula o que o cliente já viu.
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
    client = TestClient(create_app(manager))
    monkeypatch.setattr("pulse.daemon.runs.run_workflow", lambda **kwargs: 0)

    first = client.post("/api/workflows/default/runs", json={"prompt": "a"}).json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and manager.get(first).finished_at is None:
        time.sleep(0.02)
    assert manager.get(first).finished_at is not None

    # Recém-encerrada continua em memória: dá para reabrir e ver o replay.
    assert first in {item["id"] for item in manager.list_runs()}

    manager.get(first).finished_at -= runs_module.FINISHED_TTL + 1
    client.post("/api/workflows/default/runs", json={"prompt": "b"})
    assert manager.get(first) is None
