from pathlib import Path

from pulse.config.project_config import init_project_config
from pulse.history.catalog import HistoryCatalog
from pulse.plan.specify_state import TaskState, WorkflowState
from pulse.store.sessions import persist_runtime_session
from pulse.store.spec_sessions import record_spec_session
from pulse.tui.hydrate import hydrate_history_item


def _feature(workspace: Path) -> WorkflowState:
    state = WorkflowState.create_new(feature_slug="login-flow", user_prompt="Adicionar login")
    state.approve_phase("specify")
    state.tasks = [TaskState(task_id="T1", title="Criar login", status="done")]
    state.mark_phase_done("execute")
    state.save(workspace)
    (workspace / state.feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    return state


def test_history_replays_recorded_spec_session(tmp_path: Path, monkeypatch):
    init_project_config(tmp_path)
    state = _feature(tmp_path)
    record_spec_session(
        tmp_path,
        spec_dir=state.feature_dir.as_posix(),
        phase_id="execute",
        acp_session_id="sess-tasks",
        task_id="T1",
    )

    def fake_events(session_id: str) -> list[dict[str, str]]:
        if session_id != "sess-tasks":
            return []
        return [
            {
                "kind": "Assistant",
                "title": "Vou criar tasks.md",
                "detail": "Vou criar tasks.md",
                "tool_id": "",
            }
        ]

    monkeypatch.setattr("pulse.tui.hydrate.list_session_events", fake_events)
    item = HistoryCatalog(tmp_path).get("spec:features/login-flow")
    assert item is not None
    hydrated = hydrate_history_item(item, tmp_path)
    assert any(entry.title == "Vou criar tasks.md" for entry in hydrated.entries)
    hydrated.select_task(0)
    visible = hydrated.visible_entries()
    assert visible
    assert all(entry.task_id == "T1" for entry in visible)


def test_history_replays_agent_sessions_inside_spec_window(tmp_path: Path, monkeypatch):
    init_project_config(tmp_path)
    state = _feature(tmp_path)
    persist_runtime_session(
        str(tmp_path),
        pulse_session_id="run-1",
        acp_session_id="sess-specify",
        agent_id="specify",
    )

    def fake_events(session_id: str) -> list[dict[str, str]]:
        if session_id != "sess-specify":
            return []
        return [
            {
                "kind": "Tool",
                "title": "Read",
                "detail": "spec.md",
                "tool_id": "call-1",
            }
        ]

    monkeypatch.setattr("pulse.tui.hydrate.list_session_events", fake_events)
    item = HistoryCatalog(tmp_path).get("spec:features/login-flow")
    assert item is not None
    hydrated = hydrate_history_item(item, tmp_path)
    assert any(entry.title == "Read" and entry.phase_id == "specify" for entry in hydrated.entries)


def test_history_shows_elapsed_for_phases_and_tasks(tmp_path: Path):
    state = WorkflowState.create_new(feature_slug="login-flow", user_prompt="Adicionar login")
    state.created_at = "2026-09-22T21:00:00+00:00"
    state.approve_phase("specify")
    state.phases["specify"].approved_at = "2026-09-22T21:04:30+00:00"
    state.approve_phase("design")
    state.phases["design"].approved_at = "2026-09-22T21:06:00+00:00"
    state.approve_phase("tasks")
    state.phases["tasks"].approved_at = "2026-09-22T21:10:00+00:00"
    state.tasks = [
        TaskState(
            task_id="T1",
            title="Criar login",
            status="done",
            completed_at="2026-09-22T21:12:30+00:00",
        )
    ]
    state.mark_phase_done("execute")
    state.updated_at = "2026-09-22T21:12:30+00:00"
    state.save(tmp_path)
    (tmp_path / state.feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    item = HistoryCatalog(tmp_path).get("spec:features/login-flow")
    assert item is not None
    hydrated = hydrate_history_item(item, tmp_path)
    labels = {phase.id: phase.elapsed_label() for phase in hydrated.phases}
    assert labels["specify"] == "04:30"
    assert labels["design"] == "01:30"
    assert labels["tasks"] == "04:00"
    assert labels["execute"] == "02:30"
    assert hydrated.tasks[0].elapsed_label() == "02:30"
