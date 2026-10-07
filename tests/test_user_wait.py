"""Waiting for the user does not count as agent work.

While a prompt is open (permission, questionnaire, approval, retry menu) the run
is alive but paused: the step clock freezes, the waited time is excluded from the
stored duration, and the run is listed as `awaiting_input`.
"""

from __future__ import annotations

import time
from pathlib import Path

from pulse.acp.session_runner import AcpSessionRunner, _WatchedPrompts
from pulse.history.events import PhaseItem, PhaseStatus
from pulse.store import runs as run_store
from pulse.store.runs import AWAITING_INPUT, RUNNING, RunStatus, StepRecord
from pulse.tui.hydrate import _stamp_elapsed
from pulse.tui.state import CockpitState


def _run_with_step(step_id: str = "one") -> run_store.RunRecord:
    return run_store.create_run(
        run_id="run-1",
        workflow_id="demo",
        workspace=Path.cwd(),
        user_prompt="tarefa",
        steps=[StepRecord(step_id=step_id, position=1, label="Um", agent_id="tester")],
    )


def test_the_step_clock_freezes_while_the_question_is_open():
    phase = PhaseItem(id="one", label="Um", status=PhaseStatus.RUNNING, started_at=0.0)
    assert phase.elapsed_label(now=10.0) == "00:10"

    phase.begin_waiting(now=10.0)
    assert phase.elapsed_label(now=310.0) == "00:10"
    assert phase.display_status() == "awaiting_input"

    phase.end_waiting(now=310.0)
    assert phase.elapsed_label(now=320.0) == "00:20"
    assert phase.display_status() == PhaseStatus.RUNNING.value


def test_two_waits_in_the_same_step_both_come_off_the_clock():
    phase = PhaseItem(id="one", label="Um", status=PhaseStatus.RUNNING, started_at=0.0)
    phase.begin_waiting(now=5.0)
    phase.end_waiting(now=65.0)
    phase.begin_waiting(now=70.0)
    phase.end_waiting(now=100.0)
    assert phase.elapsed_label(now=100.0) == "00:10"


def test_finishing_a_step_that_is_waiting_closes_the_wait():
    phase = PhaseItem(id="one", label="Um", status=PhaseStatus.RUNNING, started_at=0.0)
    phase.begin_waiting(now=10.0)
    phase.finish(ended_at=40.0)
    assert phase.awaiting_since is None
    assert phase.elapsed_label() == "00:10"


def test_cockpit_state_marks_the_running_phase_and_the_run():
    state = CockpitState()
    state.phases = [
        PhaseItem(id="one", label="Um", status=PhaseStatus.DONE),
        PhaseItem(id="two", label="Dois", status=PhaseStatus.RUNNING, started_at=0.0),
    ]

    state.begin_waiting()
    assert state.awaiting_input is True
    assert state.phases[1].awaiting_since is not None
    assert state.phases[0].awaiting_since is None

    state.end_waiting()
    assert state.awaiting_input is False
    assert state.phases[1].awaiting_since is None


def test_stopping_a_waiting_run_clears_the_wait():
    state = CockpitState()
    state.phases = [PhaseItem(id="one", label="Um", status=PhaseStatus.RUNNING, started_at=0.0)]
    state.begin_waiting()
    state.mark_stopped()
    assert state.awaiting_input is False
    assert state.phases[0].awaiting_since is None
    assert state.phases[0].status == PhaseStatus.PENDING


def test_waiting_seconds_accumulate_and_survive_save_step():
    run = _run_with_step()
    step = run.steps[0]
    run_store.save_step(run.id, step)

    run_store.add_waiting_seconds(run.id, step.step_id, 30.0)
    run_store.add_waiting_seconds(run.id, step.step_id, 12.5)
    assert run_store.load_run(run.id).steps[0].waiting_seconds == 42.5

    step.status = "done"
    run_store.save_step(run.id, step)
    assert run_store.load_run(run.id).steps[0].waiting_seconds == 42.5


def test_waiting_is_ignored_for_a_step_that_is_not_there():
    run = _run_with_step()
    run_store.add_waiting_seconds(run.id, "fantasma", 10.0)
    assert run_store.load_run(run.id).steps[0].waiting_seconds == 0.0


def test_a_database_from_before_the_column_gains_it_on_open(tmp_path: Path):
    """An already-deployed database must not break or lose the old run."""
    import sqlite3

    from pulse.store.db import connect

    db_path = tmp_path / "antigo.db"
    connect(db_path).close()

    raw = sqlite3.connect(str(db_path))
    raw.execute("ALTER TABLE run_steps DROP COLUMN waiting_seconds")
    raw.commit()
    raw.close()

    run_store.create_run(
        run_id="run-velha",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
        db_path=db_path,
    )
    record = run_store.load_run("run-velha", db_path=db_path)
    assert record.steps[0].waiting_seconds == 0.0


