from __future__ import annotations

import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn

from pulse.api.app import create_app
from pulse.daemon.runs import RunManager
from pulse.paths import (
    DAEMON_SOCKET,
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    clear_daemon_meta,
    ensure_global_dir,
    read_daemon_meta,
    write_daemon_meta,
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


def _anchor_cwd() -> None:
    """Anchor the daemon in `~/.pulse` instead of the launcher's directory.

    The detached daemon would otherwise keep the launching terminal's cwd; if
    that project is deleted, macOS denies `getcwd()` (`EPERM`) and every new run
    fails. Runs always use an explicit `cwd`, so nothing is lost.
    """
    try:
        os.chdir(ensure_global_dir())
    except OSError:
        pass


def run_daemon(
    *,
    host: str = DEFAULT_HTTP_HOST,
    port: int = DEFAULT_HTTP_PORT,
    socket_path: Path | None = None,
) -> None:
    ensure_global_dir()
    _anchor_cwd()
    sock = socket_path or DAEMON_SOCKET
    manager = RunManager()
    app = create_app(manager)
    pid = os.getpid()

    config_tcp = uvicorn.Config(app, host=host, port=port, log_level="warning")
    config_uds = uvicorn.Config(app, uds=str(sock), log_level="warning")
    tcp_socket = config_tcp.bind_socket()
    if sock.exists():
        try:
            sock.unlink()
        except OSError:
            pass
    uds_socket = config_uds.bind_socket()
    os.chmod(sock, 0o600)
    write_daemon_meta(pid=pid, http_host=host, http_port=port, socket_path=sock)

    def _cleanup(*_args: object) -> None:
        clear_daemon_meta(pid)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)

    server_tcp = uvicorn.Server(config_tcp)
    server_uds = uvicorn.Server(config_uds)
    uds_thread = threading.Thread(
        target=server_uds.run, kwargs={"sockets": [uds_socket]}, name="pulse-uds", daemon=True
    )
    uds_thread.start()
    try:
        server_tcp.run(sockets=[tcp_socket])
    finally:
        server_uds.should_exit = True
        clear_daemon_meta(pid)


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


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "serve":
        args = args[1:]
    host = DEFAULT_HTTP_HOST
    port = DEFAULT_HTTP_PORT
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
            continue
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
            continue
        i += 1
    run_daemon(host=host, port=port)
    return 0
