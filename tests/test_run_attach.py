"""Leaving the cockpit drops the screen, not the run.

The run lives in the daemon; the cockpit is a window onto it. Detaching does not
cancel, answers no question and leaves no stuck thread, and coming back finds the
clock where it was.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pulse.client.run_session import DETACHED, EngineRunSession
from pulse.history.events import PhaseStatus
from pulse.store import runs as run_store
from pulse.store.runs import StepRecord
from pulse.tui.adapters.prompt_bridge import PromptAbandoned, PromptBridge, PromptKind
from pulse.tui.hydrate import stamp_live_elapsed
from pulse.tui.state import CockpitState
from tests.conftest import store_run_status, store_step


class _BlockingClient:
    """A stream that never ends, like that of a run still working."""

    def __init__(self) -> None:
        self.cancelled: list[str] = []
        self.closed = False

    def stream_events(self, run_id: str, *, after: int = 0):
        from pulse.daemon.protocol import PING

        yield {"type": "phase.begin", "title": "Um"}
        while not self.closed:
            yield {"type": PING}
            time.sleep(0.01)

    def cancel_run(self, run_id: str):
        self.cancelled.append(run_id)
        return {"ok": True}

    def close(self) -> None:
        self.closed = True

    def answer_prompt(self, prompt_id: str, answer):
        return {"ok": True}


def test_detaching_leaves_the_run_alone():
    client = _BlockingClient()
    session = EngineRunSession(
        stream=MagicMock(),
        prompt_handler=MagicMock(),
        client=client,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(session.attach, "run-1")
        time.sleep(0.1)
        session.detach()
        assert future.result(timeout=5) == DETACHED
    assert client.cancelled == []


def test_abandoning_the_bridge_frees_the_thread_without_answering():
    """The question stays open in the daemon; only the screen thread dies."""
    bridge = PromptBridge()
    with ThreadPoolExecutor(max_workers=1) as pool:
        asking = pool.submit(bridge.request, PromptKind.TEXT, title="t", prompt="responde?")
        deadline = time.monotonic() + 2
        while bridge.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        bridge.abandon()
        with pytest.raises(PromptAbandoned):
            asking.result(timeout=5)


def test_closing_the_bridge_still_cancels_what_is_open():
    """A finished run is a different case: there, answering "cancelled" is the truth."""
    bridge = PromptBridge()
    with ThreadPoolExecutor(max_workers=1) as pool:
        asking = pool.submit(bridge.request, PromptKind.TEXT, title="t", prompt="?")
        deadline = time.monotonic() + 2
        while bridge.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        bridge.close()
        assert asking.result(timeout=5) is None


def _seed_run(tmp_path: Path, *, run_id: str = "run-live") -> None:
    run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[
            StepRecord(step_id="one", position=1, label="Um", agent_id="tester"),
            StepRecord(step_id="two", position=2, label="Dois", agent_id="tester"),
        ],
    )


def test_the_clock_survives_leaving_and_coming_back(tmp_path: Path):
    """Replay restamps `phase.begin` as now; the real time comes from the database."""
    _seed_run(tmp_path)
    now = datetime.now(UTC).replace(microsecond=0)
    store_step(
        "run-live",
        StepRecord(
            step_id="one",
            position=1,
            label="Um",
            agent_id="tester",
            status="done",
            started_at=now - timedelta(seconds=90),
            ended_at=now - timedelta(seconds=60),
        ),
    )
    store_step(
        "run-live",
        StepRecord(
            step_id="two",
            position=2,
            label="Dois",
            agent_id="tester",
            status="running",
            started_at=now - timedelta(seconds=45),
        ),
    )

    state = CockpitState()
    state.sync_phases([{"id": "one", "label": "Um"}, {"id": "two", "label": "Dois"}])
    state.phases[0].status = PhaseStatus.DONE
    state.begin_phase("Dois")

    stamp_live_elapsed(state, "run-live")

    assert state.phases[0].elapsed_label() == "00:30"
    spent = time.monotonic() - state.phases[1].started_at
    assert 44 <= spent <= 50
    assert state.phases[1].ended_at is None


def test_attaching_to_a_waiting_run_reopens_with_the_clock_frozen(tmp_path: Path):
    """Coming back to a waiting run finds the clock stopped.

    `run.awaiting` arrives through replay with the rest of the past, so the
    rebuilt screen already knows the run is not working, and the minutes the
    question stayed open do not count toward the step duration.
    """
    from unittest.mock import MagicMock

    from pulse.tui.adapters.cockpit_sink import CockpitSink

    _seed_run(tmp_path, run_id="run-wait")
    now = datetime.now(UTC).replace(microsecond=0)
    store_step(
        "run-wait",
        StepRecord(
            step_id="one",
            position=1,
            label="Um",
            agent_id="tester",
            status="running",
            started_at=now - timedelta(seconds=300),
            waiting_seconds=240.0,
        ),
    )

    state = CockpitState()
    state.sync_phases([{"id": "one", "label": "Um"}, {"id": "two", "label": "Dois"}])
    sink = CockpitSink(state, on_change=MagicMock(), cwd=str(tmp_path))
    session = EngineRunSession(stream=sink, prompt_handler=MagicMock(), client=MagicMock())

    session._dispatch({"type": "phase.begin", "title": "Um"})
    session._dispatch({"type": "run.awaiting", "waiting": True})

    assert state.awaiting_input is True
    assert state.phases[0].display_status() == "awaiting_input"

    stamp_live_elapsed(state, "run-wait")

    assert state.phases[0].elapsed_label() == "01:00"
    assert state.phases[0].elapsed_label(now=time.monotonic() + 120) == "01:00"

    session._dispatch({"type": "run.awaiting", "waiting": False})
    assert state.awaiting_input is False
    assert state.phases[0].display_status() == PhaseStatus.RUNNING.value


def test_history_puts_what_is_running_above_the_past(tmp_path: Path):
    """In-progress runs are the only list items you can still enter."""
    from pulse.history.catalog import HistoryCatalog
    from pulse.history.models import HistoryStatus

    for run_id, status in [
        ("velha", "completed"),
        ("rodando", "running"),
        ("falhou", "failed"),
        ("rodando-2", "running"),
    ]:
        run_store.create_run(
            run_id=run_id,
            workflow_id="demo",
            workspace=tmp_path,
            user_prompt=run_id,
            steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
        )
        store_run_status(run_id, status)

    items = HistoryCatalog(tmp_path).list_items()
    assert {item.run_id for item in items[:2]} == {"rodando", "rodando-2"}, (
        "running runs must come first"
    )
    assert all(item.status is HistoryStatus.IN_PROGRESS for item in items[:2])
    assert all(item.status is not HistoryStatus.IN_PROGRESS for item in items[2:])

    from_db = [record.id for record in run_store.list_runs(tmp_path)]
    for group in (items[:2], items[2:]):
        ids = [item.run_id for item in group]
        assert ids == [run_id for run_id in from_db if run_id in set(ids)]


def test_searching_keeps_the_running_run_on_top(tmp_path: Path):
    from pulse.history.catalog import HistoryCatalog

    for run_id, status in [("alfa-velha", "completed"), ("alfa-viva", "running")]:
        run_store.create_run(
            run_id=run_id,
            workflow_id="demo",
            workspace=tmp_path,
            user_prompt="alfa",
            steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
        )
        store_run_status(run_id, status)

    found = HistoryCatalog(tmp_path).search("alfa")
    assert [item.run_id for item in found] == ["alfa-viva", "alfa-velha"]


def test_an_abandoned_bridge_never_answers_later_questions():
    """A question arriving after the bridge was abandoned does not become "cancelled"."""
    bridge = PromptBridge()
    bridge.abandon()
    with pytest.raises(PromptAbandoned):
        bridge.request(PromptKind.TEXT, title="t", prompt="?")


class _OnePromptClient:
    """A stream that delivers one question and records what went back to the daemon."""

    def __init__(self) -> None:
        self.answers: list = []

    def stream_events(self, run_id: str, *, after: int = 0):
        yield {
            "type": "prompt.request",
            "id": "p1",
            "kind": "text",
            "payload": {"prompt": "?", "title": ""},
        }

    def close(self) -> None:
        pass

    def answer_prompt(self, prompt_id: str, answer):
        self.answers.append((prompt_id, answer))
        return {"ok": True}


def test_a_detached_session_does_not_answer_for_the_screen():
    """Detached mid-question, the session does not send `None` to the daemon."""
    client = _OnePromptClient()
    handler = MagicMock()
    session = EngineRunSession(stream=MagicMock(), prompt_handler=handler, client=client)

    def _left_while_asking(prompt: str, *, title: str = ""):
        session.detach()
        return None

    handler.ask_text.side_effect = _left_while_asking
    session.run_id = "run-1"
    session.listen()

    assert client.answers == []
