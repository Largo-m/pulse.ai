from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pulse.status_labels import status_label


class HistoryStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class HistoryStep:
    id: str
    label: str
    status: str
    #: Sessão ACP daquele step — é por ela que o log é relido.
    acp_session_id: str = ""


@dataclass
class HistoryItem:
    """Uma run passada, do jeito que o histórico a mostra.

    Não há slug de feature nem pasta de spec: uma run é identificada pelo id que
    o Pulse gerou, e o que ela deixou no disco são os caminhos em `artifacts`.
    """

    run_id: str
    workflow_id: str
    workflow_label: str
    title: str
    prompt: str
    status: HistoryStatus
    updated_at: str
    steps: list[HistoryStep] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    @property
    def item_id(self) -> str:
        return self.run_id

    @property
    def status_label(self) -> str:
        return status_label(self.status)

    @property
    def is_incomplete(self) -> bool:
        return self.status in {HistoryStatus.PENDING, HistoryStatus.IN_PROGRESS}
