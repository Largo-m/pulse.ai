"""The run thread is the daemon's boundary for a run: whatever the engine raises ends there.

A failure must end the run as failed and tell every attached client why;
otherwise the run would stay "running" forever with nobody informed.
"""

from __future__ import annotations

import pytest

from pulse.daemon.events import EventBus
from pulse.daemon.runs import RunManager
from pulse.domain.run import RunStatus
from tests.conftest import make_workflow


def test_an_engine_crash_ends_the_run_as_failed_with_the_reason(monkeypatch, tmp_path):
    make_workflow("demo")

    def crashing_engine(**_kwargs: object) -> int:
        raise RuntimeError("runtime vanished")

    monkeypatch.setattr("pulse.daemon.runs.run_engine", crashing_engine)
    manager = RunManager()

    state = manager.start_run(workflow_id="demo", prompt="x", workspace=str(tmp_path))
    finished = next(event for event in state.bus.subscribe() if event.get("type") == "run.finished")

    assert finished == {
        "type": "run.finished",
        "run_id": state.id,
        "exit_code": 1,
        "error": "runtime vanished",
    }
    assert state.exit_code == 1
    assert state.status == RunStatus.FAILED
    assert not state.is_active()


@pytest.mark.parametrize("count", [1, 500])
def test_a_subscriber_that_does_not_read_misses_no_event(count: int):
    """Subscriber queues are unbounded: a slow screen falls behind but never loses an event."""
    bus = EventBus()
    reader = bus.subscribe()
    first = next(reader)

    for index in range(count):
        bus.publish({"type": "phase.info", "index": index})
    bus.close()

    assert first["type"] == "stream.replay_end"
    assert [event["index"] for event in reader] == list(range(count))
