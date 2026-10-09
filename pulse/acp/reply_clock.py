"""How long the runner waits for the agent's reply to one JSON-RPC request."""

from __future__ import annotations

import time
from dataclasses import dataclass

CANCEL_GRACE_SECONDS = 10.0

# Requests whose deadline measures silence: a working agent keeps talking.
IDLE_CLOCK_METHODS = frozenset({"session/prompt"})


@dataclass
class ReplyClock:
    """When a request stops waiting for its reply.

    `session/prompt` measures agent silence (`idle`): the deadline follows the last
    sign of activity. Other requests keep a fixed deadline. A cancelled turn gets
    a short grace period instead, so the agent can close it on its own.
    """

    limit: float
    idle: bool
    deadline: float
    cancelling: bool = False

    def follow(self, activity: float) -> None:
        if self.idle and not self.cancelling:
            self.deadline = activity + self.limit

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def start_cancel(self) -> None:
        self.cancelling = True
        self.deadline = time.monotonic() + CANCEL_GRACE_SECONDS

    @classmethod
    def for_request(cls, method: str, limit: float, started: float) -> ReplyClock:
        return cls(limit=limit, idle=method in IDLE_CLOCK_METHODS, deadline=started + limit)
