"""What changed in a worktree, and committing just those paths."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pulse.vcs import GitError, _read, _run, _write


def snapshot(cwd: Path) -> dict[str, str]:
    """Digest of each dirty path. A path absent from a later snapshot was reverted."""
    digests: dict[str, str] = {}
    for path in _status_paths(cwd):
        digests[path] = _digest(cwd, path)
    return digests


def changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    names = set(before) | set(after)
    return sorted(path for path in names if before.get(path) != after.get(path))


def commit_paths(cwd: Path, paths: list[str], message: str) -> None:
    relative = [_inside(cwd, path) for path in paths]
    if not relative:
        raise GitError("nothing to commit")
    _write(["add", "--", *relative], cwd=cwd)
    _write(["commit", "-m", message], cwd=cwd)


def _status_paths(cwd: Path) -> list[str]:
    try:
        result = _run(["status", "--porcelain", "-z"], cwd=cwd)
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return _parse_porcelain(result.stdout)


def _parse_porcelain(text: str) -> list[str]:
    entries = text.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        path = entry[3:]
        extra = ""
        if "R" in entry[:2] or "C" in entry[:2]:
            if index < len(entries) and entries[index]:
                extra = entries[index]
                index += 1
        if path:
            paths.append(path)
        if extra:
            paths.append(extra)
    return paths


def _digest(cwd: Path, relative: str) -> str:
    try:
        target = _resolved(cwd, relative)
    except GitError:
        return ""
    if not target.is_file():
        return ""
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _inside(cwd: Path, relative: str) -> str:
    _resolved(cwd, relative)
    return relative


def _resolved(cwd: Path, relative: str) -> Path:
    root = cwd.resolve()
    if not relative or Path(relative).is_absolute() or "\x00" in relative:
        raise GitError(f"path escapes the worktree: {relative}")
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise GitError(f"path escapes the worktree: {relative}")
    return target


def branch_name_ok(repo: Path, name: str) -> bool:
    if not name or name != name.strip():
        return False
    try:
        result = _run(["check-ref-format", "--branch", name], cwd=repo)
    except OSError:
        return False
    return result.returncode == 0


def default_branch(repo: Path) -> str:
    ref = _read(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=repo)
    if ref.startswith("origin/"):
        return ref.split("/", 1)[1]
    return ref
