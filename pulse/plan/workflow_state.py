from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from pulse.status_labels import status_label

WORKFLOW_VERSION = 1
PHASE_ORDER = ("specify", "design", "tasks", "execute")
OPTIONAL_PHASES = frozenset({"design"})


class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    SKIPPED = "skipped"
    DONE = "done"
    FAILED = "failed"


@dataclass
class PhaseState:
    status: PhaseStatus = PhaseStatus.PENDING
    artifact: str = ""
    skip: bool = False
    skip_reason: str = ""
    approved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "artifact": self.artifact,
            "skip": self.skip,
            "skip_reason": self.skip_reason,
            "approved_at": self.approved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhaseState:
        status_raw = str(data.get("status", PhaseStatus.PENDING.value))
        try:
            status = PhaseStatus(status_raw)
        except ValueError:
            status = PhaseStatus.PENDING
        return cls(
            status=status,
            artifact=str(data.get("artifact", "")),
            skip=bool(data.get("skip", False)),
            skip_reason=str(data.get("skip_reason", "")),
            approved_at=str(data.get("approved_at", "")),
        )


@dataclass
class TaskState:
    task_id: str
    title: str = ""
    status: str = "pending"
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.task_id,
            "title": self.title,
            "status": self.status,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskState:
        return cls(
            task_id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            status=str(data.get("status", "pending")),
            completed_at=str(data.get("completed_at", "")),
        )


@dataclass
class WorkflowState:
    feature_slug: str
    user_prompt: str
    complexity: str = "large"
    current_phase: str = "specify"
    phases: dict[str, PhaseState] = field(default_factory=dict)
    tasks: list[TaskState] = field(default_factory=list)
    current_task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = _utc_now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        for phase_name in PHASE_ORDER:
            if phase_name not in self.phases:
                artifact = _default_artifact(phase_name)
                self.phases[phase_name] = PhaseState(artifact=artifact)

    @property
    def feature_dir(self) -> Path:
        return Path(".pulse/specs/features") / self.feature_slug

    @property
    def workflow_path(self) -> Path:
        return self.feature_dir / "workflow.yaml"

    def touch(self) -> None:
        self.updated_at = _utc_now()

    def mark_phase_in_progress(self, phase: str) -> None:
        self.current_phase = phase
        self.phases[phase].status = PhaseStatus.IN_PROGRESS
        self.touch()

    def mark_phase_awaiting_approval(self, phase: str) -> None:
        self.current_phase = phase
        self.phases[phase].status = PhaseStatus.AWAITING_APPROVAL
        self.touch()

    def approve_phase(self, phase: str) -> None:
        self.phases[phase].status = PhaseStatus.APPROVED
        self.phases[phase].approved_at = _utc_now()
        self.touch()

    def mark_phase_skipped(self, phase: str, reason: str) -> None:
        phase_state = self.phases[phase]
        phase_state.status = PhaseStatus.SKIPPED
        phase_state.skip = True
        phase_state.skip_reason = reason
        self.touch()

    def mark_phase_done(self, phase: str) -> None:
        self.phases[phase].status = PhaseStatus.DONE
        self.touch()

    def mark_phase_failed(self, phase: str) -> None:
        self.current_phase = phase
        self.phases[phase].status = PhaseStatus.FAILED
        self.touch()

    def should_run_phase(self, phase: str) -> bool:
        phase_state = self.phases[phase]
        if phase_state.skip or phase_state.status == PhaseStatus.SKIPPED:
            return False
        return True

    def next_phase_after(self, phase: str) -> str | None:
        try:
            index = PHASE_ORDER.index(phase)
        except ValueError:
            return None
        for candidate in PHASE_ORDER[index + 1 :]:
            if self.should_run_phase(candidate):
                return candidate
        return None

    def pending_tasks(self) -> list[TaskState]:
        return [task for task in self.tasks if task.status != "done"]

    def next_pending_task(self) -> TaskState | None:
        for task in self.tasks:
            if task.status != "done":
                return task
        return None

    def mark_task_done(self, task_id: str) -> None:
        for task in self.tasks:
            if task.task_id == task_id:
                task.status = "done"
                task.completed_at = _utc_now()
                self.current_task_id = task_id
                self.touch()
                return

    def mark_task_failed(self, task_id: str) -> None:
        for task in self.tasks:
            if task.task_id == task_id:
                task.status = "failed"
                self.current_task_id = task_id
                self.touch()
                return

    def sync_tasks_from_markdown(self, tasks_md_path: Path) -> None:
        if not tasks_md_path.is_file():
            return
        parsed = parse_tasks_from_markdown(tasks_md_path.read_text(encoding="utf-8"))
        existing = {task.task_id: task for task in self.tasks}
        merged: list[TaskState] = []
        for entry in parsed:
            prior = existing.get(entry.task_id)
            if prior is not None:
                merged.append(
                    TaskState(
                        task_id=entry.task_id,
                        title=entry.title,
                        status=prior.status,
                        completed_at=prior.completed_at,
                    )
                )
            else:
                merged.append(TaskState(task_id=entry.task_id, title=entry.title))
        self.tasks = merged
        self.touch()

    def all_tasks_done(self) -> bool:
        return bool(self.tasks) and all(task.status == "done" for task in self.tasks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": WORKFLOW_VERSION,
            "feature_slug": self.feature_slug,
            "user_prompt": self.user_prompt,
            "complexity": self.complexity,
            "current_phase": self.current_phase,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_task_id": self.current_task_id,
            "phases": {name: phase.to_dict() for name, phase in self.phases.items()},
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowState:
        phases_raw = data.get("phases", {})
        phases: dict[str, PhaseState] = {}
        if isinstance(phases_raw, dict):
            for name, phase_data in phases_raw.items():
                if isinstance(phase_data, dict):
                    phases[str(name)] = PhaseState.from_dict(phase_data)

        tasks_raw = data.get("tasks", [])
        tasks: list[TaskState] = []
        if isinstance(tasks_raw, list):
            for item in tasks_raw:
                if isinstance(item, dict):
                    tasks.append(TaskState.from_dict(item))

        return cls(
            feature_slug=str(data.get("feature_slug", "")),
            user_prompt=str(data.get("user_prompt", "")),
            complexity=str(data.get("complexity", "large")),
            current_phase=str(data.get("current_phase", "specify")),
            phases=phases,
            tasks=tasks,
            current_task_id=data.get("current_task_id"),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )

    def save(self, workspace: Path) -> Path:
        feature_dir = workspace / self.feature_dir
        feature_dir.mkdir(parents=True, exist_ok=True)
        path = workspace / self.workflow_path
        path.write_text(
            yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, path: Path) -> WorkflowState:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"workflow.yaml inválido: {path}")
        return cls.from_dict(data)

    @classmethod
    def create_new(cls, *, feature_slug: str, user_prompt: str) -> WorkflowState:
        return cls(feature_slug=feature_slug, user_prompt=user_prompt)


