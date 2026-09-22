from __future__ import annotations

import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pulse.history.events import PhaseItem
from pulse.history.models import HistoryKind, RunPhaseSnapshot, RunRecord, RunStatus
from pulse.history.runs import save_run
from pulse.history.snapshot import RunSnapshot

_SPEC_RE = re.compile(r"\.pulse/specs/(features|quick)/([^/]+)")


class RunRecorder:
    def __init__(self, workspace: Path, *, flush_interval: float = 0.4) -> None:
        self._workspace = workspace
        self._flush_interval = flush_interval
        self._lock = threading.Lock()
        self._record: RunRecord | None = None
        self._dirty = False
        self._last_flush = 0.0
        self._finalized = False

    @property
    def record(self) -> RunRecord | None:
        return self._record

    def start(self, workflow_id: str, prompt: str) -> RunRecord:
        now = _utc_now()
        record = RunRecord(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            prompt=prompt,
            status=RunStatus.RUNNING,
            kind=_kind_for_workflow(workflow_id),
            started_at=now,
        )
        with self._lock:
            self._record = record
            self._dirty = True
            self._finalized = False
            self._last_flush = 0.0
        return record

    def observe(self, state: RunSnapshot) -> None:
        with self._lock:
            if self._record is None:
                return
            self._sync_record(state)
            self._dirty = True

    def maybe_flush(self, state: RunSnapshot) -> None:
        with self._lock:
            if self._record is None or not self._dirty or self._finalized:
                return
            now = time.monotonic()
            if now - self._last_flush < self._flush_interval:
                return
            record = self._snapshot_locked(state)
            self._dirty = False
            self._last_flush = now
        save_run(self._workspace, record, list(state.entries))

    def flush(self, state: RunSnapshot) -> None:
        with self._lock:
            if self._record is None:
                return
            record = self._snapshot_locked(state)
            self._dirty = False
            self._last_flush = time.monotonic()
        save_run(self._workspace, record, list(state.entries))

    def finalize(self, state: RunSnapshot, exit_code: int | None = None) -> None:
        with self._lock:
            if self._record is None:
                return
            self._sync_record(state)
            if not self._finalized:
                if exit_code is None:
                    exit_code = state.exit_code
                self._record.exit_code = 0 if exit_code is None else exit_code
                if self._record.exit_code != 0:
                    self._record.status = RunStatus.FAILED
                else:
                    self._record.status = RunStatus.COMPLETED
                self._record.ended_at = _utc_now()
                self._finalized = True
            record = self._snapshot_locked(state)
            self._dirty = False
            self._last_flush = time.monotonic()
        save_run(self._workspace, record, list(state.entries))

    def _sync_record(self, state: RunSnapshot) -> None:
        record = self._record
        if record is None:
            return
        record.phases = [_phase_snapshot(phase) for phase in state.phases]
        _sync_sessions(record, state)
        binding = _binding_from_state(state, record.workflow_id)
        if binding is None:
            return
        kind, slug, spec_dir = binding
        record.kind = kind
        record.slug = slug
        record.spec_dir = spec_dir

    def _snapshot_locked(self, state: RunSnapshot) -> RunRecord:
        self._sync_record(state)
        record = self._record
        assert record is not None
        return RunRecord(
            id=record.id,
            workflow_id=record.workflow_id,
            prompt=record.prompt,
            status=record.status,
            kind=record.kind,
            slug=record.slug,
            spec_dir=record.spec_dir,
            started_at=record.started_at,
            ended_at=record.ended_at,
            exit_code=record.exit_code,
            phases=list(record.phases),
            acp_session_id=record.acp_session_id,
            acp_sessions=[dict(item) for item in record.acp_sessions],
        )


def _phase_snapshot(phase: PhaseItem) -> RunPhaseSnapshot:
    return RunPhaseSnapshot(
        id=phase.id,
        label=phase.label,
        status=phase.status.value,
        files=phase.files,
        issues=phase.issues,
    )


def _kind_for_workflow(workflow_id: str) -> HistoryKind | None:
    if workflow_id in {"spec", "new-issue", "fix-bug"}:
        return HistoryKind.SPEC
    return None


def _binding_from_state(state: RunSnapshot, workflow_id: str) -> tuple[HistoryKind, str, str] | None:
    preferred = None
    if workflow_id in {"new-issue"}:
        preferred = "features"
    elif workflow_id == "fix-bug":
        preferred = "quick"
    matches: list[tuple[HistoryKind, str, str]] = []
    for item in state.artifacts:
        parsed = _parse_spec_path(item.path)
        if parsed is not None:
            matches.append(parsed)
    if not matches:
        return None
    if preferred is not None:
        for kind, slug, spec_dir in matches:
            folder = "features" if "/features/" in spec_dir else "quick"
            if folder == preferred:
                return kind, slug, spec_dir
    return matches[-1]


def _parse_spec_path(path: str) -> tuple[HistoryKind, str, str] | None:
    match = _SPEC_RE.search(str(path or "").replace("\\", "/"))
    if match is None:
        return None
    folder, slug = match.group(1), match.group(2)
    if folder == "features":
        return HistoryKind.SPEC, slug, f".pulse/specs/features/{slug}"
    return HistoryKind.SPEC, slug, f".pulse/specs/quick/{slug}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync_sessions(record: RunRecord, state: RunSnapshot) -> None:
    raw = getattr(state, "acp_sessions", None)
    refs = _normalize_session_refs(raw if isinstance(raw, list) else [])
    session_id = str(getattr(state, "acp_session_id", "") or "")
    if session_id and all(item["session_id"] != session_id for item in refs):
        phase_id = ""
        getter = getattr(state, "_entry_phase_id", None)
        if callable(getter):
            phase_id = str(getter() or "")
        refs.append({"session_id": session_id, "phase_id": phase_id})
    if not refs:
        return
    record.acp_sessions = refs
    record.acp_session_id = refs[-1]["session_id"]


def _normalize_session_refs(items: list[object]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        session_id = str(item.get("session_id", "") or "").strip()
        if not session_id or session_id in seen:
            continue
        seen.add(session_id)
        refs.append(
            {
                "session_id": session_id,
                "phase_id": str(item.get("phase_id", "") or ""),
            }
        )
    return refs
