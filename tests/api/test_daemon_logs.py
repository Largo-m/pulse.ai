"""The daemon log tells what happened to each run, findable by `run_id`.

Before it, a run's start, end or crash left nothing in `~/.pulse/daemon.log`
but a bare traceback, with no way to tell which run it belonged to.
"""

from __future__ import annotations

import io
import itertools
import logging

import pytest

from pulse.client.protocol import REPLAY_END
from pulse.daemon.adapters import ApiStreamSink
from pulse.daemon.events import EventBus
from pulse.daemon.logs import LOGGER, configure_logging
from pulse.daemon.runs import RunManager, RunState
from pulse.domain.control import RUN_BLOCKED
from tests.conftest import make_workflow

PRIVATE_PROMPT = "refactor the billing module of acme-internal"
AGENT_LABEL = "migrate /srv/acme/billing with key sk-live-123"


@pytest.fixture
def daemon_log(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.INFO, logger=LOGGER)
    return caplog


def _finished(state: RunState) -> None:
    for event in state.bus.subscribe():
        if event.get("type") == "run.finished":
            return


def _messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name.startswith(LOGGER)]


def test_a_run_logs_its_start_and_how_it_ended(monkeypatch, tmp_path, daemon_log) -> None:
    make_workflow("demo")
    monkeypatch.setattr("pulse.daemon.runs.run_engine", lambda **_: RUN_BLOCKED)
    state = RunManager().start_run(
        workflow_id="demo", prompt=PRIVATE_PROMPT, workspace=str(tmp_path)
    )
    _finished(state)

    messages = _messages(daemon_log)

    assert f"run.started run_id={state.id} workflow=demo resumed=False" in messages
    finished = [line for line in messages if line.startswith("run.finished")]
    assert len(finished) == 1
    assert f"run_id={state.id} status=blocked exit_code={RUN_BLOCKED}" in finished[0]


def test_a_crash_is_logged_with_its_run_and_traceback(monkeypatch, tmp_path, daemon_log) -> None:
    make_workflow("demo")

    def crashing_engine(**_kwargs: object) -> int:
        raise RuntimeError("runtime vanished")

    monkeypatch.setattr("pulse.daemon.runs.run_engine", crashing_engine)
    state = RunManager().start_run(workflow_id="demo", prompt="x", workspace=str(tmp_path))
    _finished(state)

    failed = [
        record for record in daemon_log.records if record.getMessage().startswith("run.failed")
    ]
    assert len(failed) == 1
    assert failed[0].levelno == logging.ERROR
    assert f"run_id={state.id}" in failed[0].getMessage()
    assert failed[0].exc_info is not None
    assert str(failed[0].exc_info[1]) == "runtime vanished"


def test_the_user_prompt_never_reaches_the_log(monkeypatch, tmp_path, daemon_log) -> None:
    """Prompts carry whatever the user typed, credentials included (AGENTS.md §6.1)."""
    make_workflow("demo")
    monkeypatch.setattr("pulse.daemon.runs.run_engine", lambda **_: 0)
    state = RunManager().start_run(
        workflow_id="demo", prompt=PRIVATE_PROMPT, workspace=str(tmp_path)
    )
    _finished(state)

    assert _messages(daemon_log)
    assert PRIVATE_PROMPT not in daemon_log.text


def test_each_step_status_change_is_logged_once(daemon_log) -> None:
    """The engine resends every status on each sync; repeating them would bury the change."""
    sink = ApiStreamSink(EventBus(), run_id="r1")

    sink.apply_phase_statuses(done_ids=["plan"])
    sink.apply_phase_statuses(done_ids=["plan"], blocked_ids=["build"])
    sink.apply_phase_statuses(done_ids=["plan", "build"])

    assert [line for line in _messages(daemon_log) if line.startswith("step.status")] == [
        "step.status run_id=r1 step=plan status=done",
        "step.status run_id=r1 step=build status=blocked",
        "step.status run_id=r1 step=build status=done",
    ]


def test_a_phase_title_reaches_the_screen_but_not_the_log(daemon_log) -> None:
    """A fan-out step is titled with the label the previous agent wrote (AGENTS.md §6.1)."""
    bus = EventBus()
    sink = ApiStreamSink(bus, run_id="r1")

    sink.begin_phase(AGENT_LABEL, turn=2)

    assert [line for line in _messages(daemon_log) if line.startswith("phase.begin")] == [
        "phase.begin run_id=r1 turn=2"
    ]
    assert AGENT_LABEL not in daemon_log.text
    replay = itertools.takewhile(lambda event: event["type"] != REPLAY_END, bus.subscribe())
    assert [event["title"] for event in replay if event["type"] == "phase.begin"] == [AGENT_LABEL]


def test_waiting_on_the_user_is_logged_with_the_run(daemon_log) -> None:
    sink = ApiStreamSink(EventBus(), run_id="r1")

    sink.begin_user_wait()
    sink.end_user_wait()

    assert [line for line in _messages(daemon_log) if line.startswith("run.awaiting")] == [
        "run.awaiting run_id=r1 waiting=True",
        "run.awaiting run_id=r1 waiting=False",
    ]


def test_configuring_twice_writes_each_line_once() -> None:
    stream = io.StringIO()
    logger = logging.getLogger(LOGGER)
    before = list(logger.handlers)
    try:
        configure_logging(stream)
        configure_logging(stream)
        logging.getLogger("pulse.daemon.runs").info("run.started run_id=r1")
    finally:
        logger.handlers[:] = before

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert lines[0].endswith("INFO pulse.daemon.runs run.started run_id=r1")
