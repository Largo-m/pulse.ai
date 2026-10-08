"""Stopping an in-flight run, and the contract for resuming it later.

An agent turn cannot be frozen mid-way, so there is only "stop": it cancels the
in-flight turn (`session/cancel`) and ends the run with `RUN_STOPPED`; the
interrupted step goes back to pending. Resuming is a new run over the same
record (`resume_run_id`) that restarts from the first unfinished step.

`RunControl` is shared between the run thread and the commander (daemon/API),
so all state goes through the lock.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

RUN_STOPPED = 130
RUN_BLOCKED = 131

# How long the daemon waits, on SIGTERM, for its runs to stop. It covers the
# agent's cancel grace plus closing its process; `stop_daemon` waits a bit longer.
SHUTDOWN_GRACE_SECONDS = 30.0

STOPPED = "stopped"


class RunControl:
    """Thread-safe stop state of a run."""

    def __init__(self, on_change: Callable[[str], None] | None = None) -> None:
        self._lock = threading.Lock()
        self._stopped = False
        self._on_change = on_change

    @property
    def interrupted(self) -> bool:
        """A stop was requested; the in-flight turn must be cancelled."""
        return self._stopped

    def stop(self) -> bool:
        """Request the stop; `False` when it was already requested.

        The state changes before `on_change` runs, so a failing listener cannot
        leave the run going.
        """
        with self._lock:
            if self._stopped:
                return False
            self._stopped = True
        if self._on_change is not None:
            self._on_change(STOPPED)
        return True

    def checkpoint(self) -> bool:
        """Cut point between steps. `False` when the run must not continue."""
        return not self._stopped
