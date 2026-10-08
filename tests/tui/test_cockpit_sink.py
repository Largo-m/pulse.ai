from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.state import CockpitState, LogKind, PhaseStatus
from tests.conftest import make_workflow

FOUR = [("one", "Um"), ("two", "Dois"), ("three", "Três"), ("four", "Quatro")]


def test_cockpit_sink_records_error_with_reason():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state)
    sink.error("Classificação cancelada", "O agente não definiu o flow (quick ou full).")
    entry = state.entries[-1]
    assert entry.kind == LogKind.ERROR
    assert entry.title == "Classificação cancelada"
    assert "flow" in entry.detail


def test_cockpit_sink_streams_assistant_and_tools():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    dirty = {"n": 0}
    sink = CockpitSink(state, on_change=lambda: dirty.__setitem__("n", dirty["n"] + 1))

    sink.begin_phase("Um")
    assert state.phases[0].status == PhaseStatus.RUNNING

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "Analisando `modelo`"},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.ASSISTANT

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "call-1",
                "title": "Read File",
                "kind": "read",
                "rawInput": {},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.READ
    assert state.entries[-1].pending is True

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "call-1",
                "status": "completed",
                "rawOutput": {"content": "# PRD\n\n**Goal**: capture requirements"},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.READ
    assert state.entries[-1].title == "PRD"
    assert state.entries[-1].pending is False
    assert dirty["n"] > 0


def test_read_update_prefers_locations_over_body():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("PRD")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "call-loc",
                "title": "Read File",
                "kind": "read",
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "call-loc",
                "locations": [{"path": "/repo/docs/STATE.md"}],
                "rawOutput": {"content": "version: 1\n"},
            }
        }
    )
    assert state.entries[-1].title.endswith("STATE.md")
    assert "version" not in state.entries[-1].title
    assert state.phases[0].files == 1


def test_phase_metrics_count_files_and_failed_tools():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Quatro")

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "read-1",
                "title": "Read File",
                "kind": "read",
                "status": "pending",
                "rawInput": {"path": "/repo/pulse/cli.py"},
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "edit-1",
                "title": "Edit File",
                "kind": "edit",
                "status": "pending",
                "rawInput": {"path": "/repo/pulse/cli.py"},
            }
        }
    )
    assert state.phases[3].files == 1

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "write-1",
                "title": "Write File",
                "kind": "write",
                "status": "pending",
                "rawInput": {"path": "/repo/pulse/tui/state.py"},
            }
        }
    )
    assert state.phases[3].files == 2

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "shell-1",
                "title": "Shell",
                "kind": "execute",
                "status": "pending",
                "rawInput": {"command": "pytest -q"},
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "shell-1",
                "status": "failed",
            }
        }
    )
    assert state.phases[3].files == 2
    assert state.phases[3].issues == 1

    sink.begin_phase("Execute — Task T2: Next")
    assert state.phases[3].files == 2
    assert state.phases[3].issues == 1


def test_edit_update_fills_path():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("PRD")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "edit-1",
                "title": "Edit File",
                "kind": "edit",
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "edit-1",
                "status": "completed",
                "content": [
                    {
                        "type": "diff",
                        "path": "/repo/docs/PRD.md",
                    }
                ],
            }
        }
    )
    entry = state.entries[-1]
    assert entry.kind == LogKind.EDIT
    assert entry.title.endswith("PRD.md")


def test_search_update_shows_query_scope_and_hits():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Planejar")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "find-1",
                "title": "Find",
                "kind": "search",
                "rawInput": {"pattern": "dashboard", "path": "/repo/docs"},
            }
        }
    )
    assert state.entries[-1].title == "“dashboard”"
    assert "in docs" in state.entries[-1].detail

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "find-1",
                "status": "completed",
                "rawOutput": {"totalFiles": 4, "truncated": False},
                "locations": [
                    "/repo/docs/a/PRD.md",
                    "/repo/docs/b/PRD.md",
                    "/repo/docs/c/PRD.md",
                    "/repo/docs/STATE.md",
                ],
            }
        }
    )
    entry = state.entries[-1]
    assert entry.kind == LogKind.SEARCH
    assert entry.title == "“dashboard”"
    assert "4 files" in entry.detail
    assert "in docs" in entry.detail
    assert "(+1)" in entry.detail


def test_search_update_count_only_fallback():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state)
    sink.begin_phase("Planejar")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "find-1",
                "title": "Find",
                "kind": "search",
            }
        }
    )
    assert state.entries[-1].pending is True
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "find-1",
                "status": "completed",
                "rawOutput": {"totalFiles": 4, "truncated": False},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.SEARCH
    assert state.entries[-1].title == "4 files"
    assert state.entries[-1].pending is False


