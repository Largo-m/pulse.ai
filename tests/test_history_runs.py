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
    assert entries == []
    assert not (tmp_path / ".pulse" / "runs" / record.id / "logs.jsonl").exists()


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
