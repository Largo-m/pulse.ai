"""Where a run works: the project root, or a git worktree of its own.

The decision lives here; the git behind it is the [pulse.domain.ports.Workspace]
port, so the engine never runs git itself.
"""

from __future__ import annotations

from pathlib import Path

from pulse.domain.ports import RunRepository, Workspace
from pulse.domain.run import RunRecord


def prepare_workspace(
    run: RunRecord,
    workspace: Workspace,
    runs: RunRepository,
    *,
    use_worktree: bool,
) -> tuple[Path, str]:
    """Where this run works, and on which branch.

    Four cases, in order:
    1. Resumed run with an existing worktree: reuse it.
    2. Resumed run that lost its worktree but still has its branch: reattach a
       worktree on that branch, regardless of the setting.
    3. No isolation (setting off, or not a git repo): run at the root on the
       project's current branch.
    4. Isolation on: a new worktree for the run, on a new branch from HEAD.

    `workspace.root` stays the run's identity (history looks it up by it); only
    where the agent writes changes.
    """
    if workspace.worktree_exists(run.worktree_path):
        return Path(run.worktree_path), run.branch

    repo = workspace.is_repo()
    if repo and run.owns_branch and workspace.has_branch(run.branch):
        target = workspace.attach_worktree(run.id, run.branch)
        return _work_in(run, runs, target, run.branch)

    if not repo or not use_worktree:
        branch = workspace.current_branch()
        run.work_in(worktree_path="", branch=branch)
        runs.save(run)
        return workspace.root, branch

    target, branch = workspace.add_worktree(run.id, run.own_branch)
    return _work_in(run, runs, target, branch)


def _work_in(run: RunRecord, runs: RunRepository, target: Path, branch: str) -> tuple[Path, str]:
    run.work_in(worktree_path=str(target), branch=branch)
    runs.save(run)
    return target, branch
