"""The TCP listener stays on loopback (AGENTS.md §6.1), on a host the API answers.

Off loopback the token would cross the network in clear text, and anyone on it
could try it: `--host 0.0.0.0` would offer run control to the whole network. A
loopback address outside `TRUSTED_HOSTS` would start a daemon that answers 400
to every request.
"""

from __future__ import annotations

import pytest

from pulse.api.app import TRUSTED_HOSTS
from pulse.daemon import server


@pytest.fixture
def daemon_starts(monkeypatch) -> list[str]:
    started: list[str] = []
    monkeypatch.setattr(server, "run_daemon", lambda *, host, port: started.append(host))
    return started


@pytest.mark.parametrize(
    "host",
    # S104: these are the hosts the test proves the daemon refuses to bind.
    ["0.0.0.0", "::", "192.168.1.10", "example.com", "127.0.0.2", "::1"],  # noqa: S104
)
def test_a_host_the_api_would_not_answer_is_refused_before_the_daemon_starts(
    daemon_starts, capsys, host
):
    exit_code = server.main(["serve", "--host", host])

    assert exit_code == server.USAGE_ERROR
    assert daemon_starts == []
    assert host in capsys.readouterr().err


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_a_loopback_host_is_served(daemon_starts, host):
    assert server.main(["--host", host]) == 0
    assert daemon_starts == [host]


def test_every_host_the_daemon_listens_on_passes_the_host_check():
    assert set(server.LOOPBACK_HOSTS) <= set(TRUSTED_HOSTS)
