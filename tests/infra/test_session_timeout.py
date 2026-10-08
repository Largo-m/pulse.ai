"""The `session/prompt` deadline measures agent silence, not total work duration.

Long implementation steps and slow user approvals must not be killed by a total timeout.
"""

from __future__ import annotations

import threading
import time

import pytest

from pulse.acp.session_runner import AcpSessionRunner


def _runner(timeout: float) -> AcpSessionRunner:
    """Process-less runner: just enough to exercise `_request`."""
    runner = AcpSessionRunner(["fake-agent"], cwd="/repo", timeout_seconds=timeout)
    runner._send = lambda _payload: None  # type: ignore[method-assign]
    runner._session_id = "sess-1"
    return runner


def _reply_after(runner: AcpSessionRunner, delay: float, result: dict) -> threading.Thread:
    def later() -> None:
        time.sleep(delay)
        runner._responses[1] = {"id": 1, "result": result}
        runner._response_queue.put(1)

    thread = threading.Thread(target=later, daemon=True)
    thread.start()
    return thread


def test_an_agent_that_keeps_talking_does_not_time_out():
    """Each received line renews the deadline: working is not hanging."""
    runner = _runner(0.3)

    def chatter() -> None:
        for _ in range(6):
            time.sleep(0.1)
            runner._activity = time.monotonic()
        runner._responses[1] = {"id": 1, "result": {"stopReason": "end_turn"}}
        runner._response_queue.put(1)

    threading.Thread(target=chatter, daemon=True).start()

    assert runner._request("session/prompt", {}) == {"stopReason": "end_turn"}


def test_a_question_on_screen_does_not_spend_the_agents_clock():
    """Waiting for the user is our wait; it must not count against the agent."""
    runner = _runner(0.3)

    def asking() -> None:
        runner._begin_user_wait()
        time.sleep(0.7)
        runner._end_user_wait()
        runner._responses[1] = {"id": 1, "result": {"stopReason": "end_turn"}}
        runner._response_queue.put(1)

    threading.Thread(target=asking, daemon=True).start()

    assert runner._request("session/prompt", {}) == {"stopReason": "end_turn"}


def test_silence_beyond_the_deadline_still_times_out():
    runner = _runner(0.2)

    with pytest.raises(TimeoutError, match="session/prompt"):
        runner._request("session/prompt", {})


def test_a_short_request_keeps_the_total_deadline():
    """`initialize` and similar requests get no silence clock: they are immediate."""
    runner = _runner(0.3)
    _reply_after(runner, 0.5, {"protocolVersion": 1})

    try:
        runner._request("initialize", {})
    except TimeoutError:
        pass
    else:  # pragma: no cover - the test fails first
        raise AssertionError("the total deadline of a short request is not renewed")


def test_a_dead_process_ends_the_wait_right_away():
    """Without a process there is no reply to wait for, let alone a 10-minute deadline."""

    class _Dead:
        def poll(self) -> int:
            return 1

    runner = _runner(600.0)
    runner._process = _Dead()  # type: ignore[assignment]

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="encerrou"):
        runner._request("session/close", {"sessionId": "sess-1"})
    assert time.monotonic() - started < 5.0


def test_closing_a_silent_session_does_not_wait_the_whole_timeout(monkeypatch):
    """After a hang, `session/close` must not cost another 10 minutes."""
    import pulse.acp.session_runner as session_runner

    monkeypatch.setattr(session_runner, "CLOSE_TIMEOUT_SECONDS", 0.2)
    runner = _runner(600.0)

    started = time.monotonic()
    runner.close_session()

    assert time.monotonic() - started < 2.0
    assert runner._session_id is None


def test_retry_after_a_timeout_restarts_a_process_that_is_alive_but_mute():
    """`poll()` says it is alive; the exceeded deadline says it is not responding."""

    class _Alive:
        def poll(self) -> None:
            return None

    runner = _runner(0.2)
    runner._process = _Alive()  # type: ignore[assignment]
    try:
        runner._request("session/prompt", {})
    except TimeoutError:
        pass

    restarted: list[str] = []
    runner.close = lambda: restarted.append("close")  # type: ignore[method-assign]
    runner.start = lambda: restarted.append("start")  # type: ignore[method-assign]
    runner.initialize = lambda: restarted.append("initialize")  # type: ignore[method-assign]
    runner.authenticate = lambda: restarted.append("authenticate")  # type: ignore[method-assign]

    assert runner.revive() is True
    assert restarted == ["close", "start", "initialize", "authenticate"]
