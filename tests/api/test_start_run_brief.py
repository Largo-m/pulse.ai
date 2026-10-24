"""Starting a run from the run form: title, description and git options for that run."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pulse.api.app import create_app
from pulse.daemon.runs import RunManager
from pulse.domain.git_options import GitOptions
from pulse.domain.task_brief import TaskBrief
from pulse.store import runs as run_store

FORM = {
    "title": "Corrigir login",
    "description": "erro 500 com e-mail maiúsculo",
    "git": {"use_worktree": True, "atomic_commits": True, "auto_pull_request": False},
    "branch": "corrigir-login",
}


@pytest.fixture
def started(monkeypatch) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr("pulse.daemon.runs.run_engine", lambda **kwargs: calls.append(kwargs) or 0)
    return calls


def _client(manager: RunManager) -> TestClient:
    return TestClient(create_app(manager), base_url="http://127.0.0.1")


def test_the_form_reaches_the_engine_as_a_brief_and_the_run_options(started, tmp_path: Path):
    manager = RunManager()

    response = _client(manager).post(
        "/api/workflows/default/runs", json={**FORM, "workspace": str(tmp_path)}
    )

    assert response.status_code == 200
    state = manager.get(response.json()["id"])
    assert state is not None
    assert state.ended.wait(timeout=5)
    (call,) = started
    assert call["brief"] == TaskBrief(title="Corrigir login", description=FORM["description"])
    assert call["git"] == GitOptions(use_worktree=True, atomic_commits=True)
    assert call["branch"] == "corrigir-login"
    assert call["user_prompt"] == f"Corrigir login\n\n{FORM['description']}"


def test_the_run_list_shows_the_title(started, tmp_path: Path):
    manager = RunManager()
    client = _client(manager)
    run_id = client.post(
        "/api/workflows/default/runs", json={**FORM, "workspace": str(tmp_path)}
    ).json()["id"]
    assert manager.get(run_id).ended.wait(timeout=5)

    (listed,) = client.get("/api/runs").json()["runs"]

    assert listed["title"] == "Corrigir login"
    assert listed["prompt"].startswith("Corrigir login\n\n")


def test_a_resumed_run_is_listed_under_its_stored_title(started, tmp_path: Path):
    """A resume sends no brief, yet the run list must still name the run it reopened."""
    stored = run_store.create_run(
        run_id="run-titled",
        workflow_id="default",
        workspace=tmp_path,
        user_prompt="Corrigir login",
        steps=[],
        brief=TaskBrief(title="Corrigir login", description=FORM["description"]),
    )
    manager = RunManager()
    client = _client(manager)

    client.post(
        "/api/workflows/default/runs",
        json={"resume_run_id": stored.id, "workspace": str(tmp_path)},
    )
    assert manager.get(stored.id).ended.wait(timeout=5)

    (listed,) = client.get("/api/runs").json()["runs"]
    assert listed["title"] == "Corrigir login"


def test_a_run_started_from_a_prompt_has_no_title_and_follows_the_project(started):
    manager = RunManager()

    run_id = _client(manager).post("/api/workflows/default/runs", json={"prompt": "x"}).json()["id"]

    assert manager.get(run_id).ended.wait(timeout=5)
    (call,) = started
    assert call["brief"].is_empty
    assert call["git"] is None
    assert call["user_prompt"] == "x"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"prompt": "x", "title": "y"}, id="prompt-and-title"),
        pytest.param({"prompt": "x", "description": "y"}, id="prompt-and-description"),
        pytest.param(
            {
                "title": "y",
                "git": {"use_worktree": True, "atomic_commits": False, "auto_pull_request": True},
            },
            id="pull-request-without-commits",
        ),
        pytest.param({"title": "y", "git": {"use_worktree": True}}, id="partial-options"),
    ],
)
def test_an_ambiguous_start_is_rejected_before_any_run(started, body):
    """Two tasks or an orphan option would make the engine guess; it refuses instead."""
    manager = RunManager()

    response = _client(manager).post("/api/workflows/default/runs", json=body)

    assert response.status_code == 422
    assert started == []
    assert manager.list_runs() == []