def test_history_duration_discounts_the_wait():
    run = _run_with_step()
    step = run.steps[0]
    step.started_at = "2026-10-01T10:00:00+00:00"
    step.ended_at = "2026-10-01T10:10:00+00:00"
    step.status = "done"
    run_store.save_step(run.id, step)
    run_store.add_waiting_seconds(run.id, step.step_id, 540.0)

    state = CockpitState()
    state.phases = [PhaseItem(id="one", label="Um", status=PhaseStatus.DONE)]
    _stamp_elapsed(state, run.id)
    assert state.phases[0].elapsed_label() == "01:00"


def _permission(kind: str = "edit") -> dict:
    return {
        "permission": {"title": "Editar app.py", "kind": kind},
        "toolCall": {"kind": kind, "rawInput": {"path": "/repo/app.py"}},
        "options": [
            {"optionId": "allow-once", "kind": "allow_once"},
            {"optionId": "reject-once", "kind": "reject_once"},
        ],
    }


def _port_and_bus():
    """The daemon port as the engine sees it: through the runner proxy, where
    the policy decides before opening the wait."""
    from pulse.daemon.adapters import ApiPromptPort, ApiStreamSink
    from pulse.daemon.events import EventBus, PromptCorrelator

    bus = EventBus()
    correlator = PromptCorrelator(bus)
    runner = AcpSessionRunner(
        ["echo"],
        cwd=str(Path.cwd()),
        stream=ApiStreamSink(bus),
        prompt_handler=ApiPromptPort(correlator),
    )
    return runner._prompt_handler, correlator, bus


def test_a_permission_the_policy_resolves_never_becomes_a_question():
    """With the cockpit closed, an `edit` under `deny_writes` used to hang the run.

    The daemon published a prompt nobody could answer for a decision the policy
    had already made.
    """
    for policy, expected in [("deny_writes", "reject-once"), ("auto_approve", "allow-once")]:
        port, correlator, bus = _port_and_bus()
        answer = port.respond_to_permission(_permission(), policy=policy)
        assert answer["outcome"]["optionId"] == expected
        assert correlator.pending() == [], f"{policy} must not leave a prompt open"
        assert [e for e in bus._history if e["type"] == "prompt.request"] == []
        assert [e for e in bus._history if e["type"] == "run.awaiting"] == [], policy


def test_a_policy_decision_never_touches_the_run_status():
    """Each tool call in an `auto_approve` step used to store `awaiting_input` then
    `running`, making the run flicker in Home and history."""
    run = _run_with_step()
    run_store.save_step(run.id, run.steps[0])
    port, _correlator, _bus = _port_and_bus()
    runner = port._on_enter.__self__
    runner.bind_run(run.id)
    run_store.update_run(run.id, status=RunStatus.BLOCKED)

    port.respond_to_permission(_permission(), policy="auto_approve")

    assert run_store.load_run(run.id).status == RunStatus.BLOCKED


def test_the_terminal_veto_is_decided_without_asking_anyone():
    """Terminal is a Pulse veto, not a question: not even `ask` prompts for it."""
    for kind in ("terminal", "shell", "bash", "run_command"):
        port, correlator, _bus = _port_and_bus()
        answer = port.respond_to_permission(_permission(kind), policy="ask")
        assert answer["outcome"]["optionId"] == "reject-once", kind
        assert correlator.pending() == [], kind


def test_a_permission_that_needs_a_person_still_waits():
    """Under `ask`, asking is the point, so it still waits."""
    from concurrent.futures import ThreadPoolExecutor

    port, correlator, _bus = _port_and_bus()
    with ThreadPoolExecutor(max_workers=1) as pool:
        asking = pool.submit(port.respond_to_permission, _permission(), policy="ask")
        deadline = time.monotonic() + 2
        while not correlator.pending() and time.monotonic() < deadline:
            time.sleep(0.01)
        pending = correlator.pending()
        assert len(pending) == 1
        correlator.answer(pending[0].id, {"outcome": {"outcome": "selected", "optionId": "allow-once"}})
        assert asking.result(timeout=5)["outcome"]["optionId"] == "allow-once"


def test_waiting_runs_come_oldest_first_and_say_how_long(monkeypatch):
    import pulse.client.active_runs as active_runs_module
    from pulse.client.active_runs import awaiting_runs, describe, waiting_for

    now = 1_000_000.0
    runs = [
        {"id": "nova", "awaiting_prompt": True, "awaiting_since": now - 30, "active": True},
        {"id": "velha", "awaiting_prompt": True, "awaiting_since": now - 4000, "active": True},
        {"id": "rodando", "awaiting_prompt": False, "active": True},
    ]
    monkeypatch.setattr(active_runs_module, "list_runs", lambda: runs)

    assert [item["id"] for item in awaiting_runs()] == ["velha", "nova"]

    assert waiting_for(runs[0], now=now) == "30s"
    assert waiting_for(runs[1], now=now) == "1h06"
    assert waiting_for({"id": "x"}, now=now) == ""

    line = describe(
        {
            "workflow_label": "Nova spec",
            "current_step_label": "Especificar",
            "awaiting_prompt": True,
            "awaiting_since": time.time() - 180,
        }
    )
    assert line == "Nova spec · Especificar · precisa de você há 3min"


