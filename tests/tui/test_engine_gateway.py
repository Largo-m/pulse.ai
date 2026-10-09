"""The TUI's gateway to the daemon: typed answers, and a failure the screens can show.

A daemon that cannot be reached must surface as `EngineUnavailable`, never as a
transport exception that would crash a screen; an unknown id is `None`, not an error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pulse.client.engine_client import SCREEN_TIMEOUT_SECONDS, EngineClient
from pulse.config.project_config import init_project_config
from pulse.tui import engine, strings
from tests.tui.conftest import DAEMON_DOWN


def test_an_unreachable_daemon_is_engine_unavailable(daemon_down, tmp_path: Path) -> None:
    with pytest.raises(engine.EngineUnavailable, match=DAEMON_DOWN):
        engine.history(tmp_path)


def test_a_screen_read_never_starts_a_daemon(daemon_down, monkeypatch, tmp_path: Path) -> None:
    """Screens read on the event loop: spawning and polling a daemon froze them for 20s.

    The CLI starts the daemon before any screen opens; a read only reports it is gone.
    """
    spawned: list[str] = []

    def spawn(_self: object) -> None:
        spawned.append("start")
        raise RuntimeError("spawned a daemon")

    monkeypatch.setattr(EngineClient, "_start_daemon", spawn)

    with pytest.raises(engine.EngineUnavailable, match=DAEMON_DOWN):
        engine.history(tmp_path)

    assert spawned == []


def test_a_daemon_that_fails_the_request_refused_it_with_its_reason(
    monkeypatch, tmp_path: Path
) -> None:
    """The daemon answered, so it is not unavailable: the screen shows what went wrong."""

    def broken(*_args: object) -> list:
        raise OSError("disk gone")

    monkeypatch.setattr("pulse.history.catalog.HistoryCatalog.list_items", broken)

    with pytest.raises(engine.EngineRefused, match="disk gone") as caught:
        engine.history(tmp_path)

    assert not isinstance(caught.value, engine.EngineUnavailable)


def test_a_rejected_value_is_refused_with_the_daemons_detail(
    tmp_path: Path, in_process_daemon
) -> None:
    init_project_config(tmp_path)

    with pytest.raises(engine.EngineRefused) as caught:
        engine.save_default(tmp_path, "permission_policy", "nope")

    assert str(caught.value) == "unknown policy: nope"
    assert caught.value.describe() == strings.ENGINE_REFUSED.format(error="unknown policy: nope")


def test_an_unreachable_daemon_describes_itself_as_unavailable(daemon_down, tmp_path: Path) -> None:
    with pytest.raises(engine.EngineUnavailable) as caught:
        engine.history(tmp_path)

    assert caught.value.describe() == strings.ENGINE_UNAVAILABLE.format(error=DAEMON_DOWN)


def test_unknown_ids_are_none(tmp_path: Path) -> None:
    assert engine.history_item(tmp_path, "nope") is None
    assert engine.run_log("nope") is None
    assert engine.worktree_state(tmp_path, "nope") is None
    assert engine.delete_history_item(tmp_path, "nope") is False
    assert engine.remove_worktree(tmp_path, "nope") is False
    assert engine.workflow("nope") is None


def test_workflows_come_back_with_their_steps_in_order() -> None:
    from tests.conftest import make_workflow

    make_workflow("demo", steps=[("plan", "Planejar"), ("run", "Implementar")], label="Demo")

    shape = engine.workflow("demo")

    assert shape is not None
    assert (shape.label, shape.steps) == ("Demo", (("plan", "Planejar"), ("run", "Implementar")))


def test_a_worktree_the_daemon_still_uses_is_refused_as_in_use(
    monkeypatch, tmp_path: Path, in_process_daemon
) -> None:
    """A 409 is the daemon keeping the worktree for a live run, not an unreachable daemon."""
    import threading

    from pulse.domain.run import StepRecord
    from pulse.store import runs as run_store
    from tests.conftest import make_workflow

    make_workflow("demo", steps=[("plan", "Planejar")])
    record = run_store.create_run(
        run_id="run-live",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[StepRecord(step_id="plan", position=1, label="Planejar", agent_id="tester")],
    )
    release = threading.Event()

    def engine_at_work(**_kwargs: object) -> int:
        release.wait(5)
        return 0

    monkeypatch.setattr("pulse.daemon.runs.run_engine", engine_at_work)
    in_process_daemon.app.state.runs.start_run(
        workflow_id="demo", prompt="x", workspace=str(tmp_path), resume_run_id=record.id
    )
    item_id = engine.history(tmp_path)[0].item_id
    try:
        with pytest.raises(engine.WorktreeInUse):
            engine.remove_worktree(tmp_path, item_id)
    finally:
        release.set()


def _timeouts_of(monkeypatch: pytest.MonkeyPatch, call: object) -> list[float]:
    used: list[float] = []
    build = EngineClient.__init__

    def recording(self: EngineClient, **kwargs: Any) -> None:
        used.append(kwargs.get("timeout", 30.0))
        build(self, **kwargs)

    monkeypatch.setattr(EngineClient, "__init__", recording)
    with pytest.raises(engine.EngineUnavailable):
        call()  # type: ignore[operator]  # a zero-argument gateway call
    return used


@pytest.mark.usefixtures("daemon_down")
def test_a_screen_read_waits_only_the_screen_timeout(monkeypatch, tmp_path: Path) -> None:
    """Screens read on the event loop: a slow daemon froze them for the client's 30s."""
    assert _timeouts_of(monkeypatch, lambda: engine.history(tmp_path)) == [SCREEN_TIMEOUT_SECONDS]
    assert _timeouts_of(monkeypatch, lambda: engine.setup_state(tmp_path)) == [
        SCREEN_TIMEOUT_SECONDS
    ]


@pytest.mark.usefixtures("daemon_down")
def test_a_probe_keeps_the_time_its_checks_need(monkeypatch, tmp_path: Path) -> None:
    """Doctor checks and the ACP probe spawn agents; the screen timeout would cut them short."""
    assert _timeouts_of(monkeypatch, engine.doctor_checks) == [engine.PROBE_TIMEOUT_SECONDS]
    assert _timeouts_of(monkeypatch, lambda: engine.acp_probe(tmp_path, "claude")) == [
        engine.PROBE_TIMEOUT_SECONDS
    ]
    assert engine.PROBE_TIMEOUT_SECONDS > SCREEN_TIMEOUT_SECONDS
