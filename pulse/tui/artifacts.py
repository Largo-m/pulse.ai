"""Artifacts shown in the cockpit.

An artifact is a Markdown file the agent wrote, discovered from ACP tool-calls
rather than by folder convention; paths arrive from the runtime and are
normalized, confined to the run's worktree and read here.
"""

from __future__ import annotations

import posixpath
from pathlib import Path

from pulse.tui import strings

MAX_ARTIFACT_CHARS = 200_000
ARTIFACT_SUFFIX = ".md"


def artifact_key(path: str) -> str:
    """Canonical form of a path: forward slashes, no `file://` prefix."""
    text = str(path or "").strip().replace("\\", "/")
    if text.startswith("file://"):
        text = text[7:]
    return text


def is_displayable_artifact(path: str, cwd: str | None = None) -> bool:
    """A Markdown path inside `cwd`; the file may not exist yet, a write is announced first."""
    key = artifact_key(path)
    if not key.lower().endswith(ARTIFACT_SUFFIX):
        return False
    if not cwd:
        normalized = posixpath.normpath(key)
        return not posixpath.isabs(normalized) and normalized.split("/")[0] != ".."
    try:
        root = Path(cwd).resolve()
        target = (root / key).resolve()
    except (ValueError, OSError, RuntimeError):
        return False
    return target.is_relative_to(root)


def artifact_paths_in_text(text: str, known: list[str]) -> list[str]:
    """Known artifacts cited by the text.

    Only searches among artifacts the run already registered; guessing paths via
    regex would match code snippets and point the tab at non-artifact files.
    """
    haystack = str(text or "").replace("\\", "/")
    found: list[str] = []
    for candidate in known:
        key = artifact_key(candidate)
        if not key:
            continue
        name = key.rsplit("/", 1)[-1]
        if (key in haystack or name in haystack) and key not in found:
            found.append(key)
    return found


def resolve_artifact_path(path: str, cwd: str | None = None) -> Path | None:
    """The artifact's file inside the run's worktree, or `None`.

    The path comes from the agent, so it is untrusted (AGENTS.md §6.1): after
    resolving `..` and symlinks it must still be under `cwd`, or a reported
    `../../.ssh/id_rsa` would be read onto the screen. Without a `cwd` there is
    nothing to confine to, so nothing is read.
    """
    key = artifact_key(path)
    if not cwd or not key:
        return None
    try:
        root = Path(cwd).resolve()
        # `root / key` is `key` itself when the runtime reported an absolute path.
        target = (root / key).resolve()
    # A NUL byte (ValueError), an unreadable parent (OSError) or a symlink loop
    # (RuntimeError before 3.13) is not a file Pulse can show.
    except (ValueError, OSError, RuntimeError):
        return None
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return target


def artifact_has_content(path: str, cwd: str | None = None) -> bool:
    """File exists and is non-empty, so there is something to display."""
    target = resolve_artifact_path(path, cwd)
    if target is None:
        return False
    try:
        return target.stat().st_size > 0
    except OSError:
        return False


def read_artifact_markdown(path: str, cwd: str | None = None) -> tuple[str, float, bool]:
    target = resolve_artifact_path(path, cwd)
    if target is None:
        return "", 0.0, False
    try:
        mtime = target.stat().st_mtime
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", 0.0, False
    if len(text) > MAX_ARTIFACT_CHARS:
        text = text[:MAX_ARTIFACT_CHARS].rstrip() + strings.ARTIFACT_TRUNCATED
    return text, mtime, True
