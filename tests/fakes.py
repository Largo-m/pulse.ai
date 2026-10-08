"""In-memory adapters of the engine's ports, for tests that need no database, git or agent.

Each fake keeps the promise of its port, not just its method names: the
contract tests in `tests/infra/` run the same assertions against the fake and
the production adapter.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from pathlib import Path

from pulse.domain.ports import AgentProfile, WorkspaceError
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


class FakeWorkspace:
    """[pulse.domain.ports.Workspace] with branches and worktrees in memory, no git."""

    def __init__(self, root: Path, *, repo: bool = True, branch: str = "main") -> None:
        self._root = root
        self._repo = repo
        self._branch = branch if repo else ""
        self.branches: set[str] = {branch} if repo else set()
        self.worktrees: dict[Path, str] = {}

    @property
    def root(self) -> Path:
        return self._root

    def is_repo(self) -> bool:
        return self._repo

    def current_branch(self) -> str:
        return self._branch

    def has_branch(self, branch: str) -> bool:
        return branch in self.branches

    def worktree_exists(self, path: str) -> bool:
        return bool(path) and Path(path) in self.worktrees

    def attach_worktree(self, run_id: str, branch: str) -> Path:
        if not self.has_branch(branch):
            raise WorkspaceError(f"branch {branch} does not exist")
        target = self._target(run_id)
        self.worktrees[target] = branch
        return target

    def add_worktree(self, run_id: str, branch: str) -> tuple[Path, str]:
        if not self._repo:
            raise WorkspaceError(f"{self._root} is not a repository")
        name, attempt = branch, 2
        while name in self.branches:
            name, attempt = f"{branch}-{attempt}", attempt + 1
        self.branches.add(name)
        target = self._target(run_id)
        self.worktrees[target] = name
        return target, name

    def lose_worktree(self, path: Path) -> None:
        """The user deleted the folder; the branch stays."""
        del self.worktrees[path]

    def _target(self, run_id: str) -> Path:
        return self._root.parent / "worktrees" / run_id


class FixedAgentProfiles:
    """[pulse.domain.ports.AgentProfiles] answering the same model and policy for every agent."""

    def __init__(
        self,
        *,
        model: str | None = "auto",
        policy: str = "ask",
        instructions: dict[str, str] | None = None,
    ) -> None:
        self._model = model
        self._policy = policy
        self._instructions = instructions or {}

    def profile(self, agent_id: str) -> AgentProfile:
        return AgentProfile(
            agent_id=agent_id,
            model=self._model,
            permission_policy=self._policy,
            instructions=self._instructions.get(agent_id, ""),
        )
