"""[pulse.domain.ports.Workspace] over git: the project root and per-run worktrees."""

from __future__ import annotations

from pathlib import Path

from pulse import vcs


class GitWorkspace:
    """A project on disk; a run's worktree goes under `worktrees/<run id>`.

    The project root and the repository root may differ (a project in a
    subfolder of a repo): branches and worktrees belong to the repository.
    """

    def __init__(self, root: Path, *, worktrees: Path) -> None:
        self._root = root
        self._worktrees = worktrees

    @property
    def root(self) -> Path:
        return self._root

    def is_repo(self) -> bool:
        return vcs.is_repo(self._root)

    def current_branch(self) -> str:
        return vcs.current_branch(self._root)

    def has_branch(self, branch: str) -> bool:
        repo = vcs.repo_root(self._root)
        return repo is not None and vcs.branch_exists(repo, branch)

    def worktree_exists(self, path: str) -> bool:
        return bool(path) and Path(path).exists()

    def attach_worktree(self, run_id: str, branch: str) -> Path:
        target = self._worktrees / run_id
        vcs.attach_worktree(self._repo(), target, branch)
        return target

    def add_worktree(self, run_id: str, branch: str) -> tuple[Path, str]:
        target = self._worktrees / run_id
        return target, vcs.add_worktree(self._repo(), target, branch)

    def _repo(self) -> Path:
        repo = vcs.repo_root(self._root)
        if repo is None:
            raise vcs.GitError(f"{self._root} is not a git repository")
        return repo
