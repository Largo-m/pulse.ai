from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pulse.history.events import (
    ROUTED_FLOW_WORKFLOWS,
    WORKFLOW_LABELS,
    WORKFLOW_PHASES,
    ArtifactItem,
    LogEntry,
    LogKind,
    PhaseItem,
    PhaseStatus,
)
from pulse.tui.artifacts import (
    artifact_key,
    extract_spec_artifacts_from_text,
    is_spec_artifact,
)

Listener = Callable[[], None]
_FOCUS_CYCLE = ("phases", "stream", "artifact")
NAV_PHASE = "phase"
NAV_TASK = "task"


def progress_bar(done: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return ""
    filled = max(0, min(width, int(round(width * done / total))))
    return "#" * filled + "." * (width - filled)


@dataclass
class CockpitState:
    workflow_id: str = ""
    workflow_label: str = ""
    surface_title: str = "RUNTIME MODE & WORKSPACE CONFIG SURFACE"
    agent_label: str = "Agent"
    model_label: str = ""
    phases: list[PhaseItem] = field(default_factory=list)
    tasks: list[PhaseItem] = field(default_factory=list)
    entries: list[LogEntry] = field(default_factory=list)
    artifacts: list[ArtifactItem] = field(default_factory=list)
    selected_phase_index: int = 0
    selected_task_index: int = 0
    selected_nav_kind: str = NAV_PHASE
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
        self.tasks = []
        self.selected_phase_index = 0
        self.selected_task_index = 0
        self.selected_nav_kind = NAV_PHASE
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
            skip_select = matched.id == "execute" and bool(self.tasks)
            if matched_index is not None and self._follow_live and not skip_select:
                self.selected_nav_kind = NAV_PHASE
                self.selected_phase_index = matched_index
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

    def apply_routed_flow(self, flow: str) -> None:
        routed_id = ROUTED_FLOW_WORKFLOWS.get(str(flow).strip().lower())
        if routed_id is None:
            return
        now = time.monotonic()
        for phase in self.phases:
            if phase.id == "classify":
                if phase.status == PhaseStatus.RUNNING:
                    phase.finish(now)
                else:
                    phase.status = PhaseStatus.DONE
                    if phase.ended_at is None:
                        phase.ended_at = now
        existing_ids = {phase.id for phase in self.phases}
        for pid, label in WORKFLOW_PHASES.get(routed_id, ()):
            if pid not in existing_ids:
                self.phases.append(PhaseItem(id=pid, label=label))
        self.notify()

    def complete_active_phase(self) -> None:
        now = time.monotonic()
        for phase in self.phases:
            if phase.status == PhaseStatus.RUNNING:
                phase.finish(now)
        for task in self.tasks:
            if task.status == PhaseStatus.RUNNING:
                task.finish(now)
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
            task_id=self._entry_task_id(),
        )
        self._next_entry_id += 1
        self.entries.append(entry)
        self.notify()
        return entry

    def record_files(self, paths: list[str] | tuple[str, ...]) -> bool:
        targets = [item for item in (self._active_phase(), self._active_task()) if item is not None]
        if not targets:
            return False
        changed = False
        for path in paths:
            key = str(path or "").strip()
            if not key or key in {"…", "..."}:
                continue
            for active in targets:
                if key in active._seen_files:
                    continue
                active._seen_files.add(key)
                active.files = len(active._seen_files)
                changed = True
        if changed:
            self.notify()
        return changed

    def record_issue(self, key: str) -> bool:
        targets = [item for item in (self._active_phase(), self._active_task()) if item is not None]
        if not targets:
            return False
        token = str(key or "").strip()
        if not token:
            return False
        changed = False
        for active in targets:
            if token in active._seen_issues:
                continue
            active._seen_issues.add(token)
            active.issues = len(active._seen_issues)
            changed = True
        if changed:
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
            task_id=self._entry_task_id(),
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
            task_id=self._entry_task_id(),
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
                task_id=self._entry_task_id(),
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
                task_id=self._entry_task_id(),
            )
        )
        self._next_entry_id += 1
        self.notify()

    def selected_phase(self) -> PhaseItem | None:
        if not self.phases:
            return None
        index = max(0, min(self.selected_phase_index, len(self.phases) - 1))
        return self.phases[index]

    def selected_task(self) -> PhaseItem | None:
        if not self.tasks:
            return None
        index = max(0, min(self.selected_task_index, len(self.tasks) - 1))
        return self.tasks[index]

    def selected_nav_item(self) -> PhaseItem | None:
        if self.selected_nav_kind == NAV_TASK:
            return self.selected_task()
        return self.selected_phase()

    def task_done_count(self) -> int:
        return sum(1 for task in self.tasks if task.status in {PhaseStatus.DONE, PhaseStatus.SKIPPED})

    def task_total_count(self) -> int:
        return len(self.tasks)

    def set_tasks(self, items: list[tuple[str, str, str]]) -> None:
        existing = {task.id: task for task in self.tasks}
        merged: list[PhaseItem] = []
        now = time.monotonic()
        for task_id, title, status in items:
            key = str(task_id or "").strip()
            if not key:
                continue
            label = str(title or "").strip() or key
            prior = existing.get(key)
            if prior is None:
                item = PhaseItem(id=key, label=label)
            else:
                item = prior
                item.label = label
            mapped = _task_status_from_name(status)
            if item.status == PhaseStatus.RUNNING and mapped == PhaseStatus.DONE:
                item.finish(now)
            elif item.status != PhaseStatus.RUNNING:
                item.status = mapped
            merged.append(item)
        self.tasks = merged
        if self.selected_task_index >= len(self.tasks):
            self.selected_task_index = max(0, len(self.tasks) - 1)
        if not self.tasks and self.selected_nav_kind == NAV_TASK:
            self.selected_nav_kind = NAV_PHASE
        self.notify()

    def begin_task(self, task_id: str, title: str = "") -> None:
        key = str(task_id or "").strip()
        if not key:
            return
        self.finish_assistant()
        now = time.monotonic()
        found: PhaseItem | None = None
        for task in self.tasks:
            if task.id == key:
                found = task
                continue
            if task.status == PhaseStatus.RUNNING:
                task.finish(now)
        label = str(title or "").strip() or key
        if found is None:
            found = PhaseItem(id=key, label=label)
            self.tasks.append(found)
        elif title.strip():
            found.label = label
        if found.status != PhaseStatus.RUNNING or found.started_at is None:
            found.started_at = now
            found.ended_at = None
        found.status = PhaseStatus.RUNNING
        index = self.tasks.index(found)
        if self._follow_live:
            self.selected_nav_kind = NAV_TASK
            self.selected_task_index = index
            self.follow_artifact = True
        self.notify()

    def visible_entries(self) -> list[LogEntry]:
        if self.selected_nav_kind == NAV_TASK:
            task = self.selected_task()
            if task is None:
                return []
            return [entry for entry in self.entries if entry.task_id == task.id]
        phase = self.selected_phase()
        if phase is None:
            return list(self.entries)
        pid = phase.id
        return [entry for entry in self.entries if entry.phase_id == pid]

    def select_phase(self, index: int) -> None:
        if not self.phases:
            return
        self.selected_nav_kind = NAV_PHASE
        self.selected_phase_index = max(0, min(index, len(self.phases) - 1))
        self._sync_follow_and_artifact()

    def select_task(self, index: int) -> None:
        if not self.tasks:
            return
        self.selected_nav_kind = NAV_TASK
        self.selected_task_index = max(0, min(index, len(self.tasks) - 1))
        self._sync_follow_and_artifact()

    def move_phase(self, delta: int) -> None:
        self.move_nav(delta)

    def move_nav(self, delta: int) -> None:
        items = self.nav_items()
        if not items:
            return
        current = (self.selected_nav_kind, self._selected_nav_index())
        try:
            position = items.index(current)
        except ValueError:
            position = 0
        position = max(0, min(position + delta, len(items) - 1))
        kind, index = items[position]
        if kind == NAV_TASK:
            self.select_task(index)
            return
        self.select_phase(index)

    def nav_items(self) -> list[tuple[str, int]]:
        items: list[tuple[str, int]] = []
        has_execute = False
        for index, phase in enumerate(self.phases):
            items.append((NAV_PHASE, index))
            if phase.id == "execute":
                has_execute = True
                items.extend((NAV_TASK, task_index) for task_index in range(len(self.tasks)))
        if self.tasks and not has_execute:
            items.extend((NAV_TASK, task_index) for task_index in range(len(self.tasks)))
        return items

    def _sync_follow_and_artifact(self) -> None:
        live = self._live_target()
        self._follow_live = live is None or live == (
            self.selected_nav_kind,
            self._selected_nav_index(),
        )
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
        if self.selected_nav_kind == NAV_TASK:
            return [item for item in self.artifacts if item.phase_id == "execute"]
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

    def _running_task_index(self) -> int | None:
        for index, task in enumerate(self.tasks):
            if task.status == PhaseStatus.RUNNING:
                return index
        return None

    def _live_target(self) -> tuple[str, int] | None:
        task_index = self._running_task_index()
        if task_index is not None:
            return (NAV_TASK, task_index)
        phase_index = self._running_index()
        if phase_index is not None:
            return (NAV_PHASE, phase_index)
        return None

    def _selected_nav_index(self) -> int:
        if self.selected_nav_kind == NAV_TASK:
            return self.selected_task_index
        return self.selected_phase_index

    def _active_phase(self) -> PhaseItem | None:
        index = self._running_index()
        if index is None:
            return None
        return self.phases[index]

    def _active_task(self) -> PhaseItem | None:
        index = self._running_task_index()
        if index is None:
            return None
        return self.tasks[index]

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

    def _entry_task_id(self) -> str:
        active = self._active_task()
        if active is not None:
            return active.id
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


def _task_status_from_name(status: str) -> PhaseStatus:
    raw = str(status or "").strip().lower()
    if raw in {"done", "completed"}:
        return PhaseStatus.DONE
    if raw in {"skipped", "skip"}:
        return PhaseStatus.SKIPPED
    if raw in {"running", "in_progress", "in-progress"}:
        return PhaseStatus.RUNNING
    return PhaseStatus.PENDING
