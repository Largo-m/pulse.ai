"""The little git that Pulse needs.

Pulse only opens an isolated place for a run to work (`git worktree`) and asks
which branch it is on; merge, push and review remain the user's job. Uses the
git CLI via `subprocess` rather than a library dependency.

Reads never raise: outside a repo, without git on PATH or on a detached HEAD
they return empty. Writes raise `GitError`: better not to start a run than to
start it in the wrong directory.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

TIMEOUT = 15.0

MAX_BRANCH_ATTEMPTS = 20


class GitError(RuntimeError):
    """A failed git command whose result cannot be ignored."""


def _run(args: list[str], *, cwd: Path | str) -> subprocess.CompletedProcess[str]:
    # argv list; git is resolved from PATH on purpose so the user's own git runs.
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
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


def _write(args: list[str], *, cwd: Path | str) -> str:
    try:
        result = _run(args, cwd=cwd)
    except (OSError, subprocess.SubprocessError) as error:
        raise GitError(f"git {' '.join(args)}: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GitError(f"git {' '.join(args)}: {detail or 'falhou'}")
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
    """Open a worktree at `path` on a new branch and return the branch name.

    If the name already exists (left by an earlier run), a suffix is added
    (`...-2`, `...-3`) instead of failing or reusing it, so two runs never share
    a history.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    prune_worktrees(repo)
    name = branch
    for attempt in range(2, MAX_BRANCH_ATTEMPTS + 2):
        if not branch_exists(repo, name):
            break
        name = f"{branch}-{attempt}"
    else:
        raise GitError(f"não consegui um nome de branch livre a partir de `{branch}`")
    _write(["worktree", "add", "-b", name, str(target), start], cwd=repo)
    return name


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
    """Remove the worktree. Without `force`, git refuses if there are unsaved changes."""
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(path))
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
    "current_branch",
    "git_available",
    "has_changes",
    "is_repo",
    "prune_worktrees",
    "remove_worktree",
    "repo_root",
]
