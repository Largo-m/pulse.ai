from __future__ import annotations

import httpx
import pytest

from pulse.client.engine_client import EngineClient

DAEMON_DOWN = "connection refused by pulse-engine"


@pytest.fixture(autouse=True)
def _screens_reach_an_in_process_daemon(in_process_daemon: object) -> None:
    """A screen never starts a real daemon, and never touches SQLite behind its back."""


def _refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError(DAEMON_DOWN, request=request)


def cut_the_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """From here on every `EngineClient` finds no daemon, as when the socket and port refuse."""
    unreachable = httpx.Client(transport=httpx.MockTransport(_refuse), base_url="http://pulse")
    monkeypatch.setattr(EngineClient, "_http", lambda _self: unreachable)


@pytest.fixture
def daemon_down(monkeypatch: pytest.MonkeyPatch) -> None:
    cut_the_daemon(monkeypatch)
