from __future__ import annotations

import contextlib
import ipaddress
import os
import signal
import socket
import sys
import threading
from pathlib import Path

import uvicorn

from pulse.api.app import create_app
from pulse.daemon.runs import RunManager
from pulse.store.paths import (
    DAEMON_SOCKET,
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    clear_daemon_meta,
    ensure_global_dir,
    write_daemon_meta,
)

SOCKET_MODE = 0o600
USAGE_ERROR = 2
LOCALHOST = "localhost"
# Masks every permission bit SOCKET_MODE does not grant.
_SOCKET_UMASK = 0o777 & ~SOCKET_MODE


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


def bind_private_socket(path: Path) -> socket.socket:
    """The daemon's Unix socket, connectable only by the user who started it.

    Whoever connects can start runs and answer their questions (AGENTS.md §6.1).
    uvicorn's own `bind_socket` makes the socket 0666 before anyone could tighten
    it, so Pulse binds it under a umask that keeps it private from the first
    instant. Changing the umask is process-wide; this runs before any server
    thread starts.
    """
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    previous = os.umask(_SOCKET_UMASK)
    try:
        server.bind(str(path))
    except OSError:
        server.close()
        raise
    finally:
        os.umask(previous)
    os.chmod(path, SOCKET_MODE)
    return server


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
    uds_socket = bind_private_socket(sock)
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


def is_loopback(host: str) -> bool:
    if host == LOCALHOST:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
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
    # The TCP API is unauthenticated; off loopback anyone on the network could drive runs.
    if not is_loopback(host):
        sys.stderr.write(f"pulse-engine: refusing to listen on non-loopback host {host!r}\n")
        return USAGE_ERROR
    run_daemon(host=host, port=port)
    return 0
