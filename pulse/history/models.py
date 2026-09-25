from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pulse.status_labels import status_label


class HistoryKind(str, Enum):
    SPEC = "spec"
    ISSUE = "issue"
    FIX = "fix"


class SpecFlow(str, Enum):
    FULL = "full"
    QUICK = "quick"


class HistoryStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    BLOCKED = "blocked"
    DONE = "done"


@dataclass
class HistoryStep:
    id: str
    label: str
    status: str
    artifact: str = ""


@dataclass
class HistoryItem:
    kind: HistoryKind
    slug: str
    title: str
    prompt: str
    status: HistoryStatus
    updated_at: str
    spec_dir: str
    flow: SpecFlow = SpecFlow.FULL
    steps: list[HistoryStep] = field(default_factory=list)
    run_id: str | None = None

    @property
    def item_id(self) -> str:
        folder = "features" if self.flow == SpecFlow.FULL else "quick"
        return f"spec:{folder}/{self.slug}"

    @property
    def kind_label(self) -> str:
        return "SPEC"

    @property
    def flow_label(self) -> str:
        if self.flow == SpecFlow.QUICK:
            return "quick"
        return "full"

    @property
    def status_label(self) -> str:
        return status_label(self.status)


