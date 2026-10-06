from __future__ import annotations

import threading
import time

from tests.conftest import make_workflow

import pulse.daemon.runs as runs_module
from pulse.daemon.runs import RunAlreadyActive, RunManager


def test_two_concurrent_resumes_start_only_one_run(monkeypatch):
    """Endpoints síncronos rodam num threadpool: dois "retomar" chegam juntos."""
    make_workflow("demo", steps=[("one", "Um")])
    release = threading.Event()
    executed: list[str] = []

    def hold(self, state):
        executed.append(state.id)
        release.wait(5)
        state.finished_at = time.time()

    real_bus = runs_module.EventBus

    def slow_bus():
        # Alarga a janela entre olhar `_runs` e gravar nele.
        time.sleep(0.05)
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
