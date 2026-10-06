from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GLOBAL_DIR = Path.home() / ".pulse"
DAEMON_SOCKET = GLOBAL_DIR / "daemon.sock"
DAEMON_PID_FILE = GLOBAL_DIR / "daemon.pid"
DAEMON_META_FILE = GLOBAL_DIR / "daemon.json"
#: Traceback do daemon. Ele roda destacado do terminal: sem isto, uma run que
#: morre por uma exceção inesperada não deixa pista nenhuma em lugar nenhum.
DAEMON_LOG_FILE = GLOBAL_DIR / "daemon.log"
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8787


def ensure_global_dir() -> Path:
    GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
    return GLOBAL_DIR


def write_daemon_meta(*, pid: int, http_host: str, http_port: int, socket_path: Path) -> None:
    ensure_global_dir()
    payload = {
        "pid": pid,
        "http_host": http_host,
        "http_port": http_port,
        "socket": str(socket_path),
    }
    DAEMON_META_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    DAEMON_PID_FILE.write_text(str(pid) + "\n", encoding="utf-8")


def read_daemon_meta() -> dict[str, Any] | None:
    if not DAEMON_META_FILE.is_file():
        return None
    try:
        data = json.loads(DAEMON_META_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def clear_daemon_meta(pid: int | None = None) -> None:
    """Apaga meta, pid e socket. Com `pid`, só se o meta ainda for desse processo.

    Um daemon que perdeu a corrida, ou um `stop` atrasado, não pode apagar os
    arquivos de outro daemon que está de pé.
    """
    if pid is not None:
        meta = read_daemon_meta()
        if meta is not None and meta.get("pid") != pid:
            return
    for path in (DAEMON_META_FILE, DAEMON_PID_FILE):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        DAEMON_SOCKET.unlink(missing_ok=True)
    except OSError:
        pass
