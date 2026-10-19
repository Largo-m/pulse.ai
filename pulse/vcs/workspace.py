"""[pulse.domain.ports.Workspace] over git: the project root and per-run worktrees."""

from __future__ import annotations

from pathlib import Path

from pulse import vcs
from pulse.vcs import changes, publish


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

    def head(self, cwd: Path) -> str:
        return vcs.head_sha(cwd)

    def snapshot(self, cwd: Path) -> dict[str, str]:
        return changes.snapshot(cwd)

    def commit(self, cwd: Path, paths: list[str], message: str) -> None:
        changes.commit_paths(cwd, paths, message)

    def commits_after(self, cwd: Path, base: str) -> list[str]:
        return vcs.commits_after(cwd, base)

    def publish_branch(self, branch: str) -> None:
        vcs.push_branch(self._repo(), branch)

    def remove_worktree(self, path: Path) -> None:
        vcs.remove_worktree(self._repo(), path)

    def delete_local_branch(self, branch: str) -> None:
        vcs.delete_local_branch(self._repo(), branch)

    def open_pull_request(self, *, branch: str, title: str, body: str) -> None:
        repo = self._repo()
        base = changes.default_branch(repo)
        if not base:
            raise vcs.GitError("origin has no default branch (`git remote set-head origin -a`)")
        publish.open_request(repo, branch=branch, title=title, body=body, base=base)

    def _repo(self) -> Path:
        repo = vcs.repo_root(self._root)
        if repo is None:
            raise vcs.GitError(f"{self._root} is not a git repository")
        return repo
