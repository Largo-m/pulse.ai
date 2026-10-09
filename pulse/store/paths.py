"""Where Pulse keeps its state under `~/.pulse`.

The single definition of that layout: config, daemon, client and engine all
read it from here, so moving the directory is a one-line change.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

GLOBAL_DIR = Path.home() / ".pulse"
GLOBAL_DB_FILE = GLOBAL_DIR / "pulse.db"
DAEMON_SOCKET = GLOBAL_DIR / "daemon.sock"
DAEMON_META_FILE = GLOBAL_DIR / "daemon.json"
DAEMON_LOG_FILE = GLOBAL_DIR / "daemon.log"
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8787
META_MODE = 0o600


def global_state_dir() -> Path:
    home = os.environ.get("PULSE_HOME")
    if home:
        return Path(home).expanduser()
    db_override = os.environ.get("PULSE_DB")
    if db_override:
        return Path(db_override).expanduser().resolve().parent
    return GLOBAL_DIR


def ensure_global_dir() -> Path:
    GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
    return GLOBAL_DIR


def safe_cwd() -> Path:
    """The current directory, or the Pulse state dir when it cannot be read.

    `os.getcwd()` raises `EPERM` on macOS inside protected folders (e.g. Trash)
    and `ENOENT` once the folder is deleted; the detached daemon hits this when
    its inherited cwd disappears. Falling back to `~/.pulse` leads callers to
    the existing "no project" path instead of crashing the run.
    """
    try:
        return Path.cwd()
    except OSError:
        return global_state_dir()


def worktrees_dir() -> Path:
    """Directory for run worktrees, deliberately outside the repository.

    Inside the project it would need a `.gitignore` entry and nested worktrees
    confuse tools that walk the tree; under `~/.pulse/` it lives with the rest
    of the Pulse state.
    """
    return global_state_dir() / "worktrees"


def write_daemon_meta(
    *, pid: int, http_host: str, http_port: int, socket_path: Path, token: str
) -> None:
    """Record where the daemon listens and the token its TCP listener demands.

    Created `0600` and re-tightened if an older daemon left it wider: whoever
    reads the token can drive runs over TCP (ADR 0005).
    """
    ensure_global_dir()
    payload = {
        "pid": pid,
        "http_host": http_host,
        "http_port": http_port,
        "socket": str(socket_path),
        "token": token,
    }
    descriptor = os.open(DAEMON_META_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, META_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as meta:
        os.fchmod(meta.fileno(), META_MODE)
        meta.write(json.dumps(payload, indent=2) + "\n")


def read_daemon_meta() -> dict[str, Any] | None:
    if not DAEMON_META_FILE.is_file():
        return None
    try:
        data = json.loads(DAEMON_META_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def clear_daemon_meta(pid: int | None = None) -> None:
    """Delete meta and socket. With `pid`, only if the meta still belongs to it.

    Keeps a daemon that lost the race, or a late `stop`, from deleting the files
    of another daemon that is running.
    """
    if pid is not None:
        meta = read_daemon_meta()
        if meta is not None and meta.get("pid") != pid:
            return
    for path in (DAEMON_META_FILE, DAEMON_SOCKET):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
