from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_CURSOR_DIR = Path.home() / ".cursor"
_ACP_SESSIONS = _CURSOR_DIR / "acp-sessions"
_CHATS = _CURSOR_DIR / "chats"


def find_session_store(session_id: str) -> Path | None:
    if not session_id:
        return None
    flat = _ACP_SESSIONS / session_id / "store.db"
    if flat.is_file():
        return flat
    if not _CHATS.is_dir():
        return None
    try:
        for hash_dir in _CHATS.iterdir():
            candidate = hash_dir / session_id / "store.db"
            if candidate.is_file():
                return candidate
    except OSError:
        return None
    return None


def normalize_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    out = dict(args)
    if "glob_pattern" in out and "glob" not in out:
        out["glob"] = out["glob_pattern"]
    if "target_file" in out and "path" not in out:
        out["path"] = out["target_file"]
    if "file_path" in out and "path" not in out:
        out["path"] = out["file_path"]
    if "target_directory" in out and "path" not in out:
        out["path"] = out["target_directory"]
    return out


class CursorStoreIndex:
    def __init__(self, session_id: str | None = None) -> None:
        self._session_id = session_id or ""
        self._args_by_id: dict[str, dict[str, Any]] = {}
        self._db_mtime: float | None = None
        self._db_path: Path | None = None

    def set_session(self, session_id: str | None) -> None:
        sid = session_id or ""
        if sid == self._session_id:
            return
        self._session_id = sid
        self._args_by_id = {}
        self._db_mtime = None
        self._db_path = None

    def lookup_args(self, tool_call_id: str, *, force: bool = False) -> dict[str, Any] | None:
        if not tool_call_id or not self._session_id:
            return None
        if force:
            self._db_mtime = None
        self._refresh_if_needed()
        args = self._resolve(tool_call_id)
        if args is not None:
            return dict(args)
        self._db_mtime = None
        self._refresh_if_needed()
        args = self._resolve(tool_call_id)
        return dict(args) if args is not None else None

    def _resolve(self, tool_call_id: str) -> dict[str, Any] | None:
        args = self._args_by_id.get(tool_call_id)
        if args is not None:
            return args
        prefix = tool_call_id.split("\n", 1)[0]
        if prefix and prefix != tool_call_id:
            return self._args_by_id.get(prefix)
        return None

    def _refresh_if_needed(self) -> None:
        path = self._db_path or find_session_store(self._session_id)
        if path is None:
            return
        self._db_path = path
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if self._db_mtime is not None and mtime <= self._db_mtime and self._args_by_id:
            return
        self._db_mtime = mtime
        self._args_by_id = _load_tool_args(path)


def _load_tool_args(db_path: Path) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return found
    try:
        rows = con.execute("SELECT data FROM blobs").fetchall()
    except sqlite3.Error:
        con.close()
        return found
    for (data,) in rows:
        try:
            raw = bytes(data)
            text = raw.decode("utf-8")
            obj = json.loads(text)
        except Exception:
            continue
        content = obj.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool-call":
                continue
            tool_id = item.get("toolCallId")
            args = item.get("args")
            if not isinstance(tool_id, str) or not tool_id:
                continue
            if not isinstance(args, dict) or not args:
                continue
            normalized = normalize_tool_args(args)
            found[tool_id] = normalized
            prefix = tool_id.split("\n", 1)[0]
            if prefix and prefix not in found:
                found[prefix] = normalized
    con.close()
    return found
