"""O log da spec precisa sobreviver ao fim da run — em qualquer runtime.

Antes o histórico vinha do store do Cursor; spec rodada no Claude Code reabria
sem log nenhum.
"""

from __future__ import annotations

from pathlib import Path

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config.project_config import init_project_config
from pulse.store.spec_events import list_spec_events, record_spec_event

SPEC_DIR = ".pulse/specs/features/demo"


def _runner(tmp_path: Path) -> AcpSessionRunner:
    runner = AcpSessionRunner(command=["true"], cwd=str(tmp_path))
    runner.bind_spec(SPEC_DIR)
    runner._phase_id = "design"
    runner._task_id = ""
    runner._session_id = "sess-1"
    return runner


def test_tool_and_text_updates_become_log_entries(tmp_path: Path):
    init_project_config(tmp_path)
    runner = _runner(tmp_path)

    runner._record_spec_event(
        {"update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "Vou ler o "}}}
    )
    runner._record_spec_event(
        {"update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "design."}}}
    )
    runner._record_spec_event(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "call-1",
                "title": "Read",
                "rawInput": {"path": "design.md"},
            }
        }
    )

    rows = list_spec_events(tmp_path, SPEC_DIR)

    assert [(row["kind"], row["title"]) for row in rows] == [
        ("Assistant", "Vou ler o design."),
        ("Tool", "Read"),
    ]
    assert rows[1]["detail"] == "design.md"
    assert rows[0]["phase_id"] == "design"


def test_tool_update_refreshes_the_same_entry(tmp_path: Path):
    init_project_config(tmp_path)
    runner = _runner(tmp_path)

    for title in ("Read", "Read design.md"):
        runner._record_spec_event(
            {"update": {"sessionUpdate": "tool_call_update", "toolCallId": "call-1", "title": title}}
        )

    rows = list_spec_events(tmp_path, SPEC_DIR)

    assert len(rows) == 1
    assert rows[0]["title"] == "Read design.md"


def test_nothing_is_recorded_without_a_spec(tmp_path: Path):
    init_project_config(tmp_path)
    runner = AcpSessionRunner(command=["true"], cwd=str(tmp_path))

    runner._record_spec_event(
        {"update": {"sessionUpdate": "tool_call", "toolCallId": "c", "title": "Read"}}
    )

    assert list_spec_events(tmp_path, SPEC_DIR) == []


def test_pending_text_is_flushed_at_the_end_of_the_prompt(tmp_path: Path):
    init_project_config(tmp_path)
    runner = _runner(tmp_path)
    runner._record_spec_event(
        {"update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "pronto"}}}
    )
    assert list_spec_events(tmp_path, SPEC_DIR) == []

    runner._flush_spec_text()

    assert [row["title"] for row in list_spec_events(tmp_path, SPEC_DIR)] == ["pronto"]


# ------------------------------------------------ o que a aba de histórico lê


def test_hydrate_reads_the_pulse_store(tmp_path: Path):
    from pulse.history.models import HistoryItem, HistoryKind, HistoryStatus, SpecFlow
    from pulse.tui.hydrate import _entries_from_store

    init_project_config(tmp_path)
    record_spec_event(
        tmp_path,
        spec_dir=SPEC_DIR,
        kind="Tool",
        title="Write",
        detail="spec.md",
        phase_id="specify",
        task_id="T1",
        tool_id="call-9",
    )

    item = HistoryItem(
        kind=HistoryKind.SPEC,
        slug="demo",
        title="demo",
        prompt="x",
        status=HistoryStatus.DONE,
        updated_at="2026-09-25T12:00:00",
        spec_dir=SPEC_DIR,
        flow=SpecFlow.FULL,
        steps=[],
    )
    entries = _entries_from_store(item, tmp_path)

    assert len(entries) == 1
    assert entries[0].title == "Write"
    assert entries[0].detail == "spec.md"
    assert entries[0].phase_id == "specify"
    assert entries[0].task_id == "T1"
