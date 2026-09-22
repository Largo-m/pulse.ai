from __future__ import annotations

from pathlib import Path

from pulse.history.models import HistoryKind, RunStatus
from pulse.history.recorder import RunRecorder
from pulse.history.runs import latest_run_for, list_runs, load_run, save_run
from pulse.tui.state import CockpitState, LogEntry, LogKind


def test_save_and_load_run_roundtrip(tmp_path: Path):
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Specify")
    state.add_tool_entry(LogKind.READ, "cli.py", "/repo/pulse/cli.py", tool_id="t1")
    state.append_assistant("Plano pronto")

    recorder = RunRecorder(tmp_path, flush_interval=0)
    record = recorder.start("new-issue", "Adicionar login")
    state.acp_session_id = "sess-cursor-1"
    state.upsert_artifact(".pulse/specs/features/login/spec.md", ready=True)
    recorder.observe(state)
    recorder.flush(state)
    recorder.finalize(state, 0)

    loaded = load_run(tmp_path, record.id)
    assert loaded is not None
    saved, entries = loaded
    assert saved.slug == "login"
    assert saved.kind == HistoryKind.SPEC
    assert saved.spec_dir == ".pulse/specs/features/login"
    assert saved.status == RunStatus.COMPLETED
    assert saved.exit_code == 0
    assert saved.acp_session_id == "sess-cursor-1"
    assert saved.acp_sessions == [{"session_id": "sess-cursor-1", "phase_id": "specify"}]
    assert entries == []
    assert not (tmp_path / ".pulse" / "runs" / record.id / "logs.jsonl").exists()


def test_recorder_persists_session_without_artifact(tmp_path: Path):
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.begin_phase("Specify")
    state.acp_session_id = "sess-early"
    recorder = RunRecorder(tmp_path, flush_interval=0)
    recorder.start("new-issue", "Adicionar login")
    recorder.observe(state)
    recorder.flush(state)
    assert recorder.record is not None
    assert recorder.record.acp_session_id == "sess-early"
    assert recorder.record.spec_dir == ""
    loaded = load_run(tmp_path, recorder.record.id)
    assert loaded is not None
    assert loaded[0].acp_session_id == "sess-early"


def test_recorder_keeps_all_acp_sessions(tmp_path: Path):
    state = CockpitState()
    state.configure_workflow("new-issue")
    state.acp_sessions = [
        {"session_id": "sess-specify", "phase_id": "specify"},
        {"session_id": "sess-design", "phase_id": "design"},
    ]
    state.acp_session_id = "sess-design"
    state.upsert_artifact(".pulse/specs/features/login/spec.md", ready=True)
    recorder = RunRecorder(tmp_path, flush_interval=0)
    recorder.start("new-issue", "Adicionar login")
    recorder.observe(state)
    recorder.flush(state)
    assert recorder.record is not None
    loaded = load_run(tmp_path, recorder.record.id)
    assert loaded is not None
    saved = loaded[0]
    assert saved.acp_session_id == "sess-design"
    assert saved.acp_sessions == [
        {"session_id": "sess-specify", "phase_id": "specify"},
        {"session_id": "sess-design", "phase_id": "design"},
    ]


def test_recorder_binds_quick_fix_from_artifact(tmp_path: Path):
    state = CockpitState()
    state.configure_workflow("fix-bug")
    state.begin_phase("Planejar")
    recorder = RunRecorder(tmp_path, flush_interval=0)
    recorder.start("fix-bug", "Corrigir token")
    state.upsert_artifact(".pulse/specs/quick/001-token/TASK.md", ready=True)
    recorder.observe(state)
    recorder.finalize(state, 0)
    assert recorder.record is not None
    assert recorder.record.kind == HistoryKind.SPEC
    assert recorder.record.slug == "001-token"
    assert recorder.record.spec_dir == ".pulse/specs/quick/001-token"


def test_latest_run_matches_spec_dir(tmp_path: Path):
    from pulse.history.models import RunRecord

    first = RunRecord(
        id="run-old",
        workflow_id="new-issue",
        prompt="old",
        status=RunStatus.COMPLETED,
        kind=HistoryKind.ISSUE,
        slug="login",
        spec_dir=".pulse/specs/features/login",
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T01:00:00+00:00",
    )
    second = RunRecord(
        id="run-new",
        workflow_id="new-issue",
        prompt="new",
        status=RunStatus.COMPLETED,
        kind=HistoryKind.ISSUE,
        slug="login",
        spec_dir=".pulse/specs/features/login",
        started_at="2026-01-02T00:00:00+00:00",
        ended_at="2026-01-02T01:00:00+00:00",
    )
    save_run(tmp_path, first, [])
    save_run(
        tmp_path,
        second,
        [LogEntry(kind=LogKind.INFO, title="novo", entry_id=1, phase_id="specify")],
    )
    records = list_runs(tmp_path)
    latest = latest_run_for(
        records,
        spec_dir=".pulse/specs/features/login",
        slug="login",
        kind=HistoryKind.ISSUE,
    )
    assert latest is not None
    assert latest.id == "run-new"


def _write_session_store(root: Path, session_id: str, title: str) -> None:
    import json
    import sqlite3

    store_root = root / session_id
    store_root.mkdir(parents=True)
    db = store_root / "store.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    blob = {
        "role": "assistant",
        "content": [
            {
                "type": "tool-call",
                "toolCallId": f"call-{session_id}",
                "title": title,
                "toolName": "Read",
                "args": {"path": title},
            }
        ],
    }
    con.execute("INSERT INTO blobs(id, data) VALUES (?, ?)", ("1", json.dumps(blob).encode("utf-8")))
    con.commit()
    con.close()


def test_hydrate_assigns_cursor_events_to_session_phase(tmp_path: Path, monkeypatch):
    from pulse.history.models import HistoryItem, HistoryStatus, SpecFlow
    from pulse.history.models import RunRecord
    from pulse.tui.hydrate import hydrate_history_item

    acp_root = tmp_path / "acp-sessions"
    _write_session_store(acp_root, "sess-specify", "spec.md")
    _write_session_store(acp_root, "sess-design", "design.md")
    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", acp_root)
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")
    save_run(
        tmp_path,
        RunRecord(
            id="run-login",
            workflow_id="new-issue",
            prompt="login",
            status=RunStatus.COMPLETED,
            kind=HistoryKind.SPEC,
            slug="login",
            spec_dir=".pulse/specs/features/login",
            acp_session_id="sess-design",
            acp_sessions=[
                {"session_id": "sess-specify", "phase_id": "specify"},
                {"session_id": "sess-design", "phase_id": "design"},
            ],
        ),
        [],
    )
    item = HistoryItem(
        kind=HistoryKind.SPEC,
        slug="login",
        title="login",
        prompt="login",
        status=HistoryStatus.DONE,
        updated_at="",
        spec_dir=".pulse/specs/features/login",
        flow=SpecFlow.FULL,
        run_id="run-login",
    )
    state = hydrate_history_item(item, tmp_path)
    by_phase = {entry.phase_id: entry.title for entry in state.entries}
    assert by_phase["specify"] == "spec.md"
    assert by_phase["design"] == "design.md"
    assert state.acp_session_id == "sess-design"
