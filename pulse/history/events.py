from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


class LogKind(str, Enum):
    SEARCH = "Search"
    LIST = "List"
    READ = "Read"
    EDIT = "Edit"
    WRITE = "Write"
    SHELL = "Shell"
    INFO = "Info"
    ERROR = "Error"
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
    task_id: str = ""


@dataclass
class ArtifactItem:
    path: str
    phase_id: str = ""
    ready: bool = False
    #: Arquivo existe em disco e tem conteúdo. Só artefato exibível abre a aba:
    #: um write pendente ou negado não deve escancarar um painel vazio.
    has_content: bool = False


WORKFLOW_PHASES: dict[str, tuple[tuple[str, str], ...]] = {
    "spec": (("classify", "Classificar"),),
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
    "spec": "SPEC",
    "new-issue": "NEW ISSUE",
    "fix-bug": "QUICK",
    "setup-project": "SETUP PROJECT",
    "analyze-codebase": "ANALYZE CODEBASE",
}

ROUTED_FLOW_WORKFLOWS = {
    "full": "new-issue",
    "quick": "fix-bug",
}
