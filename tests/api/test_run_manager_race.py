from __future__ import annotations

import threading
import time

import pulse.daemon.runs as runs_module
from pulse.daemon.runs import RunAlreadyActive, RunManager
from tests.conftest import make_workflow


def test_two_concurrent_resumes_start_only_one_run(monkeypatch):
    """Sync endpoints run in a threadpool: two resume requests arrive together."""
    make_workflow("demo", steps=[("one", "Um")])
    release = threading.Event()
    executed: list[str] = []

    def hold(self, state):
        executed.append(state.id)
        release.wait(5)
        state.finished_at = time.time()

    real_bus = runs_module.EventBus
    both_checked_in = threading.Barrier(2, timeout=5)

    def slow_bus():
        # Both requests are past the pre-lock setup before either takes the lock:
        # the race window is held open on purpose, not hoped for.
        both_checked_in.wait()
        return real_bus()

    monkeypatch.setattr(RunManager, "_execute", hold)
    monkeypatch.setattr(runs_module, "EventBus", slow_bus)
    manager = RunManager()
    outcomes: list[str] = []

    def resume():
        try:
            manager.start_run(workflow_id="demo", prompt="", resume_run_id="same")
            outcomes.append("started")
        except RunAlreadyActive:
            outcomes.append("refused")

    threads = [threading.Thread(target=resume) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    release.set()

    assert sorted(outcomes) == ["refused", "started"]
    assert executed == ["same"]