@dataclass(frozen=True)
class ParsedTask:
    task_id: str
    title: str


def slugify_feature(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"[^\w\s-]", "", normalized, flags=re.UNICODE)
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        return "feature"
    return normalized[:64].rstrip("-")


_HEADING_TASK = re.compile(r"^#{2,3}\s+(T\d+)\s*[:.\-—]\s*(.+?)\s*$", re.MULTILINE)
_TABLE_TASK = re.compile(r"^\|\s*(T\d+)\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)
_TITLE_SKIP = frozenset({"title", "título", "titulo"})


def _clean_task_title(title: str) -> str:
    cleaned = title.strip().strip("*").strip()
    cleaned = re.sub(r"\s*\[P\]\s*$", "", cleaned).strip()
    return cleaned


def parse_tasks_from_markdown(content: str) -> list[ParsedTask]:
    tasks: list[ParsedTask] = []
    seen: set[str] = set()
    for match in _HEADING_TASK.finditer(content):
        task_id = match.group(1)
        title = _clean_task_title(match.group(2))
        if not title or task_id in seen:
            continue
        seen.add(task_id)
        tasks.append(ParsedTask(task_id=task_id, title=title))
    if tasks:
        return tasks
    for match in _TABLE_TASK.finditer(content):
        task_id = match.group(1)
        title = _clean_task_title(match.group(2))
        if not title or title.casefold() in _TITLE_SKIP or task_id in seen:
            continue
        seen.add(task_id)
        tasks.append(ParsedTask(task_id=task_id, title=title))
    return tasks


def list_feature_workflows(workspace: Path) -> list[WorkflowState]:
    features_root = workspace / ".pulse/specs/features"
    if not features_root.is_dir():
        return []

    workflows: list[WorkflowState] = []
    for workflow_path in sorted(features_root.glob("*/workflow.yaml")):
        try:
            state = WorkflowState.load(workflow_path)
        except (OSError, ValueError, yaml.YAMLError):
            continue
        workflows.append(state)
    return workflows


def find_resumable_workflows(workspace: Path) -> list[WorkflowState]:
    found: list[WorkflowState] = []
    for state in list_feature_workflows(workspace):
        tasks_path = workspace / state.feature_dir / "tasks.md"
        if tasks_path.is_file():
            state.sync_tasks_from_markdown(tasks_path)
        if _is_workflow_incomplete(state):
            found.append(state)
    return found


def _is_workflow_incomplete(state: WorkflowState) -> bool:
    if state.phases["execute"].status not in {PhaseStatus.DONE, PhaseStatus.SKIPPED}:
        return True
    if state.tasks and not state.all_tasks_done():
        return True
    for phase_name in PHASE_ORDER:
        status = state.phases[phase_name].status
        if status in {
            PhaseStatus.PENDING,
            PhaseStatus.IN_PROGRESS,
            PhaseStatus.AWAITING_APPROVAL,
            PhaseStatus.FAILED,
        }:
            return True
    return False


def _default_artifact(phase: str) -> str:
    mapping = {
        "specify": "spec.md",
        "design": "design.md",
        "tasks": "tasks.md",
        "execute": "",
    }
    return mapping.get(phase, "")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_workflow_by_slug(workspace: Path, slug: str) -> WorkflowState | None:
    for state in list_feature_workflows(workspace):
        if state.feature_slug == slug:
            return state
    return None


def workflow_is_incomplete(state: WorkflowState) -> bool:
    """Workflow ainda tem fase ou task pendente — dá para retomar."""
    return _is_workflow_incomplete(state)


def resume_summary(state: WorkflowState) -> str:
    """Resumo curto de onde o workflow parou, para exibir na escolha."""
    phase = state.current_phase
    raw = state.phases[phase].status if phase in state.phases else PhaseStatus.PENDING
    status = status_label(raw)
    done = sum(1 for item in state.tasks if item.status == PhaseStatus.DONE)
    if state.tasks:
        return f"{phase} ({status}) · tasks {done}/{len(state.tasks)}"
    return f"{phase} ({status})"
