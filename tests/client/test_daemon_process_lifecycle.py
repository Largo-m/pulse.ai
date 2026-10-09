"""The daemon process seen from the client: is it alive, and stopping it via its meta file.

The meta file and socket live in a per-test temp dir; signals go through a fake
`os.kill` so no real process is touched, and time is a fake clock so waiting for
an exit costs nothing.
"""

from __future__ import annotations

import json
import signal
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

import pulse.client.daemon_process as daemon_process
import pulse.store.paths as paths
from pulse.client.daemon_process import is_daemon_alive, stop_daemon

PID = 424242


@pytest.fixture
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points the meta file and the socket at a temp dir."""
    monkeypatch.setattr(paths, "GLOBAL_DIR", tmp_path)
    monkeypatch.setattr(paths, "DAEMON_META_FILE", tmp_path / "daemon.json")
    monkeypatch.setattr(paths, "DAEMON_SOCKET", tmp_path / "daemon.sock")
    monkeypatch.setattr(daemon_process, "DAEMON_SOCKET", tmp_path / "daemon.sock")
    return tmp_path


def _write_meta(state: Path, **fields: object) -> Path:
    meta = state / "daemon.json"
    meta.write_text(json.dumps(fields), encoding="utf-8")
    return meta


class _Processes:
    """A fake process table behind `os.kill`: `alive` pids answer signal 0."""

    def __init__(self, alive: set[int], *, exits_after_checks: int | None = None) -> None:
        self.alive = set(alive)
        self.signals: list[tuple[int, int]] = []
        self._exits_after = exits_after_checks
        self._checks = 0

    def kill(self, pid: int, sig: int) -> None:
        self.signals.append((pid, sig))
        if sig == 0 and pid in self.alive and self._exits_after is not None:
            self._checks += 1
            if self._checks > self._exits_after:
                self.alive.discard(pid)
        if pid not in self.alive:
            raise ProcessLookupError(pid)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _install(monkeypatch: pytest.MonkeyPatch, processes: _Processes) -> _FakeClock:
    clock = _FakeClock()
    monkeypatch.setattr(daemon_process.os, "kill", processes.kill)
    monkeypatch.setattr(daemon_process, "time", clock)
    return clock


@pytest.fixture
def listening_port() -> Iterator[int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        yield server.getsockname()[1]
    finally:
        server.close()


@pytest.fixture
def closed_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def test_no_meta_file_means_no_daemon(state: Path):
    assert is_daemon_alive() is False


@pytest.mark.parametrize("pid", [None, "123", 1.5])
def test_a_meta_without_an_integer_pid_means_no_daemon(state: Path, pid: object):
    """A corrupt meta must not lead the client to signal an arbitrary process."""
    _write_meta(state, pid=pid)

    assert is_daemon_alive() is False


def test_a_dead_pid_means_no_daemon_even_with_a_socket(state: Path, monkeypatch):
    """A crashed daemon leaves its socket behind; the file alone proves nothing."""
    _install(monkeypatch, _Processes(alive=set()))
    _write_meta(state, pid=PID)
    (state / "daemon.sock").touch()

    assert is_daemon_alive() is False


def test_a_live_pid_with_its_socket_is_alive(state: Path, monkeypatch):
    processes = _Processes(alive={PID})
    _install(monkeypatch, processes)
    _write_meta(state, pid=PID)
    (state / "daemon.sock").touch()

    assert is_daemon_alive() is True
    assert processes.signals == [(PID, 0)]


def test_a_live_pid_without_socket_is_alive_when_its_port_accepts(
    state: Path, monkeypatch, listening_port: int
):
    _install(monkeypatch, _Processes(alive={PID}))
    _write_meta(state, pid=PID, http_host="127.0.0.1", http_port=listening_port)

    assert is_daemon_alive() is True


def test_a_live_pid_whose_port_refuses_is_not_a_daemon(state: Path, monkeypatch, closed_port: int):
    """A recycled pid belongs to some other process; only a reachable engine counts."""
    _install(monkeypatch, _Processes(alive={PID}))
    _write_meta(state, pid=PID, http_host="127.0.0.1", http_port=closed_port)

    assert is_daemon_alive() is False


def test_stop_without_a_pid_clears_the_stale_meta(state: Path, monkeypatch):
    processes = _Processes(alive=set())
    _install(monkeypatch, processes)
    meta = _write_meta(state, pid="garbage")
    (state / "daemon.sock").touch()

    assert stop_daemon() is True

    assert not meta.exists()
    assert not (state / "daemon.sock").exists()
    assert processes.signals == []


def test_stop_with_no_meta_at_all_succeeds(state: Path, monkeypatch):
    _install(monkeypatch, _Processes(alive=set()))

    assert stop_daemon() is True


def test_stop_sends_sigterm_and_clears_the_meta_once_the_process_exits(state: Path, monkeypatch):
    processes = _Processes(alive={PID}, exits_after_checks=2)
    _install(monkeypatch, processes)
    meta = _write_meta(state, pid=PID)

    assert stop_daemon() is True

    assert processes.signals[0] == (PID, signal.SIGTERM)
    assert processes.signals[1:] == [(PID, 0)] * 3
    assert not meta.exists()


def test_stop_of_an_already_dead_process_still_clears_its_meta(state: Path, monkeypatch):
    """SIGTERM failing because the process is gone is the goal reached, not an error."""
    processes = _Processes(alive=set())
    _install(monkeypatch, processes)
    meta = _write_meta(state, pid=PID)

    assert stop_daemon() is True

    assert not meta.exists()


def test_stop_reports_a_daemon_that_ignores_sigterm_and_keeps_its_meta(state: Path, monkeypatch):
    """Clearing the meta of a live daemon would orphan it, still holding the port."""
    processes = _Processes(alive={PID})
    clock = _install(monkeypatch, processes)
    meta = _write_meta(state, pid=PID)

    assert stop_daemon(timeout=1.0) is False

    assert meta.exists()
    assert clock.now >= 1.0
    assert processes.signals[0] == (PID, signal.SIGTERM)


def test_stop_does_not_clear_the_meta_of_a_newer_daemon(state: Path, monkeypatch):
    """A new daemon may have replaced the meta while the old one was exiting."""
    meta = state / "daemon.json"

    class _Replaced(_Processes):
        def kill(self, pid: int, sig: int) -> None:
            if sig == 0:
                meta.write_text(json.dumps({"pid": PID + 1}), encoding="utf-8")
            super().kill(pid, sig)

    _install(monkeypatch, _Replaced(alive={PID}, exits_after_checks=0))
    _write_meta(state, pid=PID)

    assert stop_daemon() is True

    assert json.loads(meta.read_text(encoding="utf-8")) == {"pid": PID + 1}
