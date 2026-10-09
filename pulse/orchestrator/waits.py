"""User waits recorded on the run aggregate.

The runner sees a question open and close on whichever thread asked it (the ACP
reader, the MCP bridge or the engine's own menus). This listener turns that into
intent on the run and saves it; the lock keeps two waits from interleaving.
"""

from __future__ import annotations

import threading

from pulse.domain.ports import RunRepository
from pulse.domain.run import RunRecord


class RunWaits:
    """[pulse.domain.ports.UserWaitListener] pausing the run and charging the wait to the step."""

    def __init__(self, run: RunRecord, runs: RunRepository) -> None:
        self._run = run
        self._runs = runs
        self._lock = threading.Lock()

    def user_wait_began(self) -> None:
        with self._lock:
            if self._run.await_input():
                self._runs.save(self._run)

    def user_wait_ended(self, step_id: str, seconds: float) -> None:
        """A wait before the step exists (the resume menu) only resumes the run."""
        with self._lock:
            self._run.end_wait(step_id, seconds)
            self._runs.save(self._run)
