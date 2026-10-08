"""The daemon process seen from outside: alive check and stop, via its meta file.

Lives on the client side so `pulse daemon` and `EngineClient` can manage the
daemon without importing the server, which pulls in the whole engine.
"""

from __future__ import annotations

import os
import signal
import socket
import time

from pulse.paths import (
    DAEMON_SOCKET,
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    clear_daemon_meta,
    read_daemon_meta,
)


def is_daemon_alive() -> bool:
    meta = read_daemon_meta()
    if meta is None:
        return False
    pid = meta.get("pid")
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    if DAEMON_SOCKET.exists():
        return True
    host = str(meta.get("http_host") or DEFAULT_HTTP_HOST)
    port = int(meta.get("http_port") or DEFAULT_HTTP_PORT)
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def stop_daemon(timeout: float = 5.0) -> bool:
    """SIGTERM the daemon from the meta file and wait for it to exit. `False` = still alive.

    The meta is only cleared once the process exits; clearing it earlier would
    orphan a daemon still holding the port.
    """
    meta = read_daemon_meta() or {}
    pid = meta.get("pid")
    if not isinstance(pid, int):
        clear_daemon_meta()
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            clear_daemon_meta(pid)
            return True
        time.sleep(0.1)
    return False