def test_cockpit_sink_enriches_from_cursor_store(tmp_path: Path, monkeypatch):
    session_id = "sess-enrich"
    root = tmp_path / "acp-sessions" / session_id
    root.mkdir(parents=True)
    db = root / "store.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    blob = {
        "role": "assistant",
        "content": [
            {
                "type": "tool-call",
                "toolCallId": "call-read\nfc_1",
                "toolName": "Read",
                "args": {"path": "/repo/vendor/NOTES.md"},
            },
            {
                "type": "tool-call",
                "toolCallId": "call-glob\nfc_2",
                "toolName": "Glob",
                "args": {"glob_pattern": "docs/features/**/*"},
            },
        ],
    }
    con.execute("INSERT INTO blobs(id, data) VALUES (?, ?)", ("1", json.dumps(blob).encode()))
    con.commit()
    con.close()
    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", tmp_path / "acp-sessions")
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")

    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("PRD")

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "call-read\nfc_1",
                "title": "Read File",
                "kind": "read",
                "rawInput": {},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.READ
    assert state.entries[-1].title.endswith("NOTES.md")

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "call-glob\nfc_2",
                "title": "Find",
                "kind": "search",
                "rawInput": {},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.SEARCH
    assert "docs/features/**/*" in state.entries[-1].title


def test_cockpit_sink_backfills_vague_search(tmp_path: Path, monkeypatch):
    session_id = "sess-backfill"
    root = tmp_path / "acp-sessions" / session_id
    root.mkdir(parents=True)
    db = root / "store.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    con.commit()
    con.close()
    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", tmp_path / "acp-sessions")
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")

    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("PRD")

    tool_id = "call-late\nfc_9"
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": tool_id,
                "title": "Find",
                "kind": "search",
                "rawInput": {},
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": tool_id,
                "status": "completed",
                "rawOutput": {"totalFiles": 1},
            }
        }
    )
    assert state.entries[-1].title == "1 file"

    con = sqlite3.connect(db)
    blob = {
        "role": "assistant",
        "content": [
            {
                "type": "tool-call",
                "toolCallId": tool_id,
                "toolName": "Glob",
                "args": {
                    "glob_pattern": "**/PROJECT.md",
                    "target_directory": "/repo/.pulse",
                },
            }
        ],
    }
    con.execute("INSERT INTO blobs(id, data) VALUES (?, ?)", ("1", json.dumps(blob).encode()))
    con.commit()
    con.close()

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "call-other\nfc_x",
                "title": "Read File",
                "kind": "read",
                "rawInput": {"path": "/repo/a.md"},
            }
        }
    )
    search = next(entry for entry in state.entries if entry.tool_id == tool_id)
    assert "PROJECT.md" in search.title
    assert "1 file" in search.detail
    assert ".pulse" in search.detail


def test_completed_without_path_keeps_spinner_until_backfill(tmp_path: Path, monkeypatch):
    session_id = "sess-pending-placeholder"
    root = tmp_path / "acp-sessions" / session_id
    root.mkdir(parents=True)
    db = root / "store.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    con.commit()
    con.close()
    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", tmp_path / "acp-sessions")
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")

    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("PRD")
    tool_id = "call-read\nfc_pending"

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": tool_id,
                "title": "Read File",
                "kind": "read",
                "status": "pending",
                "rawInput": {},
            }
        }
    )
    assert state.entries[-1].pending is True
    assert state.entries[-1].title in {"…", "..."}

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": tool_id,
                "status": "in_progress",
            }
        }
    )
    assert state.entries[-1].pending is True

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": tool_id,
                "status": "completed",
            }
        }
    )
    assert state.entries[-1].pending is True
    assert state.entries[-1].title in {"…", "..."}

    con = sqlite3.connect(db)
    blob = {
        "role": "assistant",
        "content": [
            {
                "type": "tool-call",
                "toolCallId": tool_id,
                "toolName": "Read",
                "args": {"path": "/repo/lib/features/home/ui/dashboard_page.dart"},
            }
        ],
    }
    con.execute("INSERT INTO blobs(id, data) VALUES (?, ?)", ("1", json.dumps(blob).encode()))
    con.commit()
    con.close()

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "call-other\nfc_y",
                "title": "Read File",
                "kind": "read",
                "rawInput": {"path": "/repo/a.md"},
            }
        }
    )
    read = next(entry for entry in state.entries if entry.tool_id == tool_id)
    assert read.pending is False
    assert read.title.endswith("dashboard_page.dart")