class _Sink:
    def __init__(self) -> None:
        self.events: list[str] = []

    def begin_user_wait(self) -> None:
        self.events.append("begin")

    def end_user_wait(self) -> None:
        self.events.append("end")


class _Port:
    """Port that asks another question in the middle of the first: a nested wait."""

    def __init__(self, runner: AcpSessionRunner | None = None) -> None:
        self._runner = runner
        self.asked: list[str] = []

    def ask_text(self, prompt: str, *, title: str = "") -> str:
        self.asked.append(prompt)
        if self._runner is not None and len(self.asked) == 1:
            self._runner._prompt_handler.select_choice("e isso?", [])
        return "ok"

    def select_choice(self, prompt: str, choices, *, title: str = ""):
        self.asked.append(prompt)
        return None


def _runner(sink: _Sink, port: _Port) -> AcpSessionRunner:
    return AcpSessionRunner(["echo"], cwd=str(Path.cwd()), stream=sink, prompt_handler=port)


def test_every_question_opens_and_closes_exactly_one_wait():
    sink = _Sink()
    runner = _runner(sink, _Port())
    runner._prompt_handler.ask_text("e agora?")
    assert sink.events == ["begin", "end"]


def test_a_question_inside_another_is_one_wait_only():
    """Otherwise the nested wait would discount the same time twice."""
    sink = _Sink()
    port = _Port()
    runner = _runner(sink, port)
    port._runner = runner
    runner._prompt_handler.ask_text("e agora?")
    assert sink.events == ["begin", "end"]
    assert len(port.asked) == 2


def test_the_wait_lands_on_the_bound_run_and_step():
    run = _run_with_step()
    run_store.save_step(run.id, run.steps[0])
    sink = _Sink()
    runner = _runner(sink, _Port())
    runner.bind_run(run.id)
    runner._phase_id = "one"

    runner._begin_user_wait()
    assert run_store.load_run(run.id).status == AWAITING_INPUT
    runner._end_user_wait()

    record = run_store.load_run(run.id)
    assert record.status == RUNNING
    assert record.steps[0].waiting_seconds >= 0.0


def test_the_wait_travels_from_the_runner_to_the_screen():
    """Contract between both ends: what the daemon publishes is what the screen reads.

    The bus event, not the local dock, freezes the screen clock so two windows on
    the same run stop together. Renaming the event on one side only fails here.
    """
    from unittest.mock import MagicMock

    from pulse.client.run_session import EngineRunSession
    from pulse.daemon.adapters import ApiStreamSink
    from pulse.daemon.events import EventBus

    bus = EventBus()
    sink = _runner(ApiStreamSink(bus), _Port())
    sink._prompt_handler.ask_text("e agora?")

    published = [event for event in bus._history if event["type"] == "run.awaiting"]
    assert [event["waiting"] for event in published] == [True, False]

    state = CockpitState()
    state.phases = [PhaseItem(id="one", label="Um", status=PhaseStatus.RUNNING, started_at=0.0)]
    from pulse.tui.adapters.cockpit_sink import CockpitSink

    session = EngineRunSession(
        stream=CockpitSink(state, on_change=lambda: None),
        prompt_handler=MagicMock(),
        client=MagicMock(),
    )
    session._dispatch(published[0])
    assert state.awaiting_input is True
    session._dispatch(published[1])
    assert state.awaiting_input is False


def test_the_proxy_still_hides_nothing_from_whoever_asks():
    """The engine's `_choose` probes the port for `select_choice`; ports without it
    must still report that it is missing."""
    proxy = _WatchedPrompts(object(), on_enter=lambda: None, on_exit=lambda: None)
    try:
        proxy.select_choice
    except AttributeError:
        return
    raise AssertionError("the proxy invented a method the port does not have")


def test_reattaching_mid_wait_freezes_the_clock_where_the_run_stopped():
    """A step started 10min ago, worked 2 and has waited 8: a reattach must show
    `02:00` frozen, not `10:00`, which would count the wait as agent work."""
    from datetime import UTC, datetime, timedelta

    from pulse.client.run_session import EngineRunSession
    from pulse.tui.adapters.cockpit_sink import CockpitSink
    from pulse.tui.hydrate import stamp_live_elapsed
    from unittest.mock import MagicMock

    run = _run_with_step()
    step = run.steps[0]
    step.status = RUNNING
    step.started_at = (datetime.now(UTC) - timedelta(minutes=10)).replace(microsecond=0).isoformat()
    run_store.save_step(run.id, step)

    state = CockpitState()
    state.phases = [PhaseItem(id="one", label="Um", status=PhaseStatus.RUNNING, started_at=0.0)]
    session = EngineRunSession(
        stream=CockpitSink(state, on_change=lambda: None),
        prompt_handler=MagicMock(),
        client=MagicMock(),
    )
    session._dispatch({"type": "run.awaiting", "waiting": True, "since": time.time() - 8 * 60})
    stamp_live_elapsed(state, run.id)

    assert state.phases[0].elapsed_label() == "02:00"
