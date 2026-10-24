"""How a run touches git: its own branch, a commit per delivery, a pull request."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum


class GitOption(StrEnum):
    WORKTREE = "use_worktree"
    COMMITS = "atomic_commits"
    PULL_REQUEST = "auto_pull_request"


# Each option needs every one before it: commits land on the run's own branch,
# and a pull request publishes those commits.
_CHAIN = (GitOption.WORKTREE, GitOption.COMMITS, GitOption.PULL_REQUEST)


class InvalidGitOptions(ValueError):
    """An option switched on without the one it builds on."""


@dataclass(frozen=True)
class GitOptions:
    use_worktree: bool = False
    atomic_commits: bool = False
    auto_pull_request: bool = False

    def __post_init__(self) -> None:
        flags = self._flags()
        for needed, option in zip(_CHAIN, _CHAIN[1:], strict=False):
            if flags[option] and not flags[needed]:
                raise InvalidGitOptions(f"{option} requires {needed}")

    @classmethod
    def chained(
        cls, *, use_worktree: bool, atomic_commits: bool, auto_pull_request: bool
    ) -> GitOptions:
        """Drop every option whose prerequisite is off, the safe reading of stored flags."""
        commits = use_worktree and atomic_commits
        return cls(use_worktree, commits, commits and auto_pull_request)

    def enabled(self, option: GitOption) -> bool:
        return self._flags()[option]

    def toggled(self, option: GitOption) -> GitOptions:
        """Flip `option`, carrying the chain along so the result is always valid.

        Switching on also switches on what it needs; switching off also
        switches off what needs it.
        """
        position = _CHAIN.index(option)
        turning_on = not self.enabled(option)
        flags = self._flags()
        for index, each in enumerate(_CHAIN):
            if turning_on and index <= position:
                flags[each] = True
            if not turning_on and index >= position:
                flags[each] = False
        return GitOptions(**{str(key): value for key, value in flags.items()})

    def _flags(self) -> dict[GitOption, bool]:
        return {GitOption(item.name): bool(getattr(self, item.name)) for item in fields(self)}


NO_GIT_OPTIONS = GitOptions()
