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
    manager = RunManager()
    app = create_app(manager)
    pid = os.getpid()

    config_tcp = uvicorn.Config(app, host=host, port=port, log_level="warning")
    config_uds = uvicorn.Config(app, uds=str(sock), log_level="warning")
    # A porta TCP primeiro: é ela que decide quem é o daemon. Quem perde a
    # corrida sai aqui (o uvicorn encerra com SystemExit), antes de apagar o
    # socket e o meta de quem ganhou — senão o daemon vivo ficava sem nenhum
    # dos dois e `pulse daemon stop` não tinha mais como achá-lo.
    tcp_socket = config_tcp.bind_socket()
    if sock.exists():
        try:
            sock.unlink()
        except OSError:
            pass
    uds_socket = config_uds.bind_socket()
    # O uvicorn deixa o socket em 0o666 ao criar; o chmod só vale depois dele.
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
    """SIGTERM no daemon do meta e espera ele sair. `False` = continua vivo.

    Só limpa o meta quando o processo saiu: apagar o de um daemon que ainda
    segura a porta é o que o deixava órfão, sem ninguém conseguir pará-lo.
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
