from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pulse.config.paths import GLOBAL_CONFIG_DIR

ACP_LOG_DIR = GLOBAL_CONFIG_DIR / "logs" / "acp"


class AcpLogger:
    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._session_id: str | None = None
        self._lock = threading.Lock()
        self._path = _log_path(run_id)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def set_session_id(self, session_id: str) -> None:
        self._session_id = session_id
        self._write_entry("EVENT", event="session_id_set", data={"session_id": session_id})

    def log_sent(self, payload: dict[str, Any]) -> None:
        self._write_entry("OUT", payload=payload)

    def log_received(self, message: dict[str, Any]) -> None:
        self._write_entry("IN", payload=message)

    def log_update(self, params: dict[str, Any]) -> None:
        self._write_entry("UPDATE", payload=params)

    def log_event(self, event: str, data: dict[str, Any] | None = None) -> None:
        self._write_entry("EVENT", event=event, data=data or {})

    def _write_entry(
        self,
        direction: str,
        *,
        payload: dict[str, Any] | None = None,
        event: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "ts": _utc_now(),
            "run_id": self._run_id,
            "session_id": self._session_id,
            "direction": direction,
        }
        if event is not None:
            entry["event"] = event
        if data is not None:
            entry["data"] = data
        if payload is not None:
            entry["payload"] = payload

        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_path(run_id: str) -> Path:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return ACP_LOG_DIR / f"{date_str}-{run_id}.jsonl"
