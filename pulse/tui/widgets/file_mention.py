from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from textual.widgets import OptionList
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from typing import Unpack

    from pulse.tui.widgets.options import WidgetOptions

MENTION_LIMIT = 8
MENTION_SIGN = "@"
# Only an `@` that starts a word: `dev@empresa.com` is an e-mail, not a mention.
_OPEN_MENTION = re.compile(rf"(?:^|\s){MENTION_SIGN}(\S*)$")
_MENTION_TAIL = re.compile(r"\S*")


def mention_at(before_cursor: str) -> str | None:
    """What follows the `@` the cursor is still typing, or None when no mention is open."""
    match = _OPEN_MENTION.search(before_cursor)
    return match.group(1) if match else None


def mention_text(path: str) -> str:
    """The `@` token typed for `path`, closed by a space.

    A path with whitespace or quotes is quoted and escaped: unquoted, the agent
    would read the first space as the end of the mention, and a raw `"` or line
    break would end or split the quoted token.
    """
    needs_quotes = any(char.isspace() or char == '"' for char in path)
    token = json.dumps(path, ensure_ascii=False) if needs_quotes else path
    return f"{MENTION_SIGN}{token} "


def mention_end(after_cursor: str) -> int:
    tail = _MENTION_TAIL.match(after_cursor)
    return tail.end() if tail else 0


def match_files(files: list[str], query: str, *, limit: int = MENTION_LIMIT) -> list[str]:
    """Files whose path holds `query`, those whose own name holds it first."""
    needle = query.casefold()
    ranked = sorted(
        (rank, index, path)
        for index, path in enumerate(files)
        if (rank := _rank(path, needle)) is not None
    )
    return [path for _rank_, _index, path in ranked[:limit]]


def _rank(path: str, needle: str) -> int | None:
    name = path.rsplit("/", 1)[-1].casefold()
    if name.startswith(needle):
        return 0
    if needle in name:
        return 1
    if needle in path.casefold():
        return 2
    return None


class FileMentionList(OptionList):
    """The workspace files matching the mention being typed.

    It never takes the focus: the composer keeps it and drives the list, so
    typing goes on filtering while the list is open. A click bubbles up as
    `OptionList.OptionSelected` for the form that holds both widgets.
    """

    can_focus = False

    def __init__(self, **kwargs: Unpack[WidgetOptions]) -> None:
        kwargs["markup"] = False
        super().__init__(**kwargs)
        self._files: list[str] = []
        self.display = False

    def set_files(self, files: list[str]) -> None:
        self._files = files

    def show_for(self, query: str) -> None:
        """List the matches; with none there is nothing to pick, so the list hides."""
        matches = match_files(self._files, query)
        self.set_options(Option(path, id=path) for path in matches)
        self.highlighted = 0 if matches else None
        self.display = bool(matches)

    def close(self) -> None:
        self.display = False

    @property
    def chosen(self) -> str | None:
        if not self.display or self.highlighted is None:
            return None
        return self.get_option_at_index(self.highlighted).id
