"""In-memory adapters of the engine's ports, for tests that need no database, git or agent.

Each fake keeps the promise of its port, not just its method names: the
contract tests in `tests/infra/` run the same assertions against the fake and
the production adapter.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from pathlib import Path

from pulse.domain.run import RunRecord, RunStatus, StepRecord, StepStatus, utc_now


class InMemoryRunRepository:
    """[pulse.domain.ports.RunRepository] in a dict.

    Stores copies, like a database would: a run changed after `save` is not
    changed in storage until the next `save`.
    """

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._artifacts: dict[str, list[str]] = {}
        self.saves = 0

    def create(
        self,
        *,
        run_id: str,
        workflow_id: str,
        workspace: Path,
        user_prompt: str,
        steps: Sequence[StepRecord],
    ) -> RunRecord:
        now = utc_now().isoformat()
        run = RunRecord(
            id=run_id,
            workflow_id=workflow_id,
            workspace_root=str(Path(workspace).resolve()),
            user_prompt=user_prompt,
            status=RunStatus.RUNNING,
            current_step=steps[0].step_id if steps else "",
            created_at=now,
            updated_at=now,
            steps=[
                StepRecord(
                    step_id=step.step_id,
                    position=step.position or index,
                    label=step.label,
                    agent_id=step.agent_id,
                    status=StepStatus.PENDING,
                )
                for index, step in enumerate(steps, start=1)
            ],
        )
        self._runs[run_id] = copy.deepcopy(run)
        return run

    def load(self, run_id: str) -> RunRecord | None:
        stored = self._runs.get(run_id)
        return copy.deepcopy(stored) if stored is not None else None

    def save(self, run: RunRecord) -> None:
        run.forget_removed_steps()
        self._runs[run.id] = copy.deepcopy(run)
        self.saves += 1

    def artifacts(self, run_id: str) -> list[str]:
        return list(self._artifacts.get(run_id, []))

    def add_artifact(self, run_id: str, path: str) -> None:
        """What the session runner does when an agent writes a file."""
        self._artifacts.setdefault(run_id, []).append(path)

    def only(self) -> RunRecord:
        """The single stored run, as the database would return it."""
        (run,) = self._runs.values()
        return copy.deepcopy(run)
