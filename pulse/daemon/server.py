from __future__ import annotations

import os
import signal
import socket
import sys
import threading
from pathlib import Path

import uvicorn

from pulse.api.app import create_app
from pulse.daemon.paths import (
    DAEMON_SOCKET,
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    clear_daemon_meta,
    ensure_global_dir,
    read_daemon_meta,
    write_daemon_meta,
)
from pulse.daemon.runs import RunManager


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
    """Ancora o daemon em `~/.pulse` em vez do diretório de quem o iniciou.

    O engine sobe destacado (`start_new_session`) e herda o cwd do terminal que
    o chamou — e aí fica, por semanas. Esse diretório não é dele: basta apagar o
    projeto para o cwd do daemon virar uma pasta na Lixeira, onde o macOS nega
    até `getcwd()` (`EPERM`). Toda run nova morria aí, antes do primeiro step,
    porque resolver config começa perguntando onde estamos.

    Ancorar não perde nada: a run roda com `cwd` explícito (o workspace, ou o
    worktree dela), e o cwd do daemon só servia de chute para cliente que não
    disse qual projeto queria — chute que já estava errado sempre que o engine
    e a TUI nasceram em projetos diferentes.
    """
    try:
        os.chdir(ensure_global_dir())
    except OSError:
        # Sem o diretório de estado o daemon tem problema maior que o cwd; quem
        # precisa dele levanta mais à frente, com mensagem melhor que esta.
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
    if sock.exists():
        try:
            sock.unlink()
        except OSError:
            pass

    manager = RunManager()
    app = create_app(manager)
    write_daemon_meta(pid=os.getpid(), http_host=host, http_port=port, socket_path=sock)

    def _cleanup(*_args: object) -> None:
        clear_daemon_meta()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)

    config_tcp = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server_tcp = uvicorn.Server(config_tcp)

    config_uds = uvicorn.Config(app, uds=str(sock), log_level="warning")
    server_uds = uvicorn.Server(config_uds)

    def _run_uds() -> None:
        try:
            os.chmod(sock, 0o600)
        except OSError:
            pass
        server_uds.run()

    uds_thread = threading.Thread(target=_run_uds, name="pulse-uds", daemon=True)
    uds_thread.start()
    try:
        try:
            os.chmod(sock, 0o600)
        except OSError:
            pass
        server_tcp.run()
    finally:
        server_uds.should_exit = True
        clear_daemon_meta()


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
