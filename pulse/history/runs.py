from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from pulse.history.events import LogEntry, LogKind
from pulse.history.models import HistoryKind, RunPhaseSnapshot, RunRecord, RunStatus

RUNS_ROOT = Path(".pulse/runs")


def runs_dir(workspace: Path) -> Path:
    return workspace / RUNS_ROOT


def run_dir(workspace: Path, run_id: str) -> Path:
    return runs_dir(workspace) / run_id


def save_run(workspace: Path, record: RunRecord, entries: list[LogEntry]) -> Path:
    target = run_dir(workspace, record.id)
    target.mkdir(parents=True, exist_ok=True)
    meta_path = target / "meta.yaml"
    meta_path.write_text(
        yaml.safe_dump(run_to_dict(record), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return target


def load_run(workspace: Path, run_id: str) -> tuple[RunRecord, list[LogEntry]] | None:
    meta_path = run_dir(workspace, run_id) / "meta.yaml"
    if not meta_path.is_file():
        return None
    try:
        data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    record = run_from_dict(data)
    entries = load_run_logs(workspace, run_id)
    return record, entries


def load_run_logs(workspace: Path, run_id: str) -> list[LogEntry]:
    logs_path = run_dir(workspace, run_id) / "logs.jsonl"
    if not logs_path.is_file():
        return []
    entries: list[LogEntry] = []
    try:
        text = logs_path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(log_entry_from_dict(payload))
    return entries


def list_runs(workspace: Path) -> list[RunRecord]:
    root = runs_dir(workspace)
    if not root.is_dir():
        return []
    records: list[RunRecord] = []
    for meta_path in sorted(root.glob("*/meta.yaml")):
        try:
            data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict):
            records.append(run_from_dict(data))
    records.sort(key=lambda item: item.ended_at or item.started_at, reverse=True)
    return records


def latest_run_for(
    records: list[RunRecord],
    *,
    spec_dir: str,
    slug: str,
    kind: HistoryKind,
) -> RunRecord | None:
    for record in records:
        if spec_dir and record.spec_dir == spec_dir:
            return record
    for record in records:
        if record.slug == slug and _kinds_match(record.kind, kind):
            return record
    return None


def _kinds_match(record_kind: HistoryKind | None, wanted: HistoryKind) -> bool:
    if record_kind is None:
        return False
    if record_kind == wanted:
        return True
    spec_kinds = {HistoryKind.SPEC, HistoryKind.ISSUE, HistoryKind.FIX}
    return record_kind in spec_kinds and wanted in spec_kinds


def run_to_dict(record: RunRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "workflow_id": record.workflow_id,
        "prompt": record.prompt,
        "status": record.status.value,
        "kind": record.kind.value if record.kind is not None else "",
        "slug": record.slug,
        "spec_dir": record.spec_dir,
        "started_at": record.started_at,
        "ended_at": record.ended_at,
        "exit_code": record.exit_code,
        "phases": [
            {
                "id": phase.id,
                "label": phase.label,
                "status": phase.status,
                "files": phase.files,
                "issues": phase.issues,
            }
            for phase in record.phases
        ],
        "acp_session_id": record.acp_session_id,
        "acp_sessions": [
            {
                "session_id": str(item.get("session_id", "")),
                "phase_id": str(item.get("phase_id", "")),
            }
            for item in record.acp_sessions
            if isinstance(item, dict) and item.get("session_id")
        ],
    }


def run_from_dict(data: dict[str, Any]) -> RunRecord:
    kind_raw = str(data.get("kind", "")).strip()
    kind: HistoryKind | None = None
    if kind_raw in {HistoryKind.SPEC.value, HistoryKind.ISSUE.value, HistoryKind.FIX.value}:
        kind = HistoryKind(kind_raw)
    status_raw = str(data.get("status", RunStatus.RUNNING.value))
    try:
        status = RunStatus(status_raw)
    except ValueError:
        status = RunStatus.RUNNING
    phases_raw = data.get("phases", [])
    phases: list[RunPhaseSnapshot] = []
    if isinstance(phases_raw, list):
        for item in phases_raw:
            if not isinstance(item, dict):
                continue
            phases.append(
                RunPhaseSnapshot(
                    id=str(item.get("id", "")),
                    label=str(item.get("label", "")),
                    status=str(item.get("status", "")),
                    files=int(item.get("files", 0) or 0),
                    issues=int(item.get("issues", 0) or 0),
                )
            )
    exit_code = data.get("exit_code")
    sessions_raw = data.get("acp_sessions", [])
    acp_sessions: list[dict[str, str]] = []
    if isinstance(sessions_raw, list):
        seen: set[str] = set()
        for item in sessions_raw:
            if not isinstance(item, dict):
                continue
            session_id = str(item.get("session_id", "")).strip()
            if not session_id or session_id in seen:
                continue
            seen.add(session_id)
            acp_sessions.append(
                {
                    "session_id": session_id,
                    "phase_id": str(item.get("phase_id", "")),
                }
            )
    fallback_id = str(data.get("acp_session_id", "")).strip()
    if fallback_id and fallback_id not in {item["session_id"] for item in acp_sessions}:
        acp_sessions.append({"session_id": fallback_id, "phase_id": ""})
    return RunRecord(
        id=str(data.get("id", "")),
        workflow_id=str(data.get("workflow_id", "")),
        prompt=str(data.get("prompt", "")),
        status=status,
        kind=kind,
        slug=str(data.get("slug", "")),
        spec_dir=str(data.get("spec_dir", "")),
        started_at=str(data.get("started_at", "")),
        ended_at=str(data.get("ended_at", "")),
        exit_code=int(exit_code) if exit_code is not None and str(exit_code) != "" else None,
        phases=phases,
        acp_session_id=acp_sessions[-1]["session_id"] if acp_sessions else fallback_id,
        acp_sessions=acp_sessions,
    )


def log_entry_to_dict(entry: LogEntry) -> dict[str, Any]:
    return {
        "kind": entry.kind.value,
        "title": entry.title,
        "detail": entry.detail,
        "body": entry.body,
        "active": False,
        "pending": False,
        "entry_id": entry.entry_id,
        "tool_id": entry.tool_id,
        "phase_id": entry.phase_id,
        "task_id": entry.task_id,
    }


def log_entry_from_dict(data: dict[str, Any]) -> LogEntry:
    kind_raw = str(data.get("kind", LogKind.INFO.value))
    try:
        kind = LogKind(kind_raw)
    except ValueError:
        kind = LogKind.INFO
    return LogEntry(
        kind=kind,
        title=str(data.get("title", "")),
        detail=str(data.get("detail", "")),
        body=str(data.get("body", "")),
        active=False,
        pending=False,
        entry_id=int(data.get("entry_id", 0) or 0),
        tool_id=str(data.get("tool_id", "")),
        phase_id=str(data.get("phase_id", "")),
        task_id=str(data.get("task_id", "")),
    )
