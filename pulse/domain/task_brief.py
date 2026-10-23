"""The task a run starts from, as the user wrote it."""

from __future__ import annotations

from dataclasses import dataclass

PARAGRAPH = "\n\n"


@dataclass(frozen=True)
class TaskBrief:
    """A title that names the run, and the details under it.

    Both parts are kept apart so history and the pull request can show the
    title alone; agents read them joined, as the run's prompt.
    """

    title: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "description", self.description.strip())

    @property
    def is_empty(self) -> bool:
        return not self.title and not self.description

    @property
    def prompt(self) -> str:
        return PARAGRAPH.join(part for part in (self.title, self.description) if part)


EMPTY_BRIEF = TaskBrief()
