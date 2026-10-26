"""A branch name suggested from the task the user typed."""

from __future__ import annotations

import re
import unicodedata

from pulse.domain.run import SHORT_ID_CHARS

SLUG_MAX = 60
_SEPARATOR = re.compile(r"[^a-z0-9]+")


def task_slug(text: str) -> str:
    """Kebab-case of `text`, accents dropped, empty when nothing safe remains."""
    folded = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    slug = _SEPARATOR.sub("-", ascii_text.lower()).strip("-")
    return slug[:SLUG_MAX].strip("-")


def worktree_folders(branch: str, run_id: str) -> tuple[str, str]:
    """The folder a worktree on `branch` gets, then the one it falls back to when taken.

    One path segment, `/` turned into `-`; the fallback adds the run's short id,
    since `feat/x` and `feat-x` are different branches with the same folder.
    """
    folder = branch.replace("/", "-")
    return folder, f"{folder}-{run_id[:SHORT_ID_CHARS]}"
