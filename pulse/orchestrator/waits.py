"""User waits recorded on the run aggregate.

The runner sees a question open and close on whichever thread asked it (the ACP
reader, the MCP bridge or the engine's own menus). This listener turns that into
intent on the run and saves it; the lock keeps two waits from interleaving.
"""

from __future__ import annotations

import threading

from pulse.store import runs as run_store


class RunWaits:
    """[pulse.ports.UserWaitListener] that pauses the run and charges the wait to the step."""

    def __init__(self, run: run_store.RunRecord) -> None:
        self._run = run
        self._lock = threading.Lock()

    def user_wait_began(self) -> None:
        with self._lock:
            if self._run.await_input():
                run_store.save(self._run)

    def user_wait_ended(self, step_id: str, seconds: float) -> None:
        """A wait before the step exists (the resume menu) only resumes the run."""
        with self._lock:
            step = self._run.step(step_id)
            if step is not None:
                step.add_wait(seconds)
            self._run.resume_work()
            run_store.save(self._run)
