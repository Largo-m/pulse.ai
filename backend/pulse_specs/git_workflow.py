from __future__ import annotations

import subprocess
from pathlib import Path


class GitWorkflowError(RuntimeError):
    pass


def _run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise GitWorkflowError(f"git {' '.join(args)} falhou: {stderr}")
    return result


def resolve_repo_root(start: Path | None = None) -> Path:
    args: list[str] = ["rev-parse", "--show-toplevel"]
    if start is not None:
        result = subprocess.run(
            ["git", *args],
            cwd=start,
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        raise GitWorkflowError("não foi possível resolver a raiz do repositório git")
    return Path(result.stdout.strip())


def current_branch(repo_root: Path) -> str:
    result = _run_git(repo_root, "branch", "--show-current")
    branch = result.stdout.strip()
    if not branch:
        raise GitWorkflowError("branch atual não identificada (detached HEAD?)")
    return branch


def branch_exists(repo_root: Path, branch: str) -> bool:
    result = _run_git(repo_root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
    return result.returncode == 0


def checkout_branch(repo_root: Path, branch: str, *, create: bool = False) -> None:
    if create:
        _run_git(repo_root, "checkout", "-b", branch)
        return
    _run_git(repo_root, "checkout", branch)


def prepare_phase_branch(repo_root: Path, parent_branch: str, phase_branch: str) -> None:
    _run_git(repo_root, "checkout", parent_branch)
    if branch_exists(repo_root, phase_branch):
        _run_git(repo_root, "checkout", phase_branch)
        return
    checkout_branch(repo_root, phase_branch, create=True)


def has_staged_or_unstaged_changes(repo_root: Path) -> bool:
    result = _run_git(repo_root, "status", "--porcelain")
    return bool(result.stdout.strip())


def ensure_committed(repo_root: Path, message: str) -> bool:
    if not has_staged_or_unstaged_changes(repo_root):
        return False
    _run_git(repo_root, "add", "-A")
    _run_git(repo_root, "commit", "-m", message)
    return True


def push_branch(repo_root: Path, branch: str) -> None:
    _run_git(repo_root, "push", "-u", "origin", branch)
