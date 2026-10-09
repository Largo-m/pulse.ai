"""How the client degrades when the engine cannot be reached or answers badly.

Only transport and decoding failures count as "engine unavailable"; anything
else is a bug and must surface instead of looking like a down daemon.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest

import pulse.client.active_runs as active_runs_module
import pulse.client.engine_client as engine_client_module
from pulse.client.engine_client import EngineClient
from pulse.client.protocol import ENGINE_PROTOCOL
from pulse.client.run_session import DETACHED, EngineRunSession


def _refused(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> EngineClient:
    return EngineClient(transport=httpx.MockTransport(handler))


def test_ping_reports_a_refused_connection_as_no_engine():
    """`ping` drives the start-the-daemon decision; a refused socket must read as "down"."""
    assert _client(_refused).ping() is False


def test_ping_reports_a_non_json_status_as_no_engine():
    """Something else listening on the port is not a usable engine."""
    client = _client(lambda _request: httpx.Response(200, text="<html>nginx</html>"))

    assert client.ping() is False


def test_ping_reports_an_error_status_as_no_engine():
    client = _client(lambda _request: httpx.Response(500, json={"ok": True}))

    assert client.ping() is False


def test_a_daemon_with_an_unreadable_protocol_is_replaced(monkeypatch):
    """An engine reporting a protocol that is not a number is treated as outdated, not fatal."""
    protocol: dict[str, Any] = {"value": "garbage"}
    stopped: list[bool] = []

    def status(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "protocol": protocol["value"]})

    def fake_stop_daemon() -> bool:
        stopped.append(True)
        protocol["value"] = ENGINE_PROTOCOL
        return True

    monkeypatch.setattr(engine_client_module, "stop_daemon", fake_stop_daemon)
    client = _client(status)
    monkeypatch.setattr(client, "_start_daemon", lambda: None)

    client.ensure_daemon(timeout=1.0)

    assert stopped == [True]


def test_listing_runs_with_the_engine_down_finds_none(monkeypatch):
    """Screens ask for live runs on every refresh; a down daemon means none, not a crash."""
    monkeypatch.setattr(
        active_runs_module,
        "EngineClient",
        lambda *, timeout: EngineClient(timeout=timeout, transport=httpx.MockTransport(_refused)),
    )

    assert active_runs_module.list_runs() == []


def test_listing_runs_does_not_hide_a_bug_as_a_down_engine(monkeypatch):
    """Only transport and decoding errors mean "no runs"; a programming error must surface."""

    class _BuggyClient:
        def list_runs(self) -> list[dict[str, Any]]:
            raise AttributeError("bug")

        def close(self) -> None:
            return None

    monkeypatch.setattr(active_runs_module, "EngineClient", lambda *, timeout: _BuggyClient())

    with pytest.raises(AttributeError, match="bug"):
        active_runs_module.list_runs()


def test_stop_with_the_engine_down_reports_not_stopped():
    """The UI must learn the stop did not reach the daemon instead of crashing."""
    session = EngineRunSession(stream=None, prompt_handler=None, client=_client(_refused))
    session.run_id = "run-1"

    assert session.stop() is False


def test_stop_reaches_the_daemon_when_it_answers():
    seen: list[str] = []

    def cancel(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    session = EngineRunSession(stream=None, prompt_handler=None, client=_client(cancel))
    session.run_id = "run-1"

    assert session.stop() is True
    assert seen == ["/api/runs/run-1/cancel"]


class _CutStreamClient:
    """A client whose event stream breaks with `error` right after the first event."""

    def __init__(self, error: Exception, *, close_error: Exception | None = None) -> None:
        self._error = error
        self._close_error = close_error

    def stream_events(self, run_id: str) -> Iterator[dict[str, Any]]:
        yield {"type": "phase.begin", "title": "Plan"}
        raise self._error

    def close(self) -> None:
        if self._close_error is not None:
            raise self._close_error


class _Stream:
    """Calls `on_phase` when a phase begins: the moment the user leaves the screen."""

    def __init__(self, on_phase: Callable[[], None]) -> None:
        self._on_phase = on_phase

    def begin_phase(self, _title: str, *, turn: int = 1) -> None:
        self._on_phase()


def _session(client: Any, on_phase: Callable[[EngineRunSession], None]) -> EngineRunSession:
    holder: list[EngineRunSession] = []
    session = EngineRunSession(
        stream=_Stream(lambda: on_phase(holder[0])), prompt_handler=None, client=client
    )
    holder.append(session)
    session.run_id = "run-1"
    return session


def test_a_read_cut_by_detach_is_a_detach_not_a_failure():
    """Detaching closes the client under the read; the run keeps going in the daemon."""
    session = _session(_CutStreamClient(httpx.ReadError("closed")), EngineRunSession.detach)

    assert session.listen() == DETACHED


def test_detach_survives_a_socket_already_gone():
    """Leaving a run must work even when closing the dead connection fails."""
    client = _CutStreamClient(httpx.ReadError("closed"), close_error=OSError("bad fd"))
    session = _session(client, EngineRunSession.detach)

    assert session.listen() == DETACHED


def test_a_lost_stream_while_attached_is_reported():
    """Without a detach, a broken stream is a real failure the caller must see."""
    session = _session(_CutStreamClient(httpx.ReadError("reset")), lambda _session: None)

    with pytest.raises(httpx.ReadError):
        session.listen()


def test_a_bug_after_detaching_is_not_hidden():
    """Detach excuses only the cut read; a programming error must still surface."""

    def detach_then_fail(session: EngineRunSession) -> None:
        session.detach()
        raise KeyError("bug")

    session = _session(_CutStreamClient(httpx.ReadError("closed")), detach_then_fail)

    with pytest.raises(KeyError, match="bug"):
        session.listen()
