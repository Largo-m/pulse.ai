"""Config, history and prompt routes: the payloads the TUI and the CLI read.

These pin what each route answers, so the routes can move between modules
without a client noticing.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pulse.api.app import create_app
from pulse.config.global_config import GlobalConfig, load_global_config, save_global_config
from pulse.config.project_config import init_project_config, update_project_defaults
from pulse.daemon.runs import RunAlreadyActive, RunManager
from pulse.domain.run import StepRecord
from pulse.history.catalog import HistoryCatalog
from pulse.store import runs as run_store
from tests.conftest import make_workflow


def _client(manager: RunManager | None = None) -> TestClient:
    return TestClient(create_app(manager or RunManager()), base_url="http://127.0.0.1")


def _save_global(workspace: Path) -> None:
    save_global_config(
        GlobalConfig(
            version=1,
            agent_binary="agent",
            acp_command=["agent", "acp"],
            auth_method="cursor_login",
            workspace_dir=workspace,
            model="Auto",
            permission_policy="ask",
            completed_at="2026-06-21T12:00:00+00:00",
            acp_test_passed=True,
            default_agent="cursor",
        )
    )


def test_config_without_onboarding_is_empty_on_both_levels(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert _client().get("/api/config").json() == {"global": None, "project": None}


def test_config_lists_the_global_and_the_project_settings(tmp_path, monkeypatch):
    _save_global(tmp_path)
    update_project_defaults(tmp_path, model="sonnet", use_worktree=True)
    monkeypatch.chdir(tmp_path)

    payload = _client().get("/api/config").json()

    assert payload["global"] == {
        "version": 1,
        "agent_binary": "agent",
        "acp_command": ["agent", "acp"],
        "auth_method": "cursor_login",
        "workspace_dir": str(tmp_path),
        "model": "Auto",
        "permission_policy": "ask",
        "completed_at": "2026-06-21T12:00:00+00:00",
        "acp_test_passed": True,
        "default_agent": "cursor",
    }
    assert payload["project"]["source_file"] == str(tmp_path.resolve())
    assert payload["project"]["model"] == "sonnet"
    assert payload["project"]["use_worktree"] is True


def test_patching_global_defaults_changes_only_the_fields_sent(tmp_path):
    _save_global(tmp_path)
    client = _client()

    response = client.patch("/api/config/global", json={"permission_policy": "deny_writes"})

    assert response.status_code == 200
    assert response.json()["global"]["permission_policy"] == "deny_writes"
    assert response.json()["global"]["model"] == "Auto"
    empty = client.patch("/api/config/global", json={})
    assert empty.json()["global"]["permission_policy"] == "deny_writes"
    saved = load_global_config()
    assert saved is not None
    assert (saved.model, saved.default_agent) == ("Auto", "cursor")


def test_creating_the_project_config_returns_its_root(tmp_path):
    response = _client().post("/api/config/project", json={"workspace": str(tmp_path)})

    assert response.json() == {"ok": True, "path": str(tmp_path.resolve())}


def test_resolved_config_reports_the_workspace_asked_for(tmp_path):
    _save_global(tmp_path)
    init_project_config(tmp_path)

    payload = _client().get("/api/config/resolved", params={"workspace": str(tmp_path)}).json()

    assert set(payload) == {
        "agent",
        "model",
        "permission_policy",
        "workspace",
        "use_worktree",
        "acp_command",
        "auth_method",
    }
    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["permission_policy"] == "ask"


@pytest.fixture
def history_run(tmp_path: Path) -> Path:
    run_store.create_run(
        run_id="run-hist",
        workflow_id="default",
        workspace=tmp_path,
        user_prompt="corrigir login",
        steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
    )
    return tmp_path


def test_history_lists_and_searches_the_runs_of_a_project(history_run):
    client = _client()
    params = {"workspace": str(history_run)}

    listed = client.get("/api/history", params=params).json()["items"]
    found = client.get("/api/history", params={**params, "query": "login"}).json()["items"]
    missed = client.get("/api/history", params={**params, "query": "zzz-nada"}).json()["items"]

    assert [item["run_id"] for item in listed] == ["run-hist"]
    assert listed[0]["prompt"] == "corrigir login"
    assert listed[0]["steps"] == [
        {"id": "one", "label": "Um", "status": "pending", "acp_session_id": ""}
    ]
    assert [item["run_id"] for item in found] == ["run-hist"]
    assert missed == []


def test_history_item_is_found_by_id_and_unknown_is_not_found(history_run):
    client = _client()
    params = {"workspace": str(history_run)}
    item_id = client.get("/api/history", params=params).json()["items"][0]["id"]

    item = client.get(f"/api/history/{item_id}", params=params)
    missing = client.get("/api/history/nope", params=params)

    assert item.json()["run_id"] == "run-hist"
    assert (missing.status_code, missing.json()) == (404, {"detail": "item not found"})


def test_the_worktree_of_a_run_the_daemon_executes_is_kept(history_run, monkeypatch, tmp_path):
    """The agent works in that directory: any client, not only the TUI, must be refused."""
    worktree = tmp_path / "wt"
    worktree.mkdir()
    record = run_store.load_run("run-hist")
    assert record is not None
    record.work_in(worktree_path=str(worktree), branch="pulse/run-hist")
    run_store.save(record)
    make_workflow("default")
    release = threading.Event()

    def engine_at_work(**_kwargs: object) -> int:
        release.wait(5)
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_engine", engine_at_work)
    manager = RunManager()
    client = _client(manager)
    params = {"workspace": str(history_run)}
    item_id = client.get("/api/history", params=params).json()["items"][0]["id"]
    state = manager.start_run(
        workflow_id="default", prompt="x", workspace=str(history_run), resume_run_id="run-hist"
    )
    try:
        shown = client.get(f"/api/history/{item_id}/worktree", params=params).json()
        refused = client.delete(f"/api/history/{item_id}/worktree", params=params)
    finally:
        release.set()
        state.ended.wait(5)

    assert shown["active"] is True
    assert refused.status_code == 409
    assert worktree.exists()
    stored = run_store.load_run("run-hist")
    assert stored is not None
    assert stored.worktree_path == str(worktree)


def test_a_run_the_daemon_executes_is_not_deleted_from_history(history_run, monkeypatch, tmp_path):
    """Deleting the run also removes its worktree and the rows the engine still writes."""
    worktree = tmp_path / "wt"
    worktree.mkdir()
    record = run_store.load_run("run-hist")
    assert record is not None
    record.work_in(worktree_path=str(worktree), branch="pulse/run-hist")
    run_store.save(record)
    make_workflow("default")
    release = threading.Event()

    def engine_at_work(**_kwargs: object) -> int:
        release.wait(5)
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_engine", engine_at_work)
    manager = RunManager()
    client = _client(manager)
    params = {"workspace": str(history_run)}
    item_id = client.get("/api/history", params=params).json()["items"][0]["id"]
    state = manager.start_run(
        workflow_id="default", prompt="x", workspace=str(history_run), resume_run_id="run-hist"
    )
    try:
        refused = client.delete(f"/api/history/{item_id}", params=params)
    finally:
        release.set()
        state.ended.wait(5)

    assert (refused.status_code, refused.json()) == (409, {"detail": "run is active"})
    assert worktree.exists()
    assert run_store.load_run("run-hist") is not None


def test_a_resume_arriving_mid_delete_is_refused(history_run, monkeypatch):
    """Two windows: one deletes the run while the other resumes it.

    The active-run check and the delete are one step for the daemon, so the
    resume cannot start on a row and a worktree that are going away.
    """
    make_workflow("default")
    deleting = threading.Event()
    release = threading.Event()

    def slow_delete(_catalog: HistoryCatalog, _item_id: str) -> bool:
        deleting.set()
        release.wait(5)
        return True

    monkeypatch.setattr(HistoryCatalog, "delete", slow_delete)
    monkeypatch.setattr("pulse.daemon.runs.run_engine", lambda **_kwargs: 0)
    manager = RunManager()
    client = _client(manager)
    params = {"workspace": str(history_run)}
    item_id = client.get("/api/history", params=params).json()["items"][0]["id"]
    responses: list[int] = []
    deleter = threading.Thread(
        target=lambda: responses.append(
            client.delete(f"/api/history/{item_id}", params=params).status_code
        )
    )
    deleter.start()
    assert deleting.wait(5)
    try:
        with pytest.raises(RunAlreadyActive):
            manager.start_run(
                workflow_id="default",
                prompt="x",
                workspace=str(history_run),
                resume_run_id="run-hist",
            )
    finally:
        release.set()
        deleter.join(5)

    assert responses == [200]
    assert manager.get("run-hist") is None


def test_answering_an_unknown_prompt_is_not_found():
    """Another window answered first; the late answer must not land anywhere."""
    response = _client().post("/api/prompts/nope/answer", json={"answer": {"index": 1}})

    assert (response.status_code, response.json()) == (404, {"detail": "prompt not found"})


def test_an_unexpected_failure_is_a_500_with_its_message(monkeypatch):
    manager = RunManager()

    def broken() -> list[dict[str, object]]:
        raise RuntimeError("store unreadable")

    monkeypatch.setattr(manager, "list_runs", broken)
    client = TestClient(
        create_app(manager), base_url="http://127.0.0.1", raise_server_exceptions=False
    )

    response = client.get("/api/runs")

    assert (response.status_code, response.json()) == (500, {"detail": "store unreadable"})


def test_an_unexpected_failure_leaves_its_traceback_in_the_daemon_log(monkeypatch, caplog):
    """The client only sees the message; whoever debugs the daemon needs the stack."""
    manager = RunManager()

    def broken() -> list[dict[str, object]]:
        raise RuntimeError("store unreadable")

    monkeypatch.setattr(manager, "list_runs", broken)
    client = TestClient(
        create_app(manager), base_url="http://127.0.0.1", raise_server_exceptions=False
    )

    with caplog.at_level(logging.ERROR, logger="pulse.api.app"):
        client.get("/api/runs")

    [record] = caplog.records
    assert record.getMessage() == "GET /api/runs failed"
    assert record.exc_info is not None
    assert str(record.exc_info[1]) == "store unreadable"
