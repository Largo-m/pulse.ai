"""A branch name suggested from the task the user typed."""

from __future__ import annotations

import re
import unicodedata

SLUG_MAX = 60
_SEPARATOR = re.compile(r"[^a-z0-9]+")


def task_slug(text: str) -> str:
    """Kebab-case of `text`, accents dropped, empty when nothing safe remains."""
    folded = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    slug = _SEPARATOR.sub("-", ascii_text.lower()).strip("-")
    return slug[:SLUG_MAX].strip("-")


def worktree_folder(branch: str) -> str:
    """The folder a worktree on `branch` gets: one path segment, `/` turned into `-`."""
    return branch.replace("/", "-")
