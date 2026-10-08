from __future__ import annotations

import pytest

from pulse.acp import reply_clock
from pulse.acp.session_runner import AcpSessionRunner
from pulse.domain.control import RunControl


def _runner(control: RunControl) -> tuple[AcpSessionRunner, list[dict]]:
    """A runner without a process: just enough to exercise `_request`."""
    runner = AcpSessionRunner(["fake-agent"], cwd="/repo", control=control)
    sent: list[dict] = []
    runner._send = sent.append  # type: ignore[method-assign]
    runner._session_id = "sess-1"
    return runner, sent


def _reply(runner: AcpSessionRunner, request_id: int, result: dict) -> None:
    runner._responses[request_id] = {"id": request_id, "result": result}
    runner._response_queue.put(request_id)


def test_stop_cancels_the_turn_in_flight(monkeypatch):
    """Stopping sends `session/cancel` and returns the turn as cancelled."""
    monkeypatch.setattr(reply_clock, "CANCEL_GRACE_SECONDS", 0.3)
    control = RunControl()
    control.stop()
    runner, sent = _runner(control)

    result = runner._request("session/prompt", {"sessionId": "sess-1"})

    assert result == {"stopReason": "cancelled"}
    methods = [payload.get("method") for payload in sent]
    assert methods == ["session/prompt", "session/cancel"]
    assert sent[1]["params"] == {"sessionId": "sess-1"}
    assert "id" not in sent[1], "cancel is a notification, not a request"


def test_cancel_is_sent_once_even_while_waiting_for_the_agent(monkeypatch):
    monkeypatch.setattr(reply_clock, "CANCEL_GRACE_SECONDS", 0.5)
    control = RunControl()
    control.stop()
    runner, sent = _runner(control)

    runner._request("session/prompt", {"sessionId": "sess-1"})

    assert [payload.get("method") for payload in sent].count("session/cancel") == 1


def test_agent_answer_to_the_cancelled_turn_wins(monkeypatch):
    """If the agent closes the turn on its own, its answer wins."""
    monkeypatch.setattr(reply_clock, "CANCEL_GRACE_SECONDS", 5.0)
    control = RunControl()
    control.stop()
    runner, sent = _runner(control)
    _reply(runner, 1, {"stopReason": "cancelled", "phaseSummary": "parcial"})

    result = runner._request("session/prompt", {"sessionId": "sess-1"})

    assert result == {"stopReason": "cancelled", "phaseSummary": "parcial"}


def test_without_a_stop_the_turn_proceeds_normally():
    runner, sent = _runner(RunControl())
    _reply(runner, 1, {"stopReason": "end_turn"})

    result = runner._request("session/prompt", {"sessionId": "sess-1"})

    assert result == {"stopReason": "end_turn"}
    assert [payload.get("method") for payload in sent] == ["session/prompt"]


def test_stop_does_not_cut_short_protocol_requests(monkeypatch):
    """`initialize`, `session/new` and the like are not cancelled midway."""
    monkeypatch.setattr(reply_clock, "CANCEL_GRACE_SECONDS", 0.2)
    control = RunControl()
    control.stop()
    runner, sent = _runner(control)
    _reply(runner, 1, {"sessionId": "sess-2"})

    result = runner._request("session/new", {"cwd": "/repo"})

    assert result == {"sessionId": "sess-2"}
    assert [payload.get("method") for payload in sent] == ["session/new"]


def test_an_error_to_the_cancelled_turn_still_reads_as_cancelled(monkeypatch):
    """An agent may answer `session/cancel` by failing the turn: that is a stop, not a crash."""
    monkeypatch.setattr(reply_clock, "CANCEL_GRACE_SECONDS", 5.0)
    control = RunControl()
    control.stop()
    runner, _sent = _runner(control)
    runner._responses[1] = {"id": 1, "error": {"message": "turn aborted"}}
    runner._response_queue.put(1)

    assert runner._request("session/prompt", {"sessionId": "sess-1"}) == {"stopReason": "cancelled"}


def test_an_error_reply_without_a_stop_raises_the_agent_message():
    runner, _sent = _runner(RunControl())
    runner._responses[1] = {"id": 1, "error": {"message": "model unavailable"}}
    runner._response_queue.put(1)

    with pytest.raises(RuntimeError, match="model unavailable"):
        runner._request("session/prompt", {"sessionId": "sess-1"})


def test_a_stale_reply_to_an_earlier_request_is_dropped():
    """A late answer to a request that already gave up must not answer the current one."""
    runner, _sent = _runner(RunControl())
    runner._next_id = 2
    _reply(runner, 1, {"stopReason": "end_turn", "stale": True})
    _reply(runner, 2, {"stopReason": "end_turn"})

    assert runner._request("session/prompt", {"sessionId": "sess-1"}) == {"stopReason": "end_turn"}
    assert runner._responses == {}
