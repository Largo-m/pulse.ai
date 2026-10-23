"""The client↔daemon wire contract shared by both sides.

Kept outside `daemon/` so the thin client can read it without importing the
engine (AGENTS.md §2.1). Bump `ENGINE_PROTOCOL` on any change a stale daemon
would serve wrongly: the client restarts a daemon older than this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ENGINE_PROTOCOL = 11

REPLAY_END = "stream.replay_end"
PING = "stream.ping"


@dataclass(frozen=True)
class RunForm:
    """What the run form adds to a start: the task in two parts and git options for that run.

    The daemon joins title and description into the run's prompt and checks
    that the options are chained; a form is sent instead of a prompt.
    """

    title: str
    description: str
    use_worktree: bool
    atomic_commits: bool
    auto_pull_request: bool

    def body(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "git": {
                "use_worktree": self.use_worktree,
                "atomic_commits": self.atomic_commits,
                "auto_pull_request": self.auto_pull_request,
            },
        }
