from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pulse.tui.cursor_store import (
    CursorStoreIndex,
    find_session_store,
    list_session_events,
    normalize_tool_args,
)


def test_normalize_tool_args_aliases():
    assert normalize_tool_args({"glob_pattern": "**/*.md"})["glob"] == "**/*.md"
    assert normalize_tool_args({"file_path": "/a/b.py"})["path"] == "/a/b.py"


def test_cursor_store_lookup_args(tmp_path: Path, monkeypatch):
    session_id = "sess-test-123"
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
                "toolCallId": "call-1\nfc_1",
                "toolName": "Read",
                "args": {"path": "/repo/docs/STATE.md"},
            },
            {
                "type": "tool-call",
                "toolCallId": "call-2\nfc_2",
                "toolName": "Glob",
                "args": {"glob_pattern": "docs/**/*"},
            },
        ],
    }
    con.execute(
        "INSERT INTO blobs(id, data) VALUES (?, ?)",
        ("1", json.dumps(blob).encode("utf-8")),
    )
    con.commit()
    con.close()

    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", tmp_path / "acp-sessions")
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")

    assert find_session_store(session_id) == db
    index = CursorStoreIndex(session_id)
    read_args = index.lookup_args("call-1\nfc_1")
    assert read_args is not None
    assert read_args["path"].endswith("STATE.md")
    glob_args = index.lookup_args("call-2\nfc_2")
    assert glob_args is not None
    assert glob_args["glob"] == "docs/**/*"
    events = list_session_events(session_id)
    assert any(event["kind"] == "Tool" and "call-1" in event["tool_id"] for event in events)
