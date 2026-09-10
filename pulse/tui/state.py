from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pulse.tui.artifacts import (
    artifact_key,
    extract_spec_artifacts_from_text,
    is_spec_artifact,
)


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"


class LogKind(str, Enum):
    SEARCH = "Search"
    LIST = "List"
    READ = "Read"
    EDIT = "Edit"
    WRITE = "Write"
    SHELL = "Shell"
    INFO = "Info"
    ASSISTANT = "Assistant"
    QUESTION = "Question"
    ANSWER = "Answer"
    TOOL = "Tool"


@dataclass
class PhaseItem:
    id: str
    label: str
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: float | None = None
    ended_at: float | None = None
    files: int = 0
    issues: int = 0
    _seen_files: set[str] = field(default_factory=set, repr=False, compare=False)
    _seen_issues: set[str] = field(default_factory=set, repr=False, compare=False)

    def elapsed_label(self, now: float | None = None) -> str:
        if self.started_at is None:
            return ""
        if self.status == PhaseStatus.RUNNING:
            end = now or time.monotonic()
        elif self.ended_at is not None:
            end = self.ended_at
        else:
            return ""
        elapsed = int(end - self.started_at)
        minutes, seconds = divmod(max(0, elapsed), 60)
        return f"{minutes:02d}:{seconds:02d}"

    def finish(self, ended_at: float | None = None) -> None:
        if self.status == PhaseStatus.RUNNING and self.started_at is not None:
            self.ended_at = ended_at if ended_at is not None else time.monotonic()
        if self.status == PhaseStatus.RUNNING:
            self.status = PhaseStatus.DONE


@dataclass
class LogEntry:
    kind: LogKind
    title: str
    detail: str = ""
    body: str = ""
    active: bool = False
    pending: bool = False
    entry_id: int = 0
    tool_id: str = ""
    phase_id: str = ""


@dataclass
class ArtifactItem:
    path: str
    phase_id: str = ""
    ready: bool = False


Listener = Callable[[], None]
_FOCUS_CYCLE = ("phases", "stream", "artifact")


WORKFLOW_PHASES: dict[str, tuple[tuple[str, str], ...]] = {
    "new-issue": (
        ("specify", "Specify"),
        ("design", "Design"),
        ("tasks", "Tasks"),
        ("execute", "Execute"),
    ),
    "fix-bug": (
        ("plan", "Planejar"),
        ("implement", "Implementar"),
    ),
    "setup-project": (
        ("phase1", "Análise do projeto"),
        ("phase2", "Gerando specs"),
    ),
    "analyze-codebase": (
        ("phase1", "Explorando codebase"),
        ("phase2", "Gerando docs"),
    ),
}

WORKFLOW_LABELS: dict[str, str] = {
    "new-issue": "NEW ISSUE",
    "fix-bug": "QUICK",
    "setup-project": "SETUP PROJECT",
    "analyze-codebase": "ANALYZE CODEBASE",
}


