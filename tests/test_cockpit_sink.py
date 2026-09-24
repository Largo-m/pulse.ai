from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.state import CockpitState, LogKind, PhaseStatus


def test_cockpit_sink_records_error_with_reason():
    state = CockpitState()
    state.configure_workflow("spec")
    sink = CockpitSink(state)
    sink.error("Classificação cancelada", "O agente não definiu o flow (quick ou full).")
    entry = state.entries[-1]
    assert entry.kind == LogKind.ERROR
    assert entry.title == "Classificação cancelada"
    assert "flow" in entry.detail


def test_cockpit_sink_streams_assistant_and_tools():
    state = CockpitState()
    state.configure_workflow("new-issue")
    dirty = {"n": 0}
    sink = CockpitSink(state, on_change=lambda: dirty.__setitem__("n", dirty["n"] + 1))

    sink.begin_phase("Fase Specify")
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
                "rawOutput": {"content": "# Specify\n\n**Goal**: capture requirements"},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.READ
    assert state.entries[-1].title == "Specify"
    assert state.entries[-1].pending is False
    assert dirty["n"] > 0


def test_read_update_prefers_locations_over_body():
    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Specify")
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
                "locations": [{"path": "/repo/.pulse/specs/project/STATE.md"}],
                "rawOutput": {"content": "version: 1\n"},
            }
        }
    )
    assert state.entries[-1].title.endswith("STATE.md")
    assert "version" not in state.entries[-1].title
    assert state.phases[0].files == 1


def test_phase_metrics_count_files_and_failed_tools():
    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Fase Execute")

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
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Specify")
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
                        "path": "/repo/.pulse/specs/features/demo/spec.md",
                    }
                ],
            }
        }
    )
    entry = state.entries[-1]
    assert entry.kind == LogKind.EDIT
    assert entry.title.endswith("spec.md")
    assert "features" in entry.title


def test_search_update_shows_query_scope_and_hits():
    state = CockpitState()
    state.configure_workflow("fix-bug")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Planejar")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "find-1",
                "title": "Find",
                "kind": "search",
                "rawInput": {"pattern": "dashboard", "path": "/repo/.pulse/specs"},
            }
        }
    )
    assert state.entries[-1].title == "“dashboard”"
    assert "in .pulse/specs" in state.entries[-1].detail

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "find-1",
                "status": "completed",
                "rawOutput": {"totalFiles": 4, "truncated": False},
                "locations": [
                    "/repo/.pulse/specs/features/a/spec.md",
                    "/repo/.pulse/specs/features/b/spec.md",
                    "/repo/.pulse/specs/features/c/spec.md",
                    "/repo/.pulse/specs/project/STATE.md",
                ],
            }
        }
    )
    entry = state.entries[-1]
    assert entry.kind == LogKind.SEARCH
    assert entry.title == "“dashboard”"
    assert "4 files" in entry.detail
    assert "in .pulse/specs" in entry.detail
    assert "(+1)" in entry.detail


def test_search_update_count_only_fallback():
    state = CockpitState()
    state.configure_workflow("fix-bug")
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
                "args": {"path": "/repo/.pulse/skills/pulse-spec-driven/SKILL.md"},
            },
            {
                "type": "tool-call",
                "toolCallId": "call-glob\nfc_2",
                "toolName": "Glob",
                "args": {"glob_pattern": ".pulse/specs/features/**/*"},
            },
        ],
    }
    con.execute("INSERT INTO blobs(id, data) VALUES (?, ?)", ("1", json.dumps(blob).encode()))
    con.commit()
    con.close()
    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", tmp_path / "acp-sessions")
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")

    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("Specify")

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
    assert state.entries[-1].title.endswith("SKILL.md")

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
    assert ".pulse/specs/features/**/*" in state.entries[-1].title


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
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("Specify")

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
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("Specify")
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
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("Specify")
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
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase("Specify")
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
    state.configure_workflow("new-issue")
    sink = CockpitSink(state)
    sink.begin_phase("Specify")
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
    state.configure_workflow("setup-project")
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


def test_write_and_edit_register_spec_artifacts():
    state = CockpitState()
    state.configure_workflow("setup-project")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Fase 2 — Gerando specs")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "w1",
                "title": "Write File",
                "kind": "write",
                "rawInput": {"path": "/repo/.pulse/specs/project/PROJECT.md"},
            }
        }
    )
    assert [item.path for item in state.artifacts] == [".pulse/specs/project/PROJECT.md"]
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
                "rawInput": {"path": "/repo/.pulse/specs/project/ROADMAP.md"},
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
                        "path": "/repo/.pulse/specs/project/PROJECT.md",
                    }
                ],
            }
        }
    )
    assert [item.path for item in state.artifacts] == [
        ".pulse/specs/project/PROJECT.md",
        ".pulse/specs/project/ROADMAP.md",
    ]


def test_read_and_search_do_not_register_artifacts():
    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Specify")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "read-1",
                "title": "Read File",
                "kind": "read",
                "status": "completed",
                "rawInput": {"path": "/repo/.pulse/specs/project/STATE.md"},
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
                    "/repo/.pulse/specs/features/a/spec.md",
                    "/repo/.pulse/specs/project/STATE.md",
                ],
            }
        }
    )
    assert state.artifacts == []
    assert state.artifact_pane_open is False


def test_cockpit_sink_collects_acp_sessions_per_phase():
    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state)
    sink.set_session_id("sess-specify")
    sink.begin_phase("Specify")
    sink.set_session_id("sess-design")
    sink.begin_phase("Design")
    assert state.acp_session_id == "sess-design"
    assert state.acp_sessions == [
        {"session_id": "sess-specify", "phase_id": "specify"},
        {"session_id": "sess-design", "phase_id": "design"},
    ]
