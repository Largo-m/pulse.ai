from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pulse.history.events import (
    ArtifactItem,
    LogEntry,
    LogKind,
    PhaseItem,
    PhaseStatus,
    workflow_label,
    workflow_steps,
)
from pulse.runcontrol import RUN_STOPPED
from pulse.tui.artifacts import artifact_key, artifact_paths_in_text

Listener = Callable[[], None]
_FOCUS_CYCLE = ("phases", "stream", "artifact")
NAV_PHASE = "phase"
#: `implement:T1` — o motor batiza cada filho de fan-out com o id do step que o
#: gerou. Ver [pulse.orchestrator.engine._units].
FANOUT_SEP = ":"


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
    entries: list[LogEntry] = field(default_factory=list)
    artifacts: list[ArtifactItem] = field(default_factory=list)
    selected_phase_index: int = 0
    selected_artifact_path: str = ""
    follow_artifact: bool = True
    artifact_pane_open: bool = False
    focus_target: str = "phases"
    running: bool = False
    #: Run viva, mas segurada pelo usuário. `running` continua True.
    paused: bool = False
    stopped: bool = False
    #: Ligados por `configure_workflow`: fora de uma run não há o que pausar.
    can_pause: bool = False
    can_stop: bool = False
    exit_code: int | None = None
    acp_session_id: str = ""
    acp_sessions: list[dict[str, str]] = field(default_factory=list)
    _listeners: list[Listener] = field(default_factory=list, repr=False)
    _next_entry_id: int = 1
    _active_assistant_id: int | None = None
    _follow_live: bool = True
    _base_labels: dict[str, str] = field(default_factory=dict, repr=False)
    _base_labels_for: str = field(default="", repr=False)

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
        self.workflow_label = workflow_label(workflow_id)
        self.phases = [
            PhaseItem(id=step_id, label=label) for step_id, label in workflow_steps(workflow_id)
        ]
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
        self.paused = False
        self.stopped = False
        # Todo workflow tem barreira entre steps: a sessão ACP é isolada por
        # step, então pausar sempre tem onde segurar e retomar tem onde voltar.
        self.can_pause = True
        self.can_stop = True
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
        if matched is not None:
            if matched.status != PhaseStatus.RUNNING or matched.started_at is None:
                matched.started_at = now
                matched.ended_at = None
            matched.status = PhaseStatus.RUNNING
            if matched_index is not None and self._follow_live:
                self.selected_phase_index = matched_index
                self.follow_artifact = True
        self.surface_title = title.upper()
        self.running = True
        self.notify()

    def sync_phases(self, steps: list[dict[str, str]] | tuple[dict[str, str], ...]) -> None:
        """Refaz a lista de fases a partir do que o motor está mesmo rodando.

        A lista muda no meio da run: um step de fan-out vira N, um por item. O
        que já existe é preservado por id — recriar apagaria status, duração e
        contadores de quem já rodou.
        """
        if not steps:
            return
        existing = {phase.id: phase for phase in self.phases}
        selected = self.selected_phase()
        self.phases = [
            existing.get(str(step["id"]))
            or PhaseItem(id=str(step["id"]), label=str(step.get("label", "")))
            for step in steps
        ]
        for phase, step in zip(self.phases, steps):
            phase.label = str(step.get("label", "")) or phase.label
        # A seleção segue a fase, não o índice: o fan-out empurra tudo que vem
        # depois dele para baixo.
        if selected is not None:
            for index, phase in enumerate(self.phases):
                if phase.id == selected.id:
                    self.selected_phase_index = index
                    break
            else:
                self.selected_phase_index = min(
                    self.selected_phase_index, max(0, len(self.phases) - 1)
                )

    def apply_phase_statuses(
        self,
        *,
        steps: list[dict[str, str]] | tuple[dict[str, str], ...] = (),
        done_ids: list[str] | tuple[str, ...] = (),
        skipped_ids: list[str] | tuple[str, ...] = (),
        failed_ids: list[str] | tuple[str, ...] = (),
    ) -> None:
        self.sync_phases(steps)
        done = set(done_ids)
        skipped = set(skipped_ids)
        failed = set(failed_ids)
        now = time.monotonic()
        for phase in self.phases:
            if phase.id in failed:
                if phase.status == PhaseStatus.RUNNING and phase.started_at is not None:
                    phase.ended_at = now
                phase.status = PhaseStatus.FAILED
            elif phase.id in skipped:
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

    def fail_active(self) -> None:
        now = time.monotonic()
        for phase in self.phases:
            if phase.status == PhaseStatus.RUNNING:
                if phase.started_at is not None:
                    phase.ended_at = now
                phase.status = PhaseStatus.FAILED
        self.notify()

    def mark_paused(self) -> None:
        """Pausa cortou o step em voo — ele volta para pendente e o relógio para.

        O step interrompido é refeito do começo ao retomar, então zerar o
        cronômetro é o que descreve a verdade: o tempo que ele já tinha gasto
        não conta para nada.
        """
        self.paused = True
        for item in self.phases:
            if item.status != PhaseStatus.RUNNING:
                continue
            item.status = PhaseStatus.PENDING
            item.started_at = None
            item.ended_at = None
        self.notify()

    def mark_resumed(self) -> None:
        self.paused = False
        self.notify()

    def mark_stopped(self) -> None:
        self.paused = False
        self.stopped = True
        for item in self.phases:
            if item.status != PhaseStatus.RUNNING:
                continue
            item.status = PhaseStatus.PENDING
            item.started_at = None
            item.ended_at = None
        self.notify()

    def mark_finished(self, exit_code: int = 0) -> None:
        if exit_code == 0:
            self.complete_active_phase()
        elif exit_code == RUN_STOPPED:
            # Parada do usuário não é falha: nada vira "falhou" na sidebar.
            self.mark_stopped()
        else:
            self.fail_active()
        self.running = False
        self.paused = False
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
        targets = [active] if active is not None else []
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
        active = self._active_phase()
        targets = [active] if active is not None else []
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
        )
        self._next_entry_id += 1
        self.entries.append(entry)
        self.notify()

    def add_error(self, title: str, reason: str = "") -> None:
        text = str(title or "Erro").strip() or "Erro"
        detail = str(reason or "").strip()
        self._clear_active_flags()
        self._active_assistant_id = None
        entry = LogEntry(
            kind=LogKind.ERROR,
            title=text,
            detail=detail or text,
            active=True,
            entry_id=self._next_entry_id,
            phase_id=self._entry_phase_id(),
        )
        self._next_entry_id += 1
        self.entries.append(entry)
        self.notify()

    def has_error(self) -> bool:
        return any(entry.kind == LogKind.ERROR for entry in self.entries)

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

    def selected_nav_item(self) -> PhaseItem | None:
        return self.selected_phase()

    def base_step_label(self, step_id: str) -> str:
        """Rótulo do step como a definição o nomeia (`implement` → Implementar).

        O fan-out apaga o step pai da run e põe os N filhos no lugar dele, então
        o nome do pai só existe na definição do workflow.
        """
        if self._base_labels_for != self.workflow_id:
            self._base_labels_for = self.workflow_id
            self._base_labels = dict(workflow_steps(self.workflow_id)) if self.workflow_id else {}
        return self._base_labels.get(step_id, "")

    def phase_groups(self) -> list[tuple[str, list[tuple[int, PhaseItem]]]]:
        """Fases na ordem, com os filhos de um fan-out reunidos sob o pai.

        Chave vazia é fase solta. O índice vem junto porque a navegação continua
        sendo sobre `phases` — agrupar é só desenho, não muda o que se seleciona.
        """
        groups: list[tuple[str, list[tuple[int, PhaseItem]]]] = []
        for index, phase in enumerate(self.phases):
            base, sep, _ = phase.id.partition(FANOUT_SEP)
            key = base if sep else ""
            if key and groups and groups[-1][0] == key:
                groups[-1][1].append((index, phase))
            else:
                groups.append((key, [(index, phase)]))
        return groups

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
        self._sync_follow_and_artifact()

    def move_phase(self, delta: int) -> None:
        self.move_nav(delta)

    def move_nav(self, delta: int) -> None:
        items = self.nav_items()
        if not items:
            return
        current = (NAV_PHASE, self._selected_nav_index())
        try:
            position = items.index(current)
        except ValueError:
            position = 0
        position = max(0, min(position + delta, len(items) - 1))
        _kind, index = items[position]
        self.select_phase(index)

    def nav_items(self) -> list[tuple[str, int]]:
        return [(NAV_PHASE, index) for index in range(len(self.phases))]

    def _sync_follow_and_artifact(self) -> None:
        live = self._live_target()
        self._follow_live = live is None or live == (NAV_PHASE, self._selected_nav_index())
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

    def upsert_artifact(
        self,
        path: str,
        *,
        ready: bool,
        has_content: bool = False,
    ) -> ArtifactItem | None:
        key = artifact_key(path)
        if not key:
            return None
        phase_id = self._entry_phase_id()
        for item in self.artifacts:
            if item.path != key:
                continue
            item.ready = ready
            item.has_content = item.has_content or has_content
            if not item.phase_id:
                item.phase_id = phase_id
            if self.follow_artifact:
                self.selected_artifact_path = item.path
            # A aba não abre sozinha: um artefato novo no meio da spec roubava a
            # tela do stream. O trilho "ABRIR" (tecla `a`) fica anunciando.
            self.notify()
            return item
        item = ArtifactItem(
            path=key,
            phase_id=phase_id,
            ready=ready,
            has_content=has_content,
        )
        self.artifacts.append(item)
        if self.follow_artifact or not self.selected_artifact_path:
            self.selected_artifact_path = item.path
        self.notify()
        return item

    def visible_artifacts(self) -> list[ArtifactItem]:
        phase = self.selected_phase()
        if phase is None:
            return list(self.artifacts)
        pid = phase.id
        return [item for item in self.artifacts if item.phase_id == pid]

    def displayable_artifacts(self) -> list[ArtifactItem]:
        """Artefatos da fase que têm mesmo algo para mostrar."""
        return [item for item in self.visible_artifacts() if item.has_content]

    def phase_has_artifacts(self) -> bool:
        # Gate da aba (trilho "ABRIR" e atalho `a`): sem artefato exibível não
        # faz sentido oferecer abrir um painel que só diria "escrevendo…".
        return bool(self.displayable_artifacts())

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

    def select_artifact_from_prompt(self, text: str) -> bool:
        """Deixa a aba apontando para o artefato que a pergunta cita.

        Só a seleção — abrir é do usuário, pela tecla `a`. A aba abrindo sozinha
        a cada pergunta cobria o stream bem na hora em que o agente pedia uma
        decisão, que é justamente o que precisa estar visível.

        Pergunta que não cita artefato nenhum não mexe em nada: um palpite aqui
        desligava o `follow_artifact` e a aba parava de acompanhar o artefato
        vivo por causa de uma pergunta sem relação com arquivo.
        """
        keys = artifact_paths_in_text(text, [item.path for item in self.artifacts])
        candidates = [item for item in self.artifacts if item.has_content]
        matched: ArtifactItem | None = None
        for key in keys:
            for item in candidates:
                if item.path == key or item.path.endswith(key) or key.endswith(item.path):
                    matched = item
                    break
            if matched is not None:
                break
        if matched is None:
            return False
        self.selected_artifact_path = matched.path
        self.follow_artifact = False
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

    def _live_target(self) -> tuple[str, int] | None:
        phase_index = self._running_index()
        if phase_index is not None:
            return (NAV_PHASE, phase_index)
        return None

    def _selected_nav_index(self) -> int:
        return self.selected_phase_index

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


