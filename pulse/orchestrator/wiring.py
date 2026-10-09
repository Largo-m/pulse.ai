"""What every step of a run shares: the ports, the stop switch and where it works."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pulse.domain.control import RunControl
from pulse.domain.ports import (
    AgentProfiles,
    AgentSession,
    RunRepository,
    StreamSink,
    Workspace,
)
from pulse.domain.run import RunRecord, StepStatus


@dataclass(frozen=True)
class EnginePorts:
    """Everything the engine does to the world, wired by the daemon."""

    session: AgentSession
    stream: StreamSink
    runs: RunRepository
    workspace: Workspace
    agents: AgentProfiles


@dataclass(frozen=True)
class Wiring:
    """What every step of one run shares: the ports, the stop switch and where it works."""

    ports: EnginePorts
    control: RunControl
    exec_dir: Path

    @property
    def session(self) -> AgentSession:
        return self.ports.session

    @property
    def runs(self) -> RunRepository:
        return self.ports.runs


def notify(wiring: Wiring, message: str) -> None:
    wiring.ports.stream.info(message)


def sync_steps(wiring: Wiring, run: RunRecord) -> None:
    """Mirror `run_steps` to the panel, including the full step list.

    The list is sent because fan-out changes it mid-run.
    """
    grouped = run.step_ids_by_status()
    wiring.ports.stream.apply_phase_statuses(
        steps=[
            {"id": item.step_id, "label": item.label, "rounds": item.rounds} for item in run.steps
        ],
        done_ids=grouped[StepStatus.DONE],
        skipped_ids=grouped[StepStatus.SKIPPED],
        failed_ids=grouped[StepStatus.FAILED],
        blocked_ids=grouped[StepStatus.BLOCKED],
    )
