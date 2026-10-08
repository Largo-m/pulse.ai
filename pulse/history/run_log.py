"""A persisted run as the cockpit rebuilds it: its steps' timings, log and artifacts.

The daemon builds it from the database (`GET /api/runs/{run_id}/log`) and the TUI
parses it back, so the screen reopens a past run without reading SQLite itself.
One codec for both sides keeps the wire format from drifting.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pulse.domain.run import RunRecord, StepRecord, StepStatus


@dataclass(frozen=True)
class LoggedStep:
    step_id: str
    label: str
    status: StepStatus
    started_at: datetime | None = None
    elapsed_seconds: float | None = None
    waiting_seconds: float = 0.0
    carried_seconds: float = 0.0
    has_ended: bool = False

    @classmethod
    def of(cls, step: StepRecord) -> LoggedStep:
        return cls(
            step_id=step.step_id,
            label=step.label,
            status=step.status,
            started_at=step.started_at,
            elapsed_seconds=step.elapsed_seconds(),
            waiting_seconds=step.waiting_seconds,
            carried_seconds=step.carried_seconds,
            has_ended=step.has_ended,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "label": self.label,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "elapsed_seconds": self.elapsed_seconds,
            "waiting_seconds": self.waiting_seconds,
            "carried_seconds": self.carried_seconds,
            "has_ended": self.has_ended,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LoggedStep:
        started = data.get("started_at")
        elapsed = data.get("elapsed_seconds")
        return cls(
            step_id=str(data["step_id"]),
            label=str(data.get("label") or ""),
            status=StepStatus.parse(str(data.get("status") or "")),
            started_at=datetime.fromisoformat(started) if started else None,
            elapsed_seconds=float(elapsed) if elapsed is not None else None,
            waiting_seconds=float(data.get("waiting_seconds") or 0.0),
            carried_seconds=float(data.get("carried_seconds") or 0.0),
            has_ended=bool(data.get("has_ended")),
        )


@dataclass(frozen=True)
class LoggedEvent:
    """One `run_events` row: what the live stream showed, as the session recorded it."""

    step_id: str
    kind: str
    title: str
    detail: str
    tool_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "step_id": self.step_id,
            "kind": self.kind,
            "title": self.title,
            "detail": self.detail,
            "tool_id": self.tool_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LoggedEvent:
        return cls(
            step_id=str(data.get("step_id") or ""),
            kind=str(data.get("kind") or ""),
            title=str(data.get("title") or ""),
            detail=str(data.get("detail") or ""),
            tool_id=str(data.get("tool_id") or ""),
        )


@dataclass(frozen=True)
class LoggedArtifact:
    path: str
    step_id: str = ""


@dataclass(frozen=True)
class RunLog:
    run_id: str
    exec_root: str
    branch: str
    steps: tuple[LoggedStep, ...] = ()
    events: tuple[LoggedEvent, ...] = ()
    artifacts: tuple[LoggedArtifact, ...] = ()

    @classmethod
    def of(
        cls,
        record: RunRecord,
        *,
        events: Sequence[Mapping[str, str]],
        artifacts: Sequence[Mapping[str, str]],
    ) -> RunLog:
        return cls(
            run_id=record.id,
            exec_root=record.exec_root,
            branch=record.branch,
            steps=tuple(LoggedStep.of(step) for step in record.steps),
            events=tuple(LoggedEvent.from_dict(row) for row in events),
            artifacts=tuple(
                LoggedArtifact(path=str(row["path"]), step_id=str(row.get("step_id") or ""))
                for row in artifacts
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "exec_root": self.exec_root,
            "branch": self.branch,
            "steps": [step.to_dict() for step in self.steps],
            "events": [event.to_dict() for event in self.events],
            "artifacts": [{"path": item.path, "step_id": item.step_id} for item in self.artifacts],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunLog:
        return cls(
            run_id=str(data["run_id"]),
            exec_root=str(data.get("exec_root") or ""),
            branch=str(data.get("branch") or ""),
            steps=tuple(LoggedStep.from_dict(item) for item in data.get("steps") or ()),
            events=tuple(LoggedEvent.from_dict(item) for item in data.get("events") or ()),
            artifacts=tuple(
                LoggedArtifact(path=str(item["path"]), step_id=str(item.get("step_id") or ""))
                for item in data.get("artifacts") or ()
            ),
        )