def test_assistant_chunk_backfills_completed_placeholder(tmp_path: Path, monkeypatch):
    session_id = "sess-assistant-backfill"
    root = tmp_path / "acp-sessions" / session_id
    root.mkdir(parents=True)
    db = root / "store.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    con.commit()
    con.close()
    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", tmp_path / "acp-sessions")
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")

    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("PRD")
    tool_id = "call-last\nfc_z"

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": tool_id,
                "title": "Read File",
                "kind": "read",
                "rawInput": {},
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": tool_id,
                "status": "completed",
            }
        }
    )
    assert state.entries[-1].pending is True

    con = sqlite3.connect(db)
    blob = {
        "role": "assistant",
        "content": [
            {
                "type": "tool-call",
                "toolCallId": tool_id,
                "toolName": "Read",
                "args": {"path": "/repo/lib/app.dart"},
            }
        ],
    }
    con.execute("INSERT INTO blobs(id, data) VALUES (?, ?)", ("1", json.dumps(blob).encode()))
    con.commit()
    con.close()

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "Seguindo com o dashboard."},
            }
        }
    )
    read = next(entry for entry in state.entries if entry.tool_id == tool_id)
    assert read.pending is False
    assert read.title.endswith("app.dart")


def test_search_stays_pending_until_completed(tmp_path: Path, monkeypatch):
    session_id = "sess-search-pending"
    root = tmp_path / "acp-sessions" / session_id
    root.mkdir(parents=True)
    db = root / "store.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    tool_id = "call-search\nfc_1"
    blob = {
        "role": "assistant",
        "content": [
            {
                "type": "tool-call",
                "toolCallId": tool_id,
                "toolName": "Glob",
                "args": {"glob_pattern": "**/PROJECT.md", "target_directory": "/repo/.pulse"},
            }
        ],
    }
    con.execute("INSERT INTO blobs(id, data) VALUES (?, ?)", ("1", json.dumps(blob).encode()))
    con.commit()
    con.close()
    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", tmp_path / "acp-sessions")
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")

    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("PRD")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": tool_id,
                "title": "Find",
                "kind": "search",
                "status": "pending",
                "rawInput": {},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.SEARCH
    assert state.entries[-1].pending is True
    assert "PROJECT.md" in state.entries[-1].title

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": tool_id,
                "status": "in_progress",
            }
        }
    )
    assert state.entries[-1].pending is True

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": tool_id,
                "status": "completed",
                "rawOutput": {"totalFiles": 1},
            }
        }
    )
    assert state.entries[-1].pending is False
    assert "1 file" in state.entries[-1].detail


def test_model_info_sets_header_without_duplicate_entry():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state)
    sink.begin_phase("PRD")
    before = len(state.entries)
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "session_info_update",
                "title": "Modelo: Auto",
            }
        }
    )
    assert state.model_label == "Auto"
    assert len(state.entries) == before
    assert not any(entry.title.startswith("Modelo:") for entry in state.entries)

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "session_info_update",
                "title": "Project Setup Request",
            }
        }
    )
    assert len(state.entries) == before
    assert not any(entry.title == "Project Setup Request" for entry in state.entries)

    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state)
    sink.begin_phase("Fase 1")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {
                    "type": "text",
                    "text": "Preciso de algumas informações\n```text\n",
                },
            }
        }
    )
    assert any(entry.title == "Questionário interativo" for entry in state.entries)


def test_outcome_block_does_not_become_questionnaire():
    """`pulse:outcome` is a code fence, not a question: the speech stays visible."""
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state)
    sink.begin_phase("Fase 1")
    for text in (
        "Review limpo.\n\n```kotlin\nval x = 1\n```\n\n",
        "```pulse:outcome\nstatus: done\nnext: close\n```",
    ):
        sink.handle_update(
            {
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": text},
                }
            }
        )

    assert not any(entry.title == "Questionário interativo" for entry in state.entries)
    spoken = "\n".join(entry.body for entry in state.entries)
    assert "next: close" in spoken


def test_unnamed_fence_with_question_is_still_questionnaire():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state)
    sink.begin_phase("Fase 1")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "```\n1. Qual banco?\nA) Postgres\n"},
            }
        }
    )
    assert any(entry.title == "Questionário interativo" for entry in state.entries)


