from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pulse.history.events import ArtifactItem, LogEntry, PhaseItem


@runtime_checkable
class RunSnapshot(Protocol):
    phases: list[PhaseItem]
    entries: list[LogEntry]
    artifacts: list[ArtifactItem]
    exit_code: int | None
