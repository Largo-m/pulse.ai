from __future__ import annotations

from pathlib import Path
from typing import Any

ACP_LOG_DIR = Path.home() / ".pulse" / "logs" / "acp"


class AcpLogger:
    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._session_id: str | None = None

    @property
    def path(self):
        return None

    def set_session_id(self, session_id: str) -> None:
        self._session_id = session_id

    def log_sent(self, payload: dict[str, Any]) -> None:
        return None

    def log_received(self, message: dict[str, Any]) -> None:
        return None

    def log_update(self, params: dict[str, Any]) -> None:
        return None

    def log_event(self, event: str, data: dict[str, Any] | None = None) -> None:
        return None
