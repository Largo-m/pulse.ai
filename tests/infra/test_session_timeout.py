"""The `session/prompt` deadline measures agent silence, not total work duration.

Long implementation steps and slow user approvals must not be killed by a total timeout.

The runner's clock and reply queue run on simulated time: waiting for a reply
advances the clock and fires whatever the test scheduled for that instant, so
each scenario is deterministic and takes no wall-clock time.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from queue import Empty
from types import SimpleNamespace

import pytest

from pulse.acp import reply_clock, session_runner
from pulse.acp.session_runner import AcpSessionRunner


class SimulatedTime:
    """A monotonic clock that only moves when a wait advances it."""

    def __init__(self) -> None:
        self.now = 0.0
        self._events: list[tuple[float, Callable[[], None]]] = []

    def monotonic(self) -> float:
        return self.now

    def at(self, when: float, action: Callable[[], None]) -> None:
        self._events.append((when, action))
        self._events.sort(key=lambda event: event[0])

    def next_event(self) -> float | None:
        return self._events[0][0] if self._events else None

    def fire_next(self) -> None:
        when, action = self._events.pop(0)
        self.now = max(self.now, when)
        action()


class SimulatedQueue:
    """Reply queue whose `get(timeout)` spends simulated time instead of real time."""

    def __init__(self, clock: SimulatedTime) -> None:
        self._clock = clock
        self._items: deque[int] = deque()

    def put(self, item: int) -> None:
        self._items.append(item)

    def empty(self) -> bool:
        return not self._items

    def get_nowait(self) -> int:
        return self._items.popleft()

    def get(self, timeout: float) -> int:
        deadline = self._clock.now + timeout
        while not self._items:
            upcoming = self._clock.next_event()
            if upcoming is None or upcoming > deadline:
                self._clock.now = deadline
                raise Empty
            self._clock.fire_next()
        return self._items.popleft()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> SimulatedTime:
    simulated = SimulatedTime()
    fake_time = SimpleNamespace(monotonic=simulated.monotonic)
    for module in (session_runner, reply_clock):
        monkeypatch.setattr(module, "time", fake_time)
    return simulated


def _runner(clock: SimulatedTime, timeout: float) -> AcpSessionRunner:
    """Process-less runner: just enough to exercise `_request`."""
    runner = AcpSessionRunner(["fake-agent"], cwd="/repo", timeout_seconds=timeout)
    runner._send = lambda _payload: None  # type: ignore[method-assign]
    runner._session_id = "sess-1"
    runner._response_queue = SimulatedQueue(clock)  # type: ignore[assignment]
    return runner


def _reply(runner: AcpSessionRunner, result: dict) -> Callable[[], None]:
    def deliver() -> None:
        runner._responses[1] = {"id": 1, "result": result}
        runner._response_queue.put(1)

    return deliver


def _touch(runner: AcpSessionRunner, clock: SimulatedTime) -> Callable[[], None]:
    def activity() -> None:
        runner._activity = clock.monotonic()

    return activity


def test_an_agent_that_keeps_talking_does_not_time_out(clock):
    """Each received line renews the deadline: working is not hanging."""
    runner = _runner(clock, 0.3)
    for tick in range(1, 7):
        clock.at(tick * 0.1, _touch(runner, clock))
    clock.at(0.65, _reply(runner, {"stopReason": "end_turn"}))

    assert runner._request("session/prompt", {}) == {"stopReason": "end_turn"}
    assert clock.now == pytest.approx(0.65), "the turn outlived its 0.3s limit by talking"


def test_a_question_on_screen_does_not_spend_the_agents_clock(clock):
    """Waiting for the user is our wait; it must not count against the agent."""
    runner = _runner(clock, 0.3)
    clock.at(0.05, runner._begin_user_wait)
    clock.at(0.75, runner._end_user_wait)
    clock.at(0.8, _reply(runner, {"stopReason": "end_turn"}))

    assert runner._request("session/prompt", {}) == {"stopReason": "end_turn"}


def test_silence_beyond_the_deadline_still_times_out(clock):
    runner = _runner(clock, 0.2)

    with pytest.raises(TimeoutError, match="session/prompt"):
        runner._request("session/prompt", {})
    assert clock.now == pytest.approx(0.2)


def test_a_short_request_keeps_the_total_deadline(clock):
    """`initialize` and similar requests get no silence clock: they are immediate."""
    runner = _runner(clock, 0.3)
    clock.at(0.2, _touch(runner, clock))
    clock.at(0.5, _reply(runner, {"protocolVersion": 1}))

    with pytest.raises(TimeoutError, match="initialize"):
        runner._request("initialize", {})
    assert clock.now == pytest.approx(0.3), "activity must not renew a short request"


def test_a_dead_process_ends_the_wait_right_away(clock):
    """Without a process there is no reply to wait for, let alone a 10-minute deadline."""

    class _Dead:
        def poll(self) -> int:
            return 1

    runner = _runner(clock, 600.0)
    runner._process = _Dead()  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="^the agent process exited during `session/close`$"):
        runner._request("session/close", {"sessionId": "sess-1"})
    assert clock.now == 0.0


def test_closing_a_silent_session_does_not_wait_the_whole_timeout(clock):
    """After a hang, `session/close` must not cost another 10 minutes."""
    runner = _runner(clock, 600.0)

    runner.close_session()

    assert clock.now == pytest.approx(session_runner.CLOSE_TIMEOUT_SECONDS)
    assert runner._session_id is None


def test_retry_after_a_timeout_restarts_a_process_that_is_alive_but_mute(clock):
    """`poll()` says it is alive; the exceeded deadline says it is not responding."""

    class _Alive:
        def poll(self) -> None:
            return None

    runner = _runner(clock, 0.2)
    runner._process = _Alive()  # type: ignore[assignment]
    with pytest.raises(TimeoutError):
        runner._request("session/prompt", {})

    restarted: list[str] = []
    runner.close = lambda: restarted.append("close")  # type: ignore[method-assign]
    runner.start = lambda: restarted.append("start")  # type: ignore[method-assign]
    runner.initialize = lambda: restarted.append("initialize")  # type: ignore[method-assign]
    runner.authenticate = lambda: restarted.append("authenticate")  # type: ignore[method-assign]

    assert runner.revive() is True
    assert restarted == ["close", "start", "initialize", "authenticate"]