@dataclass
class CockpitState:
    workflow_id: str = ""
    workflow_label: str = ""
    surface_title: str = "RUNTIME MODE & WORKSPACE CONFIG SURFACE"
    agent_label: str = "Agent"
    model_label: str = ""
    phases: list[PhaseItem] = field(default_factory=list)
    entries: list[LogEntry] = field(default_factory=list)
    artifacts: list[ArtifactItem] = field(default_factory=list)
    selected_phase_index: int = 0
    selected_artifact_path: str = ""
    follow_artifact: bool = True
    artifact_pane_open: bool = False
    focus_target: str = "phases"
    running: bool = False
    exit_code: int | None = None
    _listeners: list[Listener] = field(default_factory=list, repr=False)
    _next_entry_id: int = 1
    _active_assistant_id: int | None = None
    _follow_live: bool = True

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    def configure_workflow(self, workflow_id: str) -> None:
        self.workflow_id = workflow_id
        self.workflow_label = WORKFLOW_LABELS.get(workflow_id, workflow_id.upper())
        defs = WORKFLOW_PHASES.get(workflow_id, (("phase1", "Phase 1"),))
        self.phases = [PhaseItem(id=pid, label=label) for pid, label in defs]
        self.selected_phase_index = 0
        self.entries = []
        self.artifacts = []
        self.selected_artifact_path = ""
        self.follow_artifact = True
        self.artifact_pane_open = False
        self.focus_target = "phases"
        self._next_entry_id = 1
        self._active_assistant_id = None
        self._follow_live = True
        self.running = False
        self.exit_code = None
        self.notify()

    def done_count(self) -> int:
        return sum(1 for phase in self.phases if phase.status in {PhaseStatus.DONE, PhaseStatus.SKIPPED})

    def total_count(self) -> int:
        return len(self.phases)

    def begin_phase(self, title: str) -> None:
        self.finish_assistant()
        matched = self._match_phase(title)
        now = time.monotonic()
        matched_index = self.phases.index(matched) if matched is not None else None
        for index, phase in enumerate(self.phases):
            if matched is not None and phase is matched:
                continue
            if phase.status == PhaseStatus.RUNNING:
                phase.finish(now)
            elif (
                matched_index is not None
                and index < matched_index
                and phase.status == PhaseStatus.PENDING
            ):
                phase.status = PhaseStatus.DONE
                phase.ended_at = now
        if matched is not None:
            if matched.status != PhaseStatus.RUNNING or matched.started_at is None:
                matched.started_at = now
                matched.ended_at = None
            matched.status = PhaseStatus.RUNNING
            if self._follow_live or self.selected_phase_index == matched_index:
                self.selected_phase_index = matched_index if matched_index is not None else 0
                self._follow_live = True
                self.follow_artifact = True
        self.surface_title = title.upper()
        self.running = True
        self.notify()

    def apply_phase_statuses(
        self,
        *,
        done_ids: list[str] | tuple[str, ...] = (),
        skipped_ids: list[str] | tuple[str, ...] = (),
    ) -> None:
        done = set(done_ids)
        skipped = set(skipped_ids)
        now = time.monotonic()
        for phase in self.phases:
            if phase.id in skipped:
                if phase.status == PhaseStatus.RUNNING:
                    phase.ended_at = now if phase.started_at is not None else phase.ended_at
                phase.status = PhaseStatus.SKIPPED
            elif phase.id in done and phase.status != PhaseStatus.RUNNING:
                phase.status = PhaseStatus.DONE
        self.notify()

    def complete_active_phase(self) -> None:
        now = time.monotonic()
        for phase in self.phases:
            if phase.status == PhaseStatus.RUNNING:
                phase.finish(now)
        self.notify()

    def mark_finished(self, exit_code: int = 0) -> None:
        self.complete_active_phase()
        self.running = False
        self.exit_code = exit_code
        self.notify()

    def set_model(self, model: str) -> None:
        self.model_label = model
        self.notify()

    def set_agent(self, agent: str) -> None:
        self.agent_label = agent
        self.notify()

    def add_tool_entry(
        self,
        kind: LogKind,
        title: str,
        detail: str = "",
        *,
        tool_id: str = "",
        pending: bool = False,
    ) -> LogEntry:
        self._clear_active_flags()
        self._active_assistant_id = None
        entry = LogEntry(
            kind=kind,
            title=title,
            detail=detail,
            active=True,
            pending=pending,
            entry_id=self._next_entry_id,
            tool_id=tool_id,
            phase_id=self._entry_phase_id(),
        )
        self._next_entry_id += 1
        self.entries.append(entry)
        self.notify()
        return entry

    def record_files(self, paths: list[str] | tuple[str, ...]) -> bool:
        active = self._active_phase()
        if active is None:
            return False
        changed = False
        for path in paths:
            key = str(path or "").strip()
            if not key or key in {"…", "..."}:
                continue
            if key in active._seen_files:
                continue
            active._seen_files.add(key)
            changed = True
        if changed:
            active.files = len(active._seen_files)
            self.notify()
        return changed

    def record_issue(self, key: str) -> bool:
        active = self._active_phase()
        if active is None:
            return False
        token = str(key or "").strip()
        if not token or token in active._seen_issues:
            return False
        active._seen_issues.add(token)
        active.issues = len(active._seen_issues)
        self.notify()
        return True

    def update_tool_entry(
        self,
        tool_id: str,
        *,
        kind: LogKind | None = None,
        title: str | None = None,
        detail: str | None = None,
        pending: bool | None = None,
    ) -> LogEntry | None:
        if not tool_id:
            return None
        for entry in self.entries:
            if entry.tool_id != tool_id:
                continue
            if kind is not None:
                entry.kind = kind
            if title is not None and title.strip():
                entry.title = title.strip()
            if detail is not None:
                entry.detail = detail.strip()
            if pending is not None:
                entry.pending = pending
            self._clear_active_flags()
            entry.active = True
            self._active_assistant_id = None
            self.notify()
            return entry
        return None
    def add_info(self, title: str) -> None:
        self._clear_active_flags()
        self._active_assistant_id = None
        entry = LogEntry(
            kind=LogKind.INFO,
            title=title,
            detail=title,
            active=True,
            entry_id=self._next_entry_id,
            phase_id=self._entry_phase_id(),
        )
        self._next_entry_id += 1
        self.entries.append(entry)
        self.notify()

    def append_assistant(self, text: str) -> None:
        if not text:
            return
        if self._active_assistant_id is not None:
            for entry in self.entries:
                if entry.entry_id == self._active_assistant_id:
                    entry.body += text
                    entry.active = True
                    self.notify()
                    return
        self._clear_active_flags()
        entry = LogEntry(
            kind=LogKind.ASSISTANT,
            title="Assistant",
            body=text,
            active=True,
            entry_id=self._next_entry_id,
            phase_id=self._entry_phase_id(),
        )
        self._next_entry_id += 1
        self._active_assistant_id = entry.entry_id
        self.entries.append(entry)
        self.notify()

    def finish_assistant(self) -> None:
        self._active_assistant_id = None
        self._clear_active_flags()
        self.notify()

    def add_qa(self, prompt: str, answer: str) -> None:
        question = str(prompt or "").strip()
        reply = str(answer or "").strip() or "Cancelado"
        if not question:
            return
        self._active_assistant_id = None
        self._clear_active_flags()
        self.entries.append(
            LogEntry(
                kind=LogKind.QUESTION,
                title="Pergunta",
                body=question,
                active=False,
                entry_id=self._next_entry_id,
                phase_id=self._entry_phase_id(),
            )
        )
        self._next_entry_id += 1
        self.entries.append(
            LogEntry(
                kind=LogKind.ANSWER,
                title="Você",
                body=reply,
                active=True,
                entry_id=self._next_entry_id,
                phase_id=self._entry_phase_id(),
            )
        )
        self._next_entry_id += 1
        self.notify()

    def selected_phase(self) -> PhaseItem | None:
        if not self.phases:
            return None
        index = max(0, min(self.selected_phase_index, len(self.phases) - 1))
        return self.phases[index]

    def visible_entries(self) -> list[LogEntry]:
        phase = self.selected_phase()
        if phase is None:
            return list(self.entries)
        pid = phase.id
        return [entry for entry in self.entries if entry.phase_id == pid]

    def select_phase(self, index: int) -> None:
        if not self.phases:
            return
        self.selected_phase_index = max(0, min(index, len(self.phases) - 1))
        running = self._running_index()
        self._follow_live = running is None or self.selected_phase_index == running
        visible = self.visible_artifacts()
        if self._follow_live:
            self.follow_artifact = True
            if visible:
                self.selected_artifact_path = visible[-1].path
        elif visible:
            paths = {item.path for item in visible}
            if self.selected_artifact_path not in paths:
                self.selected_artifact_path = visible[-1].path
        self.notify()

    def move_phase(self, delta: int) -> None:
        self.select_phase(self.selected_phase_index + delta)

    def upsert_artifact(self, path: str, *, ready: bool) -> ArtifactItem | None:
        key = artifact_key(path)
        if not is_spec_artifact(key):
            return None
        phase_id = self._entry_phase_id()
        for item in self.artifacts:
            if item.path != key:
                continue
            item.ready = ready
            if not item.phase_id:
                item.phase_id = phase_id
            if self.follow_artifact:
                self.selected_artifact_path = item.path
            self.notify()
            return item
        was_empty = not self.artifacts
        item = ArtifactItem(path=key, phase_id=phase_id, ready=ready)
        self.artifacts.append(item)
        if self.follow_artifact or not self.selected_artifact_path:
            self.selected_artifact_path = item.path
        if was_empty:
            self.artifact_pane_open = True
        self.notify()
        return item

    def visible_artifacts(self) -> list[ArtifactItem]:
        phase = self.selected_phase()
        if phase is None:
            return list(self.artifacts)
        pid = phase.id
        return [item for item in self.artifacts if item.phase_id == pid]

    def phase_has_artifacts(self) -> bool:
        return bool(self.visible_artifacts())

    def selected_artifact(self) -> ArtifactItem | None:
        visible = self.visible_artifacts()
        if not visible:
            return None
        for item in visible:
            if item.path == self.selected_artifact_path:
                return item
        return visible[-1]

    def select_artifact(self, path: str) -> None:
        key = artifact_key(path)
        for item in self.artifacts:
            if item.path != key:
                continue
            self.selected_artifact_path = item.path
            self.follow_artifact = False
            self.notify()
            return

    def move_artifact(self, delta: int) -> None:
        visible = self.visible_artifacts()
        if not visible:
            return
        paths = [item.path for item in visible]
        selected = self.selected_artifact()
        current = selected.path if selected is not None else paths[0]
        try:
            index = paths.index(current)
        except ValueError:
            index = 0
        index = max(0, min(index + delta, len(paths) - 1))
        self.selected_artifact_path = paths[index]
        self.follow_artifact = False
        self.notify()

    def toggle_artifact_pane(self) -> None:
        self.artifact_pane_open = not self.artifact_pane_open
        if not self.artifact_pane_open and self.focus_target == "artifact":
            self.focus_target = "stream"
        self.notify()

    def close_artifact_pane(self) -> None:
        if not self.artifact_pane_open:
            return
        self.artifact_pane_open = False
        if self.focus_target == "artifact":
            self.focus_target = "stream"
        self.notify()

    def open_artifact_pane(self) -> None:
        if self.artifact_pane_open:
            return
        self.artifact_pane_open = True
        self.notify()

    def reveal_artifact_from_prompt(self, text: str) -> bool:
        keys = extract_spec_artifacts_from_text(text)
        matched: ArtifactItem | None = None
        for key in keys:
            for item in self.artifacts:
                if item.path == key or item.path.endswith(key) or key.endswith(item.path):
                    matched = item
                    break
            if matched is not None:
                break
        if matched is None and self.artifacts:
            visible = self.visible_artifacts()
            matched = visible[-1] if visible else self.artifacts[-1]
        if matched is None:
            return False
        self.selected_artifact_path = matched.path
        self.follow_artifact = False
        self.artifact_pane_open = True
        self.notify()
        return True

    def toggle_focus(self) -> None:
        if not self.artifact_pane_open:
            if self.focus_target == "artifact":
                self.focus_target = "stream"
            else:
                self.focus_target = "stream" if self.focus_target == "phases" else "phases"
            self.notify()
            return
        try:
            index = _FOCUS_CYCLE.index(self.focus_target)
        except ValueError:
            index = 0
        self.focus_target = _FOCUS_CYCLE[(index + 1) % len(_FOCUS_CYCLE)]
        self.notify()

    def snapshot(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "done": self.done_count(),
            "total": self.total_count(),
            "entries": len(self.entries),
            "running": self.running,
        }

    def _running_index(self) -> int | None:
        for index, phase in enumerate(self.phases):
            if phase.status == PhaseStatus.RUNNING:
                return index
        return None

    def _active_phase(self) -> PhaseItem | None:
        index = self._running_index()
        if index is None:
            return None
        return self.phases[index]

    def _entry_phase_id(self) -> str:
        active = self._active_phase()
        if active is not None:
            return active.id
        started = [phase for phase in self.phases if phase.started_at is not None]
        if started:
            return started[-1].id
        selected = self.selected_phase()
        if selected is not None:
            return selected.id
        return ""

    def _clear_active_flags(self) -> None:
        for entry in self.entries:
            entry.active = False

    def _match_phase(self, title: str) -> PhaseItem | None:
        lowered = title.lower()
        for phase in self.phases:
            if phase.id.lower() in lowered or phase.label.lower() in lowered:
                return phase
        pending = [phase for phase in self.phases if phase.status == PhaseStatus.PENDING]
        if pending:
            return pending[0]
        return None
