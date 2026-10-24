"""The little git that Pulse needs.

Pulse opens an isolated worktree, commits what a step changed, pushes that
branch and can open a pull request. Merge stays the user's job. Uses the git
CLI via `subprocess` rather than a library dependency.

Reads never raise: outside a repo, without git on PATH or on a detached HEAD
they return empty. Writes raise `GitError`: better not to start a run than to
start it in the wrong directory.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pulse.domain.ports import WorkspaceError

TIMEOUT = 15.0
PUSH_TIMEOUT = 60.0


class GitError(WorkspaceError):
    """A failed git command whose result cannot be ignored."""


def _run(
    args: list[str], *, cwd: Path | str, timeout: float = TIMEOUT, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    # argv list; git is resolved from PATH on purpose so the user's own git runs.
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def _read(args: list[str], *, cwd: Path | str) -> str:
    """Output of a read command; any failure yields an empty string."""
    try:
        result = _run(args, cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _write(
    args: list[str], *, cwd: Path | str, timeout: float = TIMEOUT, env: dict[str, str] | None = None
) -> str:
    try:
        result = _run(args, cwd=cwd, timeout=timeout, env=env)
    except (OSError, subprocess.SubprocessError) as error:
        raise GitError(f"git {' '.join(args)}: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GitError(f"git {' '.join(args)}: {detail or 'failed'}")
    return result.stdout.strip()


def repo_root(path: Path | str) -> Path | None:
    """Root of the repository containing `path`, or `None` if there is none."""
    candidate = Path(path)
    if not candidate.exists():
        return None
    top = _read(["rev-parse", "--show-toplevel"], cwd=candidate)
    if not top:
        return None
    return Path(top).resolve()


def is_repo(path: Path | str) -> bool:
    return repo_root(path) is not None


def current_branch(path: Path | str) -> str:
    """Current branch, or empty on a detached HEAD or outside a repository.

    Empty rather than the sha, since the UI shows this next to the model and a
    sha would look like a branch name.
    """
    candidate = Path(path)
    if not candidate.exists():
        return ""
    name = _read(["rev-parse", "--abbrev-ref", "HEAD"], cwd=candidate)
    return "" if name == "HEAD" else name


def list_files(root: Path | str, *, untracked: bool = False) -> list[str]:
    """Tracked files under `root`, relative to it; with `untracked`, new ones git does not ignore.

    NUL-separated output, since git quotes names with spaces or accents otherwise.
    """
    candidate = Path(root)
    if not candidate.exists():
        return []
    selection = ["--others", "--exclude-standard"] if untracked else ["--cached"]
    args = ["ls-files", "-z", *selection]
    try:
        result = _run(args, cwd=candidate)
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return sorted({name for name in result.stdout.split("\0") if name})


def branch_exists(repo: Path | str, branch: str) -> bool:
    if not branch:
        return False
    try:
        result = _run(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def add_worktree(
    repo: Path | str,
    path: Path | str,
    branch: str,
    *,
    start: str = "HEAD",
) -> str:
    """Open a worktree at `path` on `branch` and return that name.

    A name that already exists is refused: the caller confirmed it, so a suffix
    would publish a branch the user did not choose.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    prune_worktrees(repo)
    if branch_exists(repo, branch):
        raise GitError(f"branch `{branch}` already exists")
    _write(["worktree", "add", "-b", branch, str(target), start], cwd=repo)
    return branch


def attach_worktree(repo: Path | str, path: Path | str, branch: str) -> None:
    """Reopen a worktree at `path` on an existing branch.

    Used when a resumed run lost its directory: finished steps' work is
    committed on its branch, and a new branch from HEAD would leave it out.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    prune_worktrees(repo)
    _write(["worktree", "add", str(target), branch], cwd=repo)


def prune_worktrees(repo: Path | str) -> None:
    """Forget worktrees whose directory is gone from disk.

    Otherwise `worktree add` refuses the same path. Failures are ignored; the
    following `add` reports the real error.
    """
    _read(["worktree", "prune"], cwd=repo)


def remove_worktree(repo: Path | str, path: Path | str, *, force: bool = False) -> None:
    """Remove the worktree containing `path`, which may be a folder inside it.

    Without `force`, git refuses if there are unsaved changes.
    """
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(repo_root(path) or path))
    _write(args, cwd=repo)


def has_changes(path: Path | str) -> bool:
    """Whether there is uncommitted work here; `True` when in doubt.

    Callers are about to delete the directory, so a read error must not look
    like "nothing here".
    """
    candidate = Path(path)
    if not candidate.exists():
        return False
    try:
        result = _run(["status", "--porcelain"], cwd=candidate)
    except (OSError, subprocess.SubprocessError):
        return True
    if result.returncode != 0:
        return True
    return bool(result.stdout.strip())


def head_sha(path: Path | str) -> str:
    return _read(["rev-parse", "HEAD"], cwd=path)


def commits_after(path: Path | str, base: str) -> list[str]:
    if not base:
        return []
    log = _read(["log", "--format=%s", f"{base}..HEAD"], cwd=path)
    return [line for line in log.splitlines() if line.strip()]


def push_branch(repo: Path | str, branch: str) -> None:
    env = _quiet_git_env()
    _write(
        ["push", "-u", "origin", branch],
        cwd=repo,
        timeout=PUSH_TIMEOUT,
        env=env,
    )


def delete_local_branch(repo: Path | str, branch: str) -> None:
    _write(["branch", "-d", branch], cwd=repo)


def _quiet_git_env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_available() -> bool:
    try:
        # Fixed argv; git is resolved from PATH on purpose.
        result = subprocess.run(  # noqa: S603
            ["git", "--version"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


__all__ = [
    "GitError",
    "add_worktree",
    "attach_worktree",
    "branch_exists",
    "commits_after",
    "current_branch",
    "delete_local_branch",
    "git_available",
    "has_changes",
    "head_sha",
    "push_branch",
    "is_repo",
    "prune_worktrees",
    "remove_worktree",
    "repo_root",
]
