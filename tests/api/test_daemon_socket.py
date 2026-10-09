"""The daemon's Unix socket is private to the user who started it.

Connecting to it is enough to start runs and answer their questions, so another
local user must not be able to (AGENTS.md §6.1: user-only permissions).
"""

from __future__ import annotations

import os
import socket
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from pulse.daemon.server import bind_private_socket


@pytest.fixture
def socket_dir() -> Iterator[Path]:
    # A short path: macOS caps a socket path at 104 bytes, and `tmp_path` is longer.
    with tempfile.TemporaryDirectory(prefix="pulse-") as directory:
        yield Path(directory)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_the_socket_is_read_write_for_its_owner_only(socket_dir: Path):
    path = socket_dir / "daemon.sock"

    with bind_private_socket(path):
        assert stat.S_ISSOCK(path.stat().st_mode)
        assert _mode(path) == 0o600


def test_the_socket_is_private_even_under_a_permissive_umask(socket_dir: Path):
    """A user's umask of 000 must not leave a window where anyone can connect."""
    previous = os.umask(0)
    try:
        with bind_private_socket(socket_dir / "daemon.sock"):
            assert _mode(socket_dir / "daemon.sock") == 0o600
    finally:
        os.umask(previous)


def test_binding_restores_the_process_umask(socket_dir: Path):
    previous = os.umask(0o022)
    try:
        with bind_private_socket(socket_dir / "daemon.sock"):
            assert os.umask(0o022) == 0o022
    finally:
        os.umask(previous)


def test_a_stale_socket_from_a_dead_daemon_is_replaced(socket_dir: Path):
    path = socket_dir / "daemon.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(path))
    stale.close()

    with bind_private_socket(path) as server:
        server.listen(1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(path))
        assert _mode(path) == 0o600


def test_a_socket_that_cannot_be_bound_raises_instead_of_leaking(
    socket_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """The umask is process-wide: left at the socket's, every later file is private too.

    The bind's socket is closed, or its descriptor stays open for the daemon's life.
    """
    opened: list[socket.socket] = []

    class Recorded(socket.socket):
        def __init__(self, *args: object) -> None:
            super().__init__(*args)  # type: ignore[arg-type]  # forwards socket's own args
            opened.append(self)

    monkeypatch.setattr(socket, "socket", Recorded)
    caller_umask = 0o022
    previous = os.umask(caller_umask)
    try:
        with pytest.raises(FileNotFoundError):
            bind_private_socket(socket_dir / "missing" / "daemon.sock")
        restored = os.umask(previous)
    finally:
        os.umask(previous)

    assert restored == caller_umask
    assert [sock.fileno() for sock in opened] == [-1]
    assert os.listdir(socket_dir) == []