def test_write_and_edit_register_spec_artifacts():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Dois")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "w1",
                "title": "Write File",
                "kind": "write",
                "rawInput": {"path": "/repo/docs/PROJECT.md"},
            }
        }
    )
    assert [item.path for item in state.artifacts] == ["docs/PROJECT.md"]
    assert state.artifacts[0].ready is False
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "w1",
                "status": "completed",
            }
        }
    )
    assert state.artifacts[0].ready is True
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "w2",
                "title": "Write File",
                "kind": "write",
                "status": "completed",
                "rawInput": {"path": "/repo/docs/ROADMAP.md"},
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "edit-spec",
                "status": "completed",
                "content": [
                    {
                        "type": "diff",
                        "path": "/repo/docs/PROJECT.md",
                    }
                ],
            }
        }
    )
    assert [item.path for item in state.artifacts] == [
        "docs/PROJECT.md",
        "docs/ROADMAP.md",
    ]


def test_read_and_search_do_not_register_artifacts():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("PRD")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "read-1",
                "title": "Read File",
                "kind": "read",
                "status": "completed",
                "rawInput": {"path": "/repo/docs/STATE.md"},
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "find-1",
                "title": "Find",
                "kind": "search",
                "status": "completed",
                "locations": [
                    "/repo/docs/a/PRD.md",
                    "/repo/docs/STATE.md",
                ],
            }
        }
    )
    assert state.artifacts == []
    assert state.artifact_pane_open is False


def test_cockpit_sink_collects_acp_sessions_per_phase():
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    sink = CockpitSink(state)
    sink.set_session_id("sess-one")
    sink.begin_phase("Um")
    sink.set_session_id("sess-two")
    sink.begin_phase("Dois")
    assert state.acp_session_id == "sess-two"
    assert state.acp_sessions == [
        {"session_id": "sess-one", "phase_id": "one"},
        {"session_id": "sess-two", "phase_id": "two"},
    ]


def _chunk(text: str) -> dict:
    return {
        "update": {
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": text},
        }
    }


def _sink_with_counter() -> tuple[CockpitState, CockpitSink, dict[str, int]]:
    state = CockpitState()
    make_workflow("demo", steps=FOUR)
    state.configure_workflow("demo")
    dirty = {"n": 0}
    sink = CockpitSink(state, on_change=lambda: dirty.__setitem__("n", dirty["n"] + 1))
    sink.begin_phase("Um")
    return state, sink, dirty


def test_setup_marker_alone_is_captured_but_not_shown():
    """The marker is a signal for the engine; an empty speech line is noise."""
    state, sink, dirty = _sink_with_counter()
    before_entries, before_emits = len(state.entries), dirty["n"]

    sink.handle_update(_chunk("SETUP_READY "))

    assert sink.agent_text() == "SETUP_READY "
    assert len(state.entries) == before_entries
    assert dirty["n"] == before_emits


def test_non_text_chunks_thoughts_and_unknown_updates_change_nothing():
    """Only text speech and tool calls reach the log; the rest must not repaint."""
    state, sink, dirty = _sink_with_counter()
    before_entries, before_emits = len(state.entries), dirty["n"]

    sink.handle_update(
        {"update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "image"}}}
    )
    sink.handle_update({"update": {"sessionUpdate": "agent_thought_chunk"}})
    sink.handle_update({"update": {"sessionUpdate": "plan"}})
    sink.handle_update({"update": "not an object"})
    sink.handle_update({"update": {"sessionUpdate": "session_info_update", "title": ""}})

    assert sink.agent_text() == ""
    assert len(state.entries) == before_entries
    assert dirty["n"] == before_emits


def test_repeated_tool_call_does_not_duplicate_the_entry():
    """Runtimes may re-announce a call; the log keeps one line per tool id."""
    state, sink, _ = _sink_with_counter()
    call = {
        "update": {
            "sessionUpdate": "tool_call",
            "toolCallId": "read-1",
            "title": "Read File",
            "kind": "read",
            "rawInput": {"path": "/repo/a.md"},
        }
    }

    sink.handle_update(call)
    sink.handle_update(call)

    assert [entry.tool_id for entry in state.entries].count("read-1") == 1


def test_update_for_unseen_tool_without_args_waits_for_them():
    """An update with nothing to show yet must not add a blank pending line."""
    state, sink, _ = _sink_with_counter()
    before = len(state.entries)

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "late-1",
                "status": "in_progress",
            }
        }
    )

    assert len(state.entries) == before


def test_tool_result_for_unseen_tool_is_shown_as_finished():
    """`tool_result` closes the call even without a status field."""
    state, sink, _ = _sink_with_counter()

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_result",
                "toolCallId": "res-1",
                "title": "Read File",
                "kind": "read",
                "rawInput": {"path": "/repo/docs/NOTES.md"},
            }
        }
    )

    entry = state.entries[-1]
    assert entry.tool_id == "res-1"
    assert entry.kind == LogKind.READ
    assert entry.title.endswith("NOTES.md")
    assert entry.pending is False
