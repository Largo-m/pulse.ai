from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


MASTER_TASK_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(\w+)\s*\|\s*\w+\s*\|\s*(.+?)\s*\|\s*$"
)
FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
DEPENDENCY_TOKEN = re.compile(r"task_(\d+)", re.IGNORECASE)
COMPLETED_STATUSES = frozenset({"completed", "done"})


@dataclass(frozen=True)
class MasterTaskEntry:
    number: str
    title: str
    status: str
    dependencies: tuple[str, ...]

    @property
    def task_file_name(self) -> str:
        return f"task_{self.number}.md"


@dataclass(frozen=True)
class RunnableTask:
    entry: MasterTaskEntry
    task_file: Path
    master_tasks_file: Path
    task_dir: Path


def resolve_master_tasks_path(artifacts_path: Path, input_file: str) -> Path:
    path = Path(input_file).expanduser()
    if not path.is_absolute():
        path = artifacts_path / path
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Tasks master file não encontrado: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"Tasks master file deve ser um arquivo: {path}")
    if not path.name.endswith("_tasks.md"):
        raise ValueError(f"Tasks master file deve ser um arquivo _tasks.md: {path}")
    return path


def parse_master_tasks(master_tasks_file: Path) -> list[MasterTaskEntry]:
    entries: list[MasterTaskEntry] = []
    for line in master_tasks_file.read_text(encoding="utf-8").splitlines():
        match = MASTER_TASK_ROW.match(line.strip())
        if not match:
            continue
        number, title, status, dependencies_raw = match.groups()
        entries.append(
            MasterTaskEntry(
                number=number.zfill(2),
                title=title.strip(),
                status=status.strip().lower(),
                dependencies=_parse_dependencies(dependencies_raw),
            )
        )
    if not entries:
        raise ValueError(f"nenhuma task encontrada em {master_tasks_file}")
    return entries


def parse_task_frontmatter_status(task_file: Path) -> str | None:
    match = FRONTMATTER.match(task_file.read_text(encoding="utf-8"))
    if not match:
        return None
    for line in match.group(1).splitlines():
        if line.strip().lower().startswith("status:"):
            return line.split(":", 1)[1].strip().lower()
    return None


def is_task_completed(
    *,
    task_file: Path,
    master_tasks_file: Path,
    task_number: str,
) -> bool:
    normalized = task_number.zfill(2)
    frontmatter_status = parse_task_frontmatter_status(task_file)
    if frontmatter_status not in COMPLETED_STATUSES:
        return False

    for entry in parse_master_tasks(master_tasks_file):
        if entry.number == normalized:
            return entry.status in COMPLETED_STATUSES
    return False


def all_tasks_completed(master_tasks_file: Path) -> bool:
    entries = parse_master_tasks(master_tasks_file)
    return all(entry.status in COMPLETED_STATUSES for entry in entries)


def find_next_runnable(master_tasks_file: Path) -> RunnableTask | None:
    entries = parse_master_tasks(master_tasks_file)
    completed_numbers = {
        entry.number for entry in entries if entry.status in COMPLETED_STATUSES
    }
    task_dir = master_tasks_file.parent

    for entry in entries:
        if entry.status in COMPLETED_STATUSES:
            continue
        if not _dependencies_satisfied(entry.dependencies, completed_numbers):
            continue
        task_file = task_dir / entry.task_file_name
        if not task_file.exists():
            raise FileNotFoundError(f"task file não encontrado: {task_file}")
        return RunnableTask(
            entry=entry,
            task_file=task_file,
            master_tasks_file=master_tasks_file,
            task_dir=task_dir,
        )
    return None


def _parse_dependencies(raw: str) -> tuple[str, ...]:
    cleaned = raw.strip()
    if cleaned in {"—", "-", "–", "none", "n/a", ""}:
        return ()
    tokens = DEPENDENCY_TOKEN.findall(cleaned)
    return tuple(number.zfill(2) for number in tokens)


def _dependencies_satisfied(
    dependencies: tuple[str, ...],
    completed_numbers: set[str],
) -> bool:
    return all(number in completed_numbers for number in dependencies)
