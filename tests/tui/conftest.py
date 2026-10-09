from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from pulse.client.engine_client import EngineClient

DAEMON_DOWN = "connection refused by pulse-engine"
WAIT_SECONDS = 5.0


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


async def wait_until(
    pilot: Any, predicate: Callable[[], bool], *, timeout: float = WAIT_SECONDS
) -> None:
    """Let the app work until `predicate` holds; fail instead of hanging.

    `pilot.pause()` waits for the app to go idle, so no delay is guessed; the
    timeout only bounds a condition that never comes.
    """
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached")
        await pilot.pause()
