from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pulse.domain.run import SETTLED, StepStatus
from pulse.tui.status_labels import status_label


class HistoryStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_INPUT = "awaiting_input"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"
    BLOCKED = "blocked"


LIVE_STATUSES = frozenset({HistoryStatus.IN_PROGRESS, HistoryStatus.AWAITING_INPUT})


@dataclass
class HistoryStep:
    id: str
    label: str
    status: StepStatus
    acp_session_id: str = ""

    @property
    def settled(self) -> bool:
        return self.status in SETTLED


@dataclass
class HistoryItem:
    """A past run as the history screen shows it.

    A run is identified by its Pulse-generated id; files it left on disk are in
    `artifacts`.
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
    branch: str = ""
    worktree_path: str = ""

    @property
    def item_id(self) -> str:
        return self.run_id

    @property
    def status_label(self) -> str:
        return status_label(self.status)

    @property
    def is_incomplete(self) -> bool:
        """Whether steps remain to be done, which decides if the run can resume.

        Steps decide, not the run status: `failed` and `stopped` runs can also
        have work left to resume.
        """
        if self.status is HistoryStatus.DONE:
            return False
        if not self.steps:
            return self.status is HistoryStatus.PENDING or self.status in LIVE_STATUSES
        return any(not step.settled for step in self.steps)
