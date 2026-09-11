from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pulse.history.models import HistoryStatus

_STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_DATE_RE = re.compile(r"^\*\*Date:\*\*\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_STATUS_ALIASES = {
    "awaiting approval": HistoryStatus.AWAITING_APPROVAL,
    "awaiting_approval": HistoryStatus.AWAITING_APPROVAL,
    "in progress": HistoryStatus.IN_PROGRESS,
    "in_progress": HistoryStatus.IN_PROGRESS,
    "done": HistoryStatus.DONE,
    "blocked": HistoryStatus.BLOCKED,
    "pending": HistoryStatus.PENDING,
}


@dataclass(frozen=True)
class QuickTaskRecord:
    slug: str
    title: str
    status: HistoryStatus
    updated_at: str
    spec_dir: str
    path: Path


def list_quick_tasks(workspace: Path) -> list[QuickTaskRecord]:
    root = workspace / ".pulse/specs/quick"
    if not root.is_dir():
        return []
    records: list[QuickTaskRecord] = []
    for task_path in sorted(root.glob("*/TASK.md")):
        record = parse_quick_task(workspace, task_path)
        if record is not None:
            records.append(record)
    return records


def parse_quick_task(workspace: Path, path: Path) -> QuickTaskRecord | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    slug = path.parent.name.strip()
    if not slug:
        return None
    title = _parse_title(content, slug)
    status = _parse_status(content)
    updated_at = _parse_updated_at(path, content)
    try:
        spec_dir = path.parent.relative_to(workspace).as_posix()
    except ValueError:
        spec_dir = f".pulse/specs/quick/{slug}"
    return QuickTaskRecord(
        slug=slug,
        title=title,
        status=status,
        updated_at=updated_at,
        spec_dir=spec_dir,
        path=path,
    )


def _parse_title(content: str, slug: str) -> str:
    match = _TITLE_RE.search(content)
    if match is None:
        return slug
    title = match.group(1).strip()
    title = re.sub(r"^Quick Task\s+\S+:\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^Summary:\s*Quick Task\s+\S+\s+[—-]\s*", "", title, flags=re.IGNORECASE)
    return title or slug


def _parse_status(content: str) -> HistoryStatus:
    match = _STATUS_RE.search(content)
    if match is None:
        return HistoryStatus.PENDING
    raw = match.group(1).split("|", 1)[0].strip().lower()
    raw = re.sub(r"[^a-z_ ]+", "", raw).strip()
    return _STATUS_ALIASES.get(raw, HistoryStatus.PENDING)


def _parse_updated_at(path: Path, content: str) -> str:
    match = _DATE_RE.search(content)
    if match is not None:
        value = match.group(1).strip()
        if value:
            return value
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
