"""SIGTERM stops the daemon's runs before it exits.

Without it, the daemon exited with runs left `running` in the database and their
agent processes orphaned. Stopping a run is the path that records `RUN_STOPPED`,
puts the step back to pending and closes the ACP session (tested with `cancel`);
here the daemon must take that path for every run, and not start new ones.
"""

from __future__ import annotations

import signal
import threading

import pytest
import uvicorn
from fastapi.testclient import TestClient

from pulse.api.app import create_app
from pulse.daemon.runs import DaemonShuttingDown, RunManager, RunState
from pulse.daemon.server import GracefulServer
from pulse.domain.control import RUN_STOPPED, RunControl
from pulse.domain.ports import PromptPort
from pulse.domain.run import RunStatus
from tests.conftest import make_workflow


def _engine_waiting_on_the_user(
    *, prompt_handler: PromptPort, control: RunControl, **_kwargs: object
) -> int:
    """A run parked on a question, the usual state of a run when the daemon is stopped."""
    prompt_handler.ask_text("Continue?")
    return RUN_STOPPED if control.interrupted else 0


def _wait_for_the_question(state: RunState) -> None:
    for event in state.bus.subscribe():
        if event.get("type") == "prompt.request":
            return


def test_shutdown_stops_a_run_waiting_on_the_user(monkeypatch, tmp_path) -> None:
    make_workflow("demo")
    monkeypatch.setattr("pulse.daemon.runs.run_engine", _engine_waiting_on_the_user)
    manager = RunManager()
    state = manager.start_run(workflow_id="demo", prompt="x", workspace=str(tmp_path))
    _wait_for_the_question(state)

    left = manager.shutdown(grace=5.0)

    assert left == []
    assert state.status == RunStatus.STOPPED
    assert state.exit_code == RUN_STOPPED
    assert not state.is_active()


def test_shutdown_names_the_runs_that_did_not_stop_in_time(monkeypatch, tmp_path) -> None:
    """The daemon still exits, but the log must say which run it left behind."""
    make_workflow("demo")
    release = threading.Event()

    def stuck_engine(**_kwargs: object) -> int:
        release.wait(5)
        return RUN_STOPPED

    monkeypatch.setattr("pulse.daemon.runs.run_engine", stuck_engine)
    manager = RunManager()
    state = manager.start_run(workflow_id="demo", prompt="x", workspace=str(tmp_path))

    try:
        assert manager.shutdown(grace=0.0) == [state.id]
        assert state.control.interrupted
    finally:
        release.set()


def test_no_run_starts_once_shutdown_began(monkeypatch, tmp_path) -> None:
    """A run started now would outlive the stop and be orphaned with its agent."""
    make_workflow("demo")
    monkeypatch.setattr("pulse.daemon.runs.run_engine", _engine_waiting_on_the_user)
    manager = RunManager()
    manager.shutdown(grace=0.0)

    with pytest.raises(DaemonShuttingDown):
        manager.start_run(workflow_id="demo", prompt="x", workspace=str(tmp_path))

    response = TestClient(create_app(manager), base_url="http://127.0.0.1").post(
        "/api/workflows/demo/runs", json={"prompt": "x", "workspace": str(tmp_path)}
    )
    assert response.status_code == 503
    assert manager.list_runs() == []


def _stopped(server: GracefulServer) -> None:
    assert server.stopping is not None
    server.stopping.join()


def test_the_first_signal_stops_the_runs_before_the_server_exits() -> None:
    calls: list[bool] = []
    server = GracefulServer(
        uvicorn.Config(create_app(RunManager())),
        before_exit=lambda: calls.append(server.should_exit),
    )

    server.handle_exit(signal.SIGTERM, None)
    _stopped(server)

    assert calls == [False]
    assert server.should_exit


def test_the_runs_stop_off_the_thread_the_signal_lands_on() -> None:
    """The signal lands on the event loop's thread, which may hold a lock the stop needs.

    `run_events` holds `RunManager`'s lock there; stopping the runs inside the
    handler waited on it forever, until a second signal.
    """
    held_by_the_loop = threading.Lock()

    def stop_needing_the_lock() -> None:
        with held_by_the_loop:
            pass

    server = GracefulServer(
        uvicorn.Config(create_app(RunManager())), before_exit=stop_needing_the_lock
    )

    with held_by_the_loop:
        server.handle_exit(signal.SIGTERM, None)
        assert not server.should_exit

    _stopped(server)
    assert server.should_exit
    assert not server.force_exit


def test_a_second_signal_forces_the_exit_without_stopping_again() -> None:
    """Ctrl-C twice keeps uvicorn's meaning: stop waiting."""
    calls: list[int] = []
    server = GracefulServer(
        uvicorn.Config(create_app(RunManager())), before_exit=lambda: calls.append(1)
    )

    server.handle_exit(signal.SIGINT, None)
    _stopped(server)
    server.handle_exit(signal.SIGINT, None)

    assert calls == [1]
    assert server.force_exit


def test_a_signal_arriving_while_the_runs_stop_forces_the_exit() -> None:
    """The stop can take the whole grace period: a second Ctrl-C must force the
    exit right away, not start a second stop."""
    calls: list[int] = []
    release = threading.Event()

    def stop_still_running() -> None:
        calls.append(1)
        release.wait()

    server = GracefulServer(
        uvicorn.Config(create_app(RunManager())), before_exit=stop_still_running
    )

    server.handle_exit(signal.SIGINT, None)
    server.handle_exit(signal.SIGINT, None)

    assert server.force_exit
    assert server.should_exit
    release.set()
    _stopped(server)
    assert calls == [1]


def test_a_run_left_behind_is_logged_by_id(monkeypatch, tmp_path, caplog) -> None:
    from pulse.daemon import server as server_module

    make_workflow("demo")
    release = threading.Event()

    def stuck_engine(**_kwargs: object) -> int:
        release.wait(5)
        return RUN_STOPPED

    monkeypatch.setattr("pulse.daemon.runs.run_engine", stuck_engine)
    manager = RunManager()
    state = manager.start_run(workflow_id="demo", prompt="x", workspace=str(tmp_path))

    try:
        with caplog.at_level("WARNING", logger="pulse.daemon.server"):
            server_module.stop_runs(manager, grace=0.0)
    finally:
        release.set()

    assert state.id in caplog.text
