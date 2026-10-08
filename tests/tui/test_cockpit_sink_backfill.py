"""The cockpit sink fills vague tool calls from the runtime's own session store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.state import CockpitState, LogKind
from tests.conftest import make_workflow

FOUR = [("one", "Um"), ("two", "Dois"), ("three", "Três"), ("four", "Quatro")]


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
