"""The TCP listener stays on loopback (AGENTS.md §6.1).

The API has no authentication over TCP, and the Host check is no defense on a
network: any client can send `Host: 127.0.0.1`. `--host 0.0.0.0` would hand
run control to the whole network.
"""

from __future__ import annotations

import pytest

from pulse.daemon import server


@pytest.fixture
def daemon_starts(monkeypatch) -> list[str]:
    started: list[str] = []
    monkeypatch.setattr(server, "run_daemon", lambda *, host, port: started.append(host))
    return started


@pytest.mark.parametrize(
    "host",
    # S104: these are the hosts the test proves the daemon refuses to bind.
    ["0.0.0.0", "::", "192.168.1.10", "example.com"],  # noqa: S104
)
def test_a_non_loopback_host_is_refused_before_the_daemon_starts(daemon_starts, capsys, host):
    exit_code = server.main(["serve", "--host", host])

    assert exit_code == server.USAGE_ERROR
    assert daemon_starts == []
    assert host in capsys.readouterr().err


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1", "localhost"])
def test_a_loopback_host_is_served(daemon_starts, host):
    assert server.main(["--host", host]) == 0
    assert daemon_starts == [host]
