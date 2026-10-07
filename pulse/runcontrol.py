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

STOPPED = "stopped"


class RunControl:
    """Thread-safe stop state of a run."""

    def __init__(self, on_change: Callable[[str], None] | None = None) -> None:
        self._lock = threading.Lock()
        self._stopped = False
        self._on_change = on_change

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def interrupted(self) -> bool:
        """A stop was requested; the in-flight turn must be cancelled."""
        return self._stopped

    def stop(self) -> bool:
        with self._lock:
            if self._stopped:
                return False
            self._stopped = True
        self._emit(STOPPED)
        return True

    def checkpoint(self) -> bool:
        """Cut point between steps. `False` when the run must not continue."""
        return not self._stopped

    def _emit(self, kind: str) -> None:
        if self._on_change is None:
            return
        try:
            self._on_change(kind)
        except Exception:
            pass
